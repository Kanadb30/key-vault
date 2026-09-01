use crate::error::{CustomError, Result};
use crate::storage::disk_manager::DiskManager;
use crate::storage::page::{Page, PAGE_SIZE, PageType};
use std::collections::{HashMap, HashSet, VecDeque};

pub const BUFFER_POOL_CAPACITY: usize = 5;

pub struct BufferPool {
    dm: DiskManager,
    page_table: HashMap<u32, Page>,
    dirty_pages: HashSet<u32>,
    capacity: usize,
    lru: VecDeque<u32>,
    pins: HashMap<u32, u32>,
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
            capacity: BUFFER_POOL_CAPACITY,
            lru: VecDeque::new(),
            pins: HashMap::new(),
        })
    }

    pub fn fetch_page(&mut self, page_no: u32) -> Result<&Page> {
        if !self.page_table.contains_key(&page_no) { 
            let page = self.dm.read_page(page_no)?;
            self.page_table.insert(page_no, page);
            self.pin(page_no)?;
            self.lru.push_front(page_no);
            self.evict()?;
            return Ok(self.page_table.get(&page_no).unwrap());
        } else {
            self.pin(page_no)?;
            self.lru.retain(|&existing_page_no| existing_page_no != page_no);
            self.lru.push_front(page_no);
            self.evict()?;
            return Ok(self.page_table.get(&page_no).unwrap());
        }
    }

    pub fn fetch_page_mut(&mut self, page_no: u32) -> Result<&mut Page> {
        if !self.page_table.contains_key(&page_no) {
            let page = self.dm.read_page(page_no)?;
            self.page_table.insert(page_no, page);
            self.pin(page_no)?;
            self.dirty_pages.insert(page_no);
            self.lru.push_front(page_no);
            self.evict()?;
            return Ok(self.page_table.get_mut(&page_no).unwrap());
        } else {
            self.pin(page_no)?;
            self.dirty_pages.insert(page_no);
            self.lru.retain(|&existing_page_no| existing_page_no != page_no);
            self.lru.push_front(page_no);
            self.evict()?;
            return Ok(self.page_table.get_mut(&page_no).unwrap());
        }
    }

    pub fn create_page(&mut self, page_type: PageType) -> Result<&Page> {
        let page = self.dm.create_page(page_type)?;
        let page_no = page.get_page_no();
        self.page_table.insert(page_no, page);
        self.pin(page_no)?;
        self.lru.push_front(page_no);
        self.evict()?;
        return Ok(self.page_table.get(&page_no).unwrap());
    }

    pub fn flush(&mut self) -> Result<()> {
        for page_no in &self.dirty_pages {
            let page = self.page_table.get(page_no).unwrap();
            self.dm.write_page(*page_no, &page.data)?;
        }
        self.dirty_pages.clear();
        Ok(())
    }

    fn evict(&mut self) -> Result<()> {
        if self.lru.len() > self.capacity {
            let mut stack = Vec::new();
            let mut pop_page_no: u32 = 0;
            while true {
                if self.lru.len() == 0 {
                    return Err(CustomError::Err_from_wrong_arg("Buffer pool has no unpinned pages, cannot evict any page".to_string()));
                }
                pop_page_no = self.lru.pop_back().unwrap();
                if self.pins.get(&pop_page_no).unwrap_or(&0) != &0 {
                    stack.push(pop_page_no);
                } else {
                    break;
                }
            }
            while !stack.is_empty() {
                self.lru.push_back(stack.pop().unwrap());
            }
            if self.dirty_pages.contains(&pop_page_no) {
                let page = self.page_table.get(&pop_page_no).unwrap();
                self.dm.write_page(pop_page_no, &page.data)?;
                self.dirty_pages.remove(&pop_page_no);
            }
            self.page_table.remove(&pop_page_no);
        }
        Ok(())
    }

    fn pin(&mut self, page_no: u32) -> Result<()> {
        if !self.page_table.contains_key(&page_no) {
            return Err(CustomError::Err_from_wrong_arg(format!("Page {} not found in buffer pool", page_no)));
        }
        let mut count = self.pins.entry(page_no).or_insert(0);
        *count += 1;
        Ok(())
    }

    pub fn unpin(&mut self, page_no: u32) -> Result<()> {
        if !self.page_table.contains_key(&page_no) {
            return Err(CustomError::Err_from_wrong_arg(format!("Page {} not found in buffer pool", page_no)));
        }
        if let Some(count) = self.pins.get_mut(&page_no) {
            if *count > 0 {
                *count -= 1;
            } else {
                return Err(CustomError::Err_from_wrong_arg(format!("Page {} is not pinned", page_no)));
            }
        }
        Ok(())
    }

    pub fn total_pages_in_disk(&self) -> Result<u64> {
        self.dm.total_pages()
    }
}
