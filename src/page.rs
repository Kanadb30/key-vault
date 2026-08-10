

// Okay so implemented a page here for my db.
// but i think it has many improvements to consider:
// 1) write page does not support writting at a specific offset.
// 2) write page only excepts a vec for now.
// 3) multiple conversions as usize -- > need to search for its fix. {feeling lazy to do it now}.




pub const PAGE_SIZE: usize = 4096;

pub const HEADER_WITHOUT_PAGE_NO: [u8; 4] = [0, 8, 0, 0];


struct Page{
    page_no: u32,
    data_end: u16,                           // till where data is written
    record_count: u16,                        // how many records are there in this page
    data: [u8; PAGE_SIZE],
}

impl Page {
    fn new(page_no: u64) -> Page {
        let mut data = [0u8; PAGE_SIZE];

        data[0..4].copy_from_slice(&page_no.to_be_bytes());
        data[4..8].copy_from_slice(&HEADER_WITHOUT_PAGE_NO);

        Page {
            page_no,
            data_end: 8,
            record_count: 0,
            data: data,
        }
    }

    //creating page instance from data read from disk.

    fn create(data: [u8; PAGE_SIZE]) -> Result<Page> {
        Page {
            page_no: u32::from_be_bytes(data[0..4].try_into()?),
            data_end: u16::from_be_bytes(data[4..6].try_into()?),
            record_count: u16::from_be_bytes(data[6..8].try_into()?),
            data
        }
    }

    fn read_record(&self, offset: usize, read_size: usize) -> Result<&[u8]> {
        if offset + read_size > self.data_end as usize {
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


