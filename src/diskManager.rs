// implementing a basic disk manager with fuctions such as:
// - opening a file
// - read a page
// - write to a page
use crate::customErrors::CustomError;
use crate::customErrors::Result;
use crate::page::{PAGE_SIZE, Page};
use std::fs::{File, OpenOptions};
use std::io::{Read, Seek, SeekFrom, Write};

pub struct DiskManager {
    file: File,                        // db file -> openend instance.
}

impl DiskManager {

    pub fn new_db(file_name: &str) -> Result<DiskManager> {
        let file_to_create = format!("{}.db", file_name);
        let file = match OpenOptions::new().read(true).write(true).create(true).open(&file_to_create){
            Ok(file) => file,
            Err(e) => return Err(CustomError::Err_from_wrong_arg(format!("Error creating file: {}", e)))
        };
        Ok(DiskManager { file })
    }

    pub fn open_db(file_name: &str) -> Result<DiskManager>{
        let file_to_open = format!("{}.db", file_name);
        let file = match OpenOptions::new().read(true).write(true).open(&file_to_open){
            Ok(file) => file,
            Err(e) => return Err(CustomError::Err_from_wrong_arg(format!("Error opening file: {}", e)))
        };
        Ok(DiskManager { file })
    }
    // Loads whole page, creates a page object and returns it.
    pub fn read_page(&mut self, page_no: u32) -> Result<Page> {
        if page_no * PAGE_SIZE as u32 >= self.file.metadata()?.len() as u32 {
            return Err(CustomError::Err_from_wrong_arg("Page number exceeds file size".to_string()));
        }else{
            let mut buffer = [0; PAGE_SIZE];
            self.file.seek(SeekFrom::Start((page_no * PAGE_SIZE as u32).into()))?;
            self.file.read_exact(&mut buffer)?;
            let page = Page::create(buffer)?;
            Ok(page)
        }
    }

    pub fn create_page(&mut self) -> Result<Page> {
        let page_no = self.file.metadata()?.len() / PAGE_SIZE as u64;
        self.file.seek(SeekFrom::Start(page_no * PAGE_SIZE as u64))?;
        let page = Page::new(page_no as u32);
        self.file.write_all(&page.data)?;
        Ok(page)
    }

    pub fn write_page(&mut self, page_no: u32, data: &[u8; PAGE_SIZE]) -> Result<()> {
        if page_no * PAGE_SIZE as u32 >= self.file.metadata()?.len() as u32 {
            return Err(CustomError::Err_from_wrong_arg("Page number exceeds file size".to_string()));
        }else{
            self.file.seek(SeekFrom::Start((page_no * PAGE_SIZE as u32).into()))?;
            self.file.write_all(data)?;
            Ok(())
        }
    }

    pub fn total_pages(&self) -> Result<u64> {
        let total_pages = self.file.metadata()?.len() / PAGE_SIZE as u64;
        Ok(total_pages)
    }
}

