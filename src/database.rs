use crate::catalog::manager::CatalogManager;
use crate::catalog::table::{TableMetadata, TableId};
use crate::storage::buffer_pool::BufferPool;
use crate::error::{Result, CustomError};
use crate::storage::page::{PageType, PAGE_HEADER_SIZE};

pub struct Database {
    catalog_manager: CatalogManager,
    buffer_pool: BufferPool,
}

impl Database {
    pub fn new(db_name: &str) -> Result<Database> {
        let mut b_p = BufferPool::new(db_name)?;
        let (next_table_id, mut catalog_page_no) = match b_p.fetch_page(0) {
            Ok(page) => {
                let is_valid_start_page = page.get_page_no() == 0
                    && page.get_page_type() == PageType::StartPage
                    && page.get_data_end() >= PAGE_HEADER_SIZE as u16;

                if !is_valid_start_page {
                    return Err(CustomError::Err_from_wrong_arg("The first page is missing or corrupted, but other pages exist".to_string()));
                }
                (page.get_next_table_id()?, page.get_catalog_page_no()?)
            }
            Err(_) => {
                // If the first page doesn't exist, create it as a start page
                if b_p.total_pages_in_disk()? > 0 {
                    return Err(CustomError::Err_from_wrong_arg("The first page is missing or corrupted, but other pages exist".to_string()));
                }
                b_p.create_page(PageType::StartPage)?;
                let mut start_page = b_p.fetch_page_mut(0)?;
                start_page.set_next_table_id(0)?;
                start_page.set_catalog_page_no(u32::MAX)?;
                (0, u32::MAX)
            }
        };
        let mut c_m = CatalogManager::new(next_table_id);
        while catalog_page_no != u32::MAX {
            let catalog_page = b_p.fetch_page(catalog_page_no)?;
            let mut record_count = catalog_page.get_record_count();
            while record_count > 0 {
                // Process each record in the catalog page
                let record = catalog_page.read_record(record_count - 1)?;
                let table_id = u32::from_be_bytes(record[0..4].try_into()?);
                let table_start_page = u32::from_be_bytes(record[4..8].try_into()?);
                let table_name_size = u16::from_be_bytes(record[8..10].try_into()?);
                let table_name = String::from_utf8(record[10..(10 + table_name_size as usize)].to_vec())
                    .map_err(|_| CustomError::Err_from_wrong_arg("Invalid UTF-8 in table name".to_string()))?;
                let table_metadata = TableMetadata::new(crate::catalog::table::TableId::new(table_id), table_start_page, table_name);
                c_m.add_table(table_metadata)?;
                record_count -= 1;
                
            }
            let unpin_page_no = catalog_page.get_page_no(); 
            catalog_page_no = catalog_page.get_next_page_no();
            b_p.unpin(unpin_page_no)?;
        }

        b_p.unpin(0)?;
        b_p.flush()?;
        
        Ok(Database {
            catalog_manager: c_m,
            buffer_pool: b_p,
        })
    }

    // TODO: Implement methods for creating tables, inserting records, querying records, etc.

    pub fn craete_table(&mut self, table_name: String) -> Result<TableId> {
        let start_page_no = self.buffer_pool.create_page(PageType::DataPage)?.get_page_no();
        let table_name_bytes = table_name.as_bytes().to_vec();
        let table_name_size = table_name_bytes.len() as u16;
        let table_id = self.catalog_manager.create_table(start_page_no, table_name)?;
        self.buffer_pool.unpin(start_page_no)?;

        self.buffer_pool
            .fetch_page_mut(0)?
            .set_next_table_id(table_id.id() + 1)?;
        self.buffer_pool.unpin(0)?;

        let mut catalog_page_no = {
            let db_start_page = self.buffer_pool.fetch_page(0)?;
            let catalog_page_no = db_start_page.get_catalog_page_no()?;
            self.buffer_pool.unpin(0)?;
            catalog_page_no
        };

        if catalog_page_no == u32::MAX {
            let new_catalog_page_no = self
                .buffer_pool
                .create_page(PageType::CatalogPage)?
                .get_page_no();
            self.buffer_pool
                .fetch_page_mut(0)?
                .set_catalog_page_no(new_catalog_page_no)?;
            self.buffer_pool.unpin(0)?;
            catalog_page_no = new_catalog_page_no;
        }

        let mut page_data_to_insert = Vec::new();
        page_data_to_insert.extend_from_slice(&table_id.id().to_be_bytes());
        page_data_to_insert.extend_from_slice(&start_page_no.to_be_bytes());
        page_data_to_insert.extend_from_slice(&table_name_size.to_be_bytes());
        page_data_to_insert.extend_from_slice(&table_name_bytes);

        while match self.buffer_pool.fetch_page_mut(catalog_page_no)?.insert_into_page(&page_data_to_insert) {Ok(_) => false,
        Err(_) => true,} {
            let unpin_page_no = catalog_page_no;
            let next_page_no = self.buffer_pool.fetch_page(catalog_page_no)?.get_next_page_no();
            catalog_page_no = if next_page_no != u32::MAX {
                next_page_no
            } else {
                let new_catalog_page = self.buffer_pool.create_page(PageType::CatalogPage)?;
                let new_catalog_page_no = new_catalog_page.get_page_no();
                self.buffer_pool.fetch_page_mut(unpin_page_no)?.set_next_page_no(new_catalog_page_no);
                new_catalog_page_no
            };
            self.buffer_pool.unpin(unpin_page_no)?;
        }
        self.buffer_pool.unpin(catalog_page_no)?;
        Ok(table_id)

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


