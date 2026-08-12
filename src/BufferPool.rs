use crate::page::{Page, PAGE_SIZE};
use crate::diskManager::DiskManager;
use std::collections::{HashMap, HashSet};
use crate::customErrors::{CustomError, Result};

pub struct BufferPool {
    dm: DiskManager,
    page_table: HashMap<u32, Page>,
    dirty_pages: HashSet<u32>,
}

impl BufferPool {
    pub fn new(file_name: &str) -> Result<BufferPool> {
        let disk_manager = match DiskManager::open_db(file_name) {
            Ok(dm) => dm,
            Err(_) => match DiskManager::new_db(file_name) {
                Ok(dm) => dm,
                Err(e) => return Err(CustomError::Err_from_wrong_arg(format!("Error creating or opening database: {}", e))),
            },
        };
        Ok(BufferPool {
            dm: disk_manager,
            page_table: HashMap::new(),
            dirty_pages: HashSet::new(),
        })
    }

    pub fn fetch_page(&mut self, page_no: u32) -> Result<&Page> {
        if !self.page_table.contains_key(&page_no) {
            let page = self.dm.read_page(page_no)?;
            self.page_table.insert(page_no, page);
        }
        Ok(self.page_table.get(&page_no).unwrap())
    }

    pub fn fetch_page_mut(&mut self, page_no: u32) -> Result<&mut Page> {
        if !self.page_table.contains_key(&page_no) {
            let page = self.dm.read_page(page_no)?;
            self.page_table.insert(page_no, page);
        }
        self.dirty_pages.insert(page_no);
        Ok(self.page_table.get_mut(&page_no).unwrap())
    }

    pub fn flush(&mut self) -> Result<()> {
        for page_no in &self.dirty_pages {
            let page = self.page_table.get(page_no).unwrap();
            self.dm.write_page(*page_no, &page.data)?;
        }
        self.dirty_pages.clear();
        Ok(())
    }
}

