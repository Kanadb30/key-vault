
use crate::customErrors::CustomError;
use crate::customErrors::Result;

pub const PAGE_SIZE: usize = 4096;

pub const HEADER_WITHOUT_PAGE_NO: [u8; 4] = [0, 8, 0, 0];

// Making struct fields pub for now to test will convert them again soon. 
pub struct Page{
    pub page_no: u32,
    pub data_end: u16,                    
    pub record_count: u16,                    
    pub data: [u8; PAGE_SIZE],
}

impl Page {
    pub fn new(page_no: u32) -> Page {
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


    pub fn create(data: [u8; PAGE_SIZE]) -> Result<Page> {
        Ok(Page {
            page_no: u32::from_be_bytes(data[0..4].try_into()?),
            data_end: u16::from_be_bytes(data[4..6].try_into()?),
            record_count: u16::from_be_bytes(data[6..8].try_into()?),
            data
        })
    }

    pub fn insert_record(&mut self, record: &[u8]) -> Result<()> {
        if self.data_end as usize + record.len() + 2 > PAGE_SIZE {
            return Err(CustomError::Err_from_wrong_arg("Record exceeds page size".to_string()));
        }
        self.data[self.data_end as usize..self.data_end as usize + 2].copy_from_slice(&(record.len() as u16).to_be_bytes());
        self.data_end += 2;
        self.data[self.data_end as usize..(self.data_end as usize + record.len())].copy_from_slice(&record);
        self.data_end += record.len() as u16;
        self.record_count += 1;
        self.data[4..6].copy_from_slice(&self.data_end.to_be_bytes());
        self.data[6..8].copy_from_slice(&self.record_count.to_be_bytes());
        Ok(())        
    }

    pub fn read_record(&self, record_no: u16) -> Result<&[u8]> {
        if record_no >= self.record_count {
            return Err(CustomError::Err_from_wrong_arg("Record no. exceeds record count".to_string()));
        }
        let mut offset: usize = 8;
        for _ in 1..record_no{
            offset += self.data[offset..offset + 2].try_into().map(u16::from_be_bytes)? as usize;
            offset += 2;
        }
        let number_of_bytes: u16 = self.data[offset..offset + 2].try_into().map(u16::from_be_bytes)?;
        Ok(&self.data[offset + 2..offset + 2 + number_of_bytes as usize])
        
    }
}


