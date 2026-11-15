use crate::error::{CustomError, Result};
use crate::storage::disk_manager::DiskManager;
use crate::storage::page::{Page, PageType};
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
            Err(CustomError::IoError(e)) if e.kind() == std::io::ErrorKind::NotFound => {
                DiskManager::new_db(file_name)?
            }
            Err(e) => return Err(e),
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
            self.make_room()?;
            let page = self.dm.read_page(page_no)?;
            self.page_table.insert(page_no, page);
            self.pin(page_no)?;
            self.lru.push_front(page_no);
            self.evict()?;
            return Ok(self.page_table.get(&page_no).unwrap());
        } else {
            self.pin(page_no)?;
            self.lru
                .retain(|&existing_page_no| existing_page_no != page_no);
            self.lru.push_front(page_no);
            self.evict()?;
            return Ok(self.page_table.get(&page_no).unwrap());
        }
    }

    pub fn fetch_page_mut(&mut self, page_no: u32) -> Result<&mut Page> {
        if !self.page_table.contains_key(&page_no) {
            self.make_room()?;
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
            self.lru
                .retain(|&existing_page_no| existing_page_no != page_no);
            self.lru.push_front(page_no);
            self.evict()?;
            return Ok(self.page_table.get_mut(&page_no).unwrap());
        }
    }

    pub fn create_page(&mut self, page_type: PageType) -> Result<&Page> {
        self.make_room()?;
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
        self.dm.sync()?;
        Ok(())
    }

    fn evict(&mut self) -> Result<()> {
        if self.lru.len() > self.capacity {
            // Pop from the LRU end until an unpinned page is found.
            // Pinned pages encountered are recorded so they can be restored
            // in their original LRU order, on both the success and error paths.
            let mut pinned_seen: Vec<u32> = Vec::new();
            let victim: Option<u32> = loop {
                match self.lru.pop_back() {
                    None => break None,
                    Some(page_no) => {
                        if self.pins.get(&page_no).copied().unwrap_or(0) != 0 {
                            pinned_seen.push(page_no);
                        } else {
                            break Some(page_no);
                        }
                    }
                }
            };
            // pinned_seen[0] was popped first, i.e. it sat closest to the LRU
            // end; pushing back in scan order preserves the original ordering.
            for page_no in pinned_seen.iter().rev() {
                self.lru.push_back(*page_no);
            }
            let pop_page_no = match victim {
                Some(page_no) => page_no,
                None => {
                    return Err(CustomError::Err_from_wrong_arg(
                        "Buffer pool has no unpinned pages, cannot evict any page".to_string(),
                    ));
                }
            };
            if self.dirty_pages.contains(&pop_page_no) {
                let page = self.page_table.get(&pop_page_no).unwrap();
                self.dm.write_page(pop_page_no, &page.data)?;
                self.dirty_pages.remove(&pop_page_no);
            }
            self.page_table.remove(&pop_page_no);
            self.pins.remove(&pop_page_no);
        }
        Ok(())
    }

    fn pin(&mut self, page_no: u32) -> Result<()> {
        if !self.page_table.contains_key(&page_no) {
            return Err(CustomError::Err_from_wrong_arg(format!(
                "Page {} not found in buffer pool",
                page_no
            )));
        }
        let count = self.pins.entry(page_no).or_insert(0);
        *count += 1;
        Ok(())
    }

    pub fn unpin(&mut self, page_no: u32) -> Result<()> {
        if !self.page_table.contains_key(&page_no) {
            return Err(CustomError::Err_from_wrong_arg(format!(
                "Page {} not found in buffer pool",
                page_no
            )));
        }
        if let Some(count) = self.pins.get_mut(&page_no) {
            if *count > 0 {
                *count -= 1;
            } else {
                return Err(CustomError::Err_from_wrong_arg(format!(
                    "Page {} is not pinned",
                    page_no
                )));
            }
        }
        Ok(())
    }

    pub fn total_pages_in_disk(&self) -> Result<u64> {
        self.dm.total_pages()
    }

    pub fn page_count(&self) -> usize {
        self.page_table.len()
    }

    pub fn guard(&mut self, page_no: u32) -> Result<PageGuard<'_>> {
        self.fetch_page(page_no)?;
        Ok(PageGuard {
            pool: self,
            page_no,
        })
    }

    fn make_room(&mut self) -> Result<()> {
        if self.page_table.len() >= self.capacity {
            self.capacity -= 1;
            let result = self.evict();
            self.capacity += 1;
            result?;
        }
        Ok(())
    }

    pub fn allocate(&mut self, kind: PageType) -> Result<u32> {
        let no = self.create_page(kind)?.get_page_no();
        self.unpin(no)?;
        Ok(no)
    }
}

/// Pins exactly one page, unpins on every success/error return path.
pub struct PageGuard<'a> {
    pool: &'a mut BufferPool,
    page_no: u32,
}
impl PageGuard<'_> {
    pub fn page(&self) -> &Page {
        &self.pool.page_table[&self.page_no]
    }
    pub fn page_mut(&mut self) -> &mut Page {
        self.pool.dirty_pages.insert(self.page_no);
        self.pool
            .page_table
            .get_mut(&self.page_no)
            .expect("guard owns a pin")
    }
}
impl Drop for PageGuard<'_> {
    fn drop(&mut self) {
        let _ = self.pool.unpin(self.page_no);
    }
}
