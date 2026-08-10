

// Okay so implemented a page here for my db.
// but i think it has many improvements to consider:
// 1) write page does not support writting at a specific offset.
// 2) write page only excepts a vec for now.
// 3) multiple conversions as usize -- > need to search for its fix. {feeling lazy to do it now}.




pub const PAGE_SIZE: usize = 4096;


struct Page{
    page_no: u64,
    offset : usize,                            // till where data is written
    data: [u8; PAGE_SIZE],
}

impl Page {
    fn new(page_no: u64) -> Page {
        Page {
            page_no,
            offset: 0,
            data: [0; PAGE_SIZE]
        }
    }

    fn create(page_no: u64, data: [u8; PAGE_SIZE]) -> Page {
        Page {
            page_no,
            offset: PAGE_SIZE, // assuming the data is filled to the end of the page -> need to change this later. 
            data
        }
    }

    fn read_page(&self, offset: usize, read_size: usize) -> Result<&[u8]> {
        if offset + read_size > self.offset {
            return Err(CustomError::Err_from_wrong_arg("Read exceeds page size".to_string()));
        }
        Ok(&self.data[offset..(offset + read_size)])
    }

    // currently keeping it append only. Easy to handle.
    // can change to write at specific offset later. => that will have fragmentation issues.

    fn write_page(&mut self, data: &[u8]) -> Result<()> {           
        if data.len() + self.offset > PAGE_SIZE {
            Err(CustomError::Err_from_wrong_arg("Write exceeds page size".to_string()))
        } else {
            self.data[self.offset..(self.offset + data.len())].copy_from_slice(&data);
            self.offset = self.offset + data.len();
            Ok(())
        }
    }
}


