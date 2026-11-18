use crate::error::{CustomError, Result};
use crate::storage::page::{PAGE_SIZE, Page, PageType};
use std::fs::{File, OpenOptions};
use std::io::{Read, Seek, SeekFrom, Write};

pub struct DiskManager {
    file: File,
}

impl DiskManager {
    /// Paths are explicit; no hidden .db suffix or CWD-relative bridge paths.
    pub fn new_db(path: &str) -> Result<Self> {
        let file = OpenOptions::new()
            .read(true)
            .write(true)
            .create_new(true)
            .open(path)?;
        Ok(Self { file })
    }
    pub fn open_db(path: &str) -> Result<Self> {
        let file = OpenOptions::new().read(true).write(true).open(path)?;
        if file.metadata()?.len() % PAGE_SIZE as u64 != 0 {
            return Err(CustomError::Corrupt("truncated final page".into()));
        }
        Ok(Self { file })
    }
    pub fn read_page(&mut self, page_no: u32) -> Result<Page> {
        if page_no as u64 >= self.total_pages()? {
            return Err(CustomError::Corrupt("page number exceeds file size".into()));
        }
        let mut data = [0; PAGE_SIZE];
        self.file
            .seek(SeekFrom::Start(page_no as u64 * PAGE_SIZE as u64))?;
        self.file.read_exact(&mut data)?;
        let page = Page::create(data)?;
        if page.get_page_no() != page_no
            || (page.get_next_page_no() != u32::MAX
                && page.get_next_page_no() as u64 >= self.total_pages()?)
        {
            return Err(CustomError::Corrupt(
                "page number or next-page pointer invalid".into(),
            ));
        }
        Ok(page)
    }
    pub fn create_page(&mut self, kind: PageType) -> Result<Page> {
        let no = u32::try_from(self.total_pages()?)
            .map_err(|_| CustomError::Corrupt("too many pages".into()))?;
        let page = Page::new(no, kind);
        self.file.seek(SeekFrom::End(0))?;
        self.file.write_all(&page.data)?;
        Ok(page)
    }
    pub fn write_page(&mut self, no: u32, data: &[u8; PAGE_SIZE]) -> Result<()> {
        if no as u64 >= self.total_pages()? {
            return Err(CustomError::Corrupt("write beyond EOF".into()));
        }
        self.file
            .seek(SeekFrom::Start(no as u64 * PAGE_SIZE as u64))?;
        self.file.write_all(data)?;
        Ok(())
    }
    pub fn total_pages(&self) -> Result<u64> {
        Ok(self.file.metadata()?.len() / PAGE_SIZE as u64)
    }
    pub fn sync(&self) -> Result<()> {
        self.file.sync_all()?;
        Ok(())
    }
}
