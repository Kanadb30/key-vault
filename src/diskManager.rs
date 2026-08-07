// implementing a basic disk manager with fuctions such as:
// - opening a file
// - read a page
// - write to a page

use std::fs::{File, OpenOptions};
use std::io::{Read, Seek, SeekFrom, Write};
use std::collections::HashMap as Map;

struct DiskManager {
    file: File,
    AvailablePageMap : Map<u64, Page>, // mapping of page number to page object.
}

impl DiskManager {

    fn open_file(file_name: &str) -> Result<DiskManager>{
        let file_to_open = format!("{}.db", file_name);
        let file = match OpenOptions::new().read(true).write(true).open(&file_to_open){
            Ok(file) => file,
            Err(e) => return Err(format!("Error opening file: {}", e))
        };
        Ok(DiskManager { file })
    }

    fn read_page(&mut self, page_no: u64) -> Result<Page> {
        if page_no * PAGE_SIZE as u64 > self.file.metadata()?.len() {
            return Err("Page number exceeds file size".to_string());
        }else{
            if self.AvailablePage
            let mut buffer = [0; PAGE_SIZE];
            self.file.seek(SeekFrom::Start(page_no * PAGE_SIZE as u64))?;
            self.file.read_exact(&mut buffer)?;
            let page = Page::create(page_no, buffer);
            self.AvailablePageMap.insert(page_no, page);
            Ok(page)
        }
    }

    fn write_page(&mut self, page_no: u64, data: &[u8; PAGE_SIZE]) -> Result<()> {
        if page_no * PAGE_SIZE as u64 > self.file.metadata()?.len() {
            return Err("Page number exceeds file size".to_string());
        }else{
            self.file.seek(SeekFrom::Start(page_no * PAGE_SIZE as u64));
            self.file.write_all(data)?;
            Ok(())
        }
    }
}

