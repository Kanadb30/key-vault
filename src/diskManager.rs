// implementing a basic disk manager with fuctions such as:
// - opening a file
// - read a page
// - write to a page

use std::fs::{File, OpenOptions};
use std::io::{Read, Seek, SeekFrom, Write};

struct DiskManager {
    file: File,                        // db file -> openend instance.
}

impl DiskManager {

    fn new_db(file_name: &str) -> Result<DiskManager> {
        let file_to_create = format!("{}.db", file_name);
        let file = match OpenOptions::new().read(true).write(true).create(true).open(&file_to_create){
            Ok(file) => file,
            Err(e) => return Err(CustomError::Err_from_wrong_arg(format!("Error creating file: {}", e)))
        };
        Ok(DiskManager { file })
    }

    fn open_db(file_name: &str) -> Result<DiskManager>{
        let file_to_open = format!("{}.db", file_name);
        let file = match OpenOptions::new().read(true).write(true).open(&file_to_open){
            Ok(file) => file,
            Err(e) => return Err(CustomError::Err_from_wrong_arg(format!("Error opening file: {}", e)))
        };
        Ok(DiskManager { file })
    }
    // Loads whole page, creates a page object and returns it.
    fn read_page(&mut self, page_no: u64) -> Result<Page> {
        if page_no * PAGE_SIZE as u64 >= self.file.metadata()?.len() {
            return Err(CustomError::Err_from_wrong_arg("Page number exceeds file size".to_string()));
        }else{
            let mut buffer = [0; PAGE_SIZE];
            self.file.seek(SeekFrom::Start(page_no * PAGE_SIZE as u64))?;
            self.file.read_exact(&mut buffer)?;
            let page = Page::create(page_no, buffer);
            Ok(page)
        }
    }

    fn create_page(&mut self) -> Result<Page> {
        let page_no = self.file.metadata()?.len() / PAGE_SIZE as u64;
        let buffer = [0; PAGE_SIZE];
        self.file.seek(SeekFrom::Start(page_no * PAGE_SIZE as u64))?;
        self.file.write_all(&buffer)?;
        let page = Page::create(page_no, buffer);
        Ok(page)
    }

    fn write_page(&mut self, page_no: u64, data: &[u8; PAGE_SIZE]) -> Result<()> {
        if page_no * PAGE_SIZE as u64 >= self.file.metadata()?.len() {
            return Err(CustomError::Err_from_wrong_arg("Page number exceeds file size".to_string()));
        }else{
            self.file.seek(SeekFrom::Start(page_no * PAGE_SIZE as u64))?;
            self.file.write_all(data)?;
            Ok(())
        }
    }

    fn total_pages(&self) -> Result<u64> {
        let total_pages = self.file.metadata()?.len() / PAGE_SIZE as u64;
        Ok(total_pages)
    }
}

