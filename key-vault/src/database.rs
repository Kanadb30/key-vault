//! Append-only scan store. All relational query operators remain in Python.
use crate::catalog::{
    manager::CatalogManager,
    table::{TableId, TableMetadata},
};
use crate::codec::{self, Column};
use crate::error::{CustomError, Result};
use crate::storage::{buffer_pool::BufferPool, page::PageType};
use serde_json::Value;
use std::collections::HashSet;

pub struct Database {
    catalog_manager: CatalogManager,
    buffer_pool: BufferPool,
}

impl Database {
    pub fn new(path: &str) -> Result<Self> {
        let mut pool = BufferPool::new(path)?;
        if pool.total_pages_in_disk()? == 0 {
            pool.allocate(PageType::StartPage)?;
            pool.flush()?; // Valid start page durable before any catalog/data allocation.
        }
        let (next_id, mut catalog) = {
            let guard = pool.guard(0)?;
            let page = guard.page();
            if page.get_page_type() != PageType::StartPage {
                return Err(CustomError::Corrupt("missing start page".into()));
            }
            (page.get_next_table_id()?, page.get_catalog_page_no()?)
        };
        let mut manager = CatalogManager::new(next_id);
        let mut visited = HashSet::new();
        while catalog != u32::MAX {
            if !visited.insert(catalog) {
                return Err(CustomError::Corrupt("catalog cycle".into()));
            }
            let guard = pool.guard(catalog)?;
            let page = guard.page();
            if page.get_page_type() != PageType::CatalogPage {
                return Err(CustomError::Corrupt(
                    "catalog points to non-catalog page".into(),
                ));
            }
            for i in 0..page.get_record_count() {
                let table = codec::decode_catalog(page.read_record(i)?)?;
                if table.table_id().id() >= next_id || table.start_page() == 0 {
                    return Err(CustomError::Corrupt("invalid table id/start page".into()));
                }
                manager.add_table(table)?;
            }
            catalog = page.get_next_page_no();
        }
        // Validate every on-disk header, even pages not visited by the catalog.
        for no in 0..pool.total_pages_in_disk()? {
            drop(pool.guard(no as u32)?);
        }
        let mut db = Self {
            catalog_manager: manager,
            buffer_pool: pool,
        };
        // Validate row chains eagerly at open; a corrupt table is never silently ignored.
        let names: Vec<_> = db.tables().iter().map(|t| t.table_name().clone()).collect();
        for name in names {
            db.scan_table(&name)?;
        }
        Ok(db)
    }
    pub fn tables(&self) -> Vec<TableMetadata> {
        let mut tables: Vec<_> = self
            .catalog_manager
            .get_catalog()
            .tables()
            .cloned()
            .collect();
        tables.sort_by_key(|t| t.table_id().id());
        tables
    }
    fn table(&self, name: &str) -> Result<TableMetadata> {
        self.tables()
            .into_iter()
            .find(|t| t.table_name() == name)
            .ok_or_else(|| CustomError::Schema(format!("unknown table '{name}'")))
    }
    pub fn create_table(&mut self, name: String, columns: Vec<Column>) -> Result<TableId> {
        codec::validate_schema(&name, &columns)?;
        if self.tables().iter().any(|t| t.table_name() == &name) {
            return Err(CustomError::TableNameExists(name));
        }
        codec::encode_catalog(&TableMetadata::new(
            TableId::new(0),
            1,
            name.clone(),
            columns.clone(),
        ))?;
        let start = self.buffer_pool.allocate(PageType::DataPage)?;
        let id = self
            .catalog_manager
            .create_table(start, name.clone(), columns)?;
        let record = codec::encode_catalog(&self.table(&name)?)?;
        let head = self.buffer_pool.guard(0)?.page().get_catalog_page_no()?;
        let head = if head == u32::MAX {
            let no = self.buffer_pool.allocate(PageType::CatalogPage)?;
            self.buffer_pool
                .guard(0)?
                .page_mut()
                .set_catalog_page_no(no)?;
            no
        } else {
            head
        };
        self.append(head, PageType::CatalogPage, &record)?;
        self.buffer_pool
            .guard(0)?
            .page_mut()
            .set_next_table_id(id.id() + 1)?;
        self.flush()?;
        Ok(id)
    }
    fn append(&mut self, mut page_no: u32, kind: PageType, record: &[u8]) -> Result<()> {
        let mut visited = HashSet::new();
        loop {
            if !visited.insert(page_no) {
                return Err(CustomError::Corrupt("page chain cycle".into()));
            }
            let (result, next) = {
                let mut guard = self.buffer_pool.guard(page_no)?;
                if guard.page().get_page_type() != kind {
                    return Err(CustomError::Corrupt("wrong page type in chain".into()));
                }
                let next = guard.page().get_next_page_no();
                // Always append at the chain tail to preserve insertion order.
                let result = if next == u32::MAX {
                    guard.page_mut().insert_into_page(record)
                } else {
                    Err(CustomError::PageFull)
                };
                (result, next)
            };
            match result {
                Ok(()) => return Ok(()),
                Err(CustomError::PageFull) => {
                    page_no = if next != u32::MAX {
                        next
                    } else {
                        let new = self.buffer_pool.allocate(kind)?;
                        self.buffer_pool
                            .guard(page_no)?
                            .page_mut()
                            .set_next_page_no(new);
                        new
                    };
                }
                Err(e) => return Err(e),
            }
        }
    }
    pub fn insert_rows(&mut self, name: &str, rows: &[Vec<Value>]) -> Result<usize> {
        let table = self.table(name)?;
        let encoded: Vec<_> = rows
            .iter()
            .map(|r| codec::encode_row(table.columns(), r))
            .collect::<Result<_>>()?;
        for row in encoded {
            self.append(table.start_page(), PageType::DataPage, &row)?;
        }
        self.flush()?;
        Ok(rows.len())
    }
    pub fn scan_table(&mut self, name: &str) -> Result<Vec<Vec<Value>>> {
        let table = self.table(name)?;
        let mut page_no = table.start_page();
        let mut visited = HashSet::new();
        let mut rows = Vec::new();
        while page_no != u32::MAX {
            if !visited.insert(page_no) {
                return Err(CustomError::Corrupt("data page cycle".into()));
            }
            let guard = self.buffer_pool.guard(page_no)?;
            let page = guard.page();
            if page.get_page_type() != PageType::DataPage {
                return Err(CustomError::Corrupt("table points to non-data page".into()));
            }
            for i in 0..page.get_record_count() {
                rows.push(codec::decode_row(table.columns(), page.read_record(i)?)?);
            }
            page_no = page.get_next_page_no();
        }
        Ok(rows)
    }
    pub fn dump_page(&mut self, no: u32) -> Result<[u8; 4096]> {
        Ok(self.buffer_pool.guard(no)?.page().data)
    }
    pub fn flush(&mut self) -> Result<()> {
        self.buffer_pool.flush()
    }
}
impl Drop for Database {
    fn drop(&mut self) {
        let _ = self.flush();
    }
}
