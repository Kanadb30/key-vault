use crate::error::{CustomError, Result};

pub const PAGE_SIZE: usize = 4096;
pub const PAGE_HEADER_SIZE: usize = 14;
pub const HEADER_WITHOUT_PAGE_NO_AND_TYPE: [u8; 4] = [0, 14, 0, 0];

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum PageType {
    StartPage = 0,
    DataPage = 1,
    CatalogPage = 2,
}

impl PageType {
    pub fn from_u16(value: u16) -> Result<PageType> {
        match value {
            0 => Ok(PageType::StartPage),
            1 => Ok(PageType::DataPage),
            2 => Ok(PageType::CatalogPage),
            _ => Err(CustomError::Err_from_wrong_arg(format!("Invalid page type: {}", value)))
        }
    }
}

pub struct Page {
    page_no: u32,
    page_type: PageType,
    data_end: u16,
    record_count: u16,
    next_page_no: u32,
    pub data: [u8; PAGE_SIZE],
}

impl Page {
    pub fn new(page_no: u32, page_type: PageType) -> Page {
        let mut data = [0u8; PAGE_SIZE];

        data[0..4].copy_from_slice(&page_no.to_be_bytes());
        data[4..6].copy_from_slice(&(page_type as u16).to_be_bytes());
        data[6..10].copy_from_slice(&HEADER_WITHOUT_PAGE_NO_AND_TYPE);
        data[10..14].copy_from_slice(&u32::MAX.to_be_bytes());

        Page {
            page_no,
            page_type,
            data_end: PAGE_HEADER_SIZE as u16,
            record_count: 0,
            next_page_no: u32::MAX,
            data,
        }
    }

    pub fn create(data: [u8; PAGE_SIZE]) -> Result<Page> {
        Ok(Page {
            page_no: u32::from_be_bytes(data[0..4].try_into()?),
            page_type: PageType::from_u16(u16::from_be_bytes(data[4..6].try_into()?))?,
            data_end: u16::from_be_bytes(data[6..8].try_into()?),
            record_count: u16::from_be_bytes(data[8..10].try_into()?),
            next_page_no: u32::from_be_bytes(data[10..14].try_into()?),
            data,
        })
 }
    // IMP => 
    /// Implementation details:
    /// If it's a catalog page, provide table_id, table_start_page, table_name_size and table_name as a record: [u8].
    /// Otherwise, provide just the record for a data page, and the length will be added automatically.

    pub fn insert_into_page(&mut self, record: &[u8]) -> Result<()> {
        if self.page_type == PageType::DataPage {
            return self.insert_record_data(record);
        }else if self.page_type == PageType::StartPage {
            return Err(CustomError::Err_from_wrong_arg("Cannot insert record into a start page".to_string()));
        }else if self.page_type == PageType::CatalogPage {
            if self.data_end as usize + record.len() > PAGE_SIZE {
                return Err(CustomError::Err_from_wrong_arg("Record exceeds page size".to_string()));
            } else {
                self.data[self.data_end as usize..self.data_end as usize + record.len()].copy_from_slice(record);
                self.data_end += record.len() as u16;
                self.record_count += 1;
                self.data[6..8].copy_from_slice(&self.data_end.to_be_bytes());
                self.data[8..10].copy_from_slice(&self.record_count.to_be_bytes());
            }
        }
        Ok(())
    }

    fn insert_record_data(&mut self, record: &[u8]) -> Result<()> {
        if self.data_end as usize + record.len() + 2 > PAGE_SIZE {
            return Err(CustomError::Err_from_wrong_arg("Record exceeds page size".to_string()));
        }
        self.data[self.data_end as usize..self.data_end as usize + 2].copy_from_slice(&(record.len() as u16).to_be_bytes());
        self.data_end += 2;
        self.data[self.data_end as usize..(self.data_end as usize + record.len())].copy_from_slice(record);
        self.data_end += record.len() as u16;
        self.record_count += 1;
        self.data[6..8].copy_from_slice(&self.data_end.to_be_bytes());
        self.data[8..10].copy_from_slice(&self.record_count.to_be_bytes());
        Ok(())
    }

    // IMP => 
    // if page = catalog -> return = table_id, table_start_page, table_name_size, table_name as record: [u8]
    // else -> return record for data page, length will be removed automatically

    pub fn read_record(&self, record_no: u16) -> Result<&[u8]> {
        if record_no >= self.record_count {
            return Err(CustomError::Err_from_wrong_arg("Record no. exceeds record count".to_string()));
        }
        let mut offset = PAGE_HEADER_SIZE;
        if self.page_type == PageType::StartPage {
            return Err(CustomError::Err_from_wrong_arg("Cannot read record from a start page".to_string()));
        } else if self.page_type == PageType::DataPage {
            for _ in 0..record_no {
                let record_length = u16::from_be_bytes(self.data[offset..offset + 2].try_into()?);
                offset += 2 + record_length as usize;
            }
            let record_length = u16::from_be_bytes(self.data[offset..offset + 2].try_into()?);
            return Ok(&self.data[offset + 2..offset + 2 + record_length as usize]);
        } else if self.page_type == PageType::CatalogPage {
            for _ in 0..record_no {
                let table_name_length = u16::from_be_bytes(self.data[offset+8..offset + 10].try_into()?);
                offset += 10 + table_name_length as usize;
            }
            let table_name_length = u16::from_be_bytes(self.data[offset+8..offset + 10].try_into()?);
            return Ok(&self.data[offset..offset + 10 + table_name_length as usize]);
        }

        Err(CustomError::Err_from_wrong_arg("Invalid page type".to_string()))
    }

    pub fn get_page_no(&self) -> u32 {
        self.page_no
    }

    pub fn get_page_type(&self) -> &PageType {
        &self.page_type
    }

    pub fn get_data_end(&self) -> u16 {
        self.data_end
    }

    pub fn get_record_count(&self) -> u16 {
        self.record_count
    }

    pub fn get_next_page_no(&self) -> u32 {
        self.next_page_no
    }

    pub fn set_next_page_no(&mut self, next_page_no: u32) {
        self.next_page_no = next_page_no;
        self.data[10..14].copy_from_slice(&next_page_no.to_be_bytes());
    }
}
