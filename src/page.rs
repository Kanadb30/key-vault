

// Okay so implemented a page here for my db.
// but i think it has many improvements to consider:
// 1) write page does not support writting at a specific offset.
// 2) write page only excepts a vec for now.
// 3) multiple conversions as usize -- > need to search for its fix. {feeling lazy to do it now}.




pub const PAGE_SIZE: u64 = 4096;


struct Page{
    page_no: u64,
    offset : u64,                            // till where data is written
    data: [u8; PAGE_SIZE as usize],
}

impl Page {
    fn new(page_no: u64) -> Page {
        Page {
            page_no,
            offset: 0,
            data: [0; PAGE_SIZE as usize]
        }
    }

    fn read_page(&self, offset: u64, read_size: u64) -> Result<Vec<u8>, String> {
        if offset + read_size > self.offset as u64 {
            Err("Read exceeds page size".to_string())
        }
        Ok(self.data[offset as usize..(offset + read_size) as usize].to_vec())
    }

    fn write_page(&mut self, data: &Vec<u8>) -> Result<(), String> {
        if data.len() + self.offset > PAGE_SIZE as usize {
            Err("Write exceeds page size".to_string())
        } else {
            self.data[self.offset as usize..(self.offset + data.len() as u64) as usize].copy_from_slice(&data);
            self.offset += data.len() as u64;
            Ok(())
        }
    }
}


