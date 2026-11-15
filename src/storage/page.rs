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
            _ => Err(CustomError::Corrupt(format!(
                "Invalid page type: {}",
                value
            ))),
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

        if page_type == PageType::StartPage {
            data[14..18].copy_from_slice(&0u32.to_be_bytes());
            data[18..22].copy_from_slice(&u32::MAX.to_be_bytes());
            data[22..26].copy_from_slice(b"KBDB");
            data[26..30].copy_from_slice(&1u32.to_be_bytes());
        }

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
        let page = Page {
            page_no: u32::from_be_bytes(data[0..4].try_into()?),
            page_type: PageType::from_u16(u16::from_be_bytes(data[4..6].try_into()?))?,
            data_end: u16::from_be_bytes(data[6..8].try_into()?),
            record_count: u16::from_be_bytes(data[8..10].try_into()?),
            next_page_no: u32::from_be_bytes(data[10..14].try_into()?),
            data,
        };
        if page.data_end as usize > PAGE_SIZE || page.data_end < PAGE_HEADER_SIZE as u16 {
            return Err(CustomError::Corrupt("invalid data_end".into()));
        }
        if page.page_type == PageType::StartPage {
            if page.record_count != 0 || page.data_end != 14 {
                return Err(CustomError::Corrupt(
                    "invalid start-page record area".into(),
                ));
            }
            if &page.data[22..26] != b"KBDB" {
                return Err(CustomError::Corrupt(
                    "legacy v0 or missing KBDB magic; migration required".into(),
                ));
            }
            if u32::from_be_bytes(page.data[26..30].try_into()?) != 1 {
                return Err(CustomError::Corrupt("unsupported format version".into()));
            }
        } else {
            let mut offset = PAGE_HEADER_SIZE;
            for _ in 0..page.record_count {
                if offset + 2 > page.data_end as usize {
                    return Err(CustomError::Corrupt("record prefix overruns page".into()));
                }
                let len = u16::from_be_bytes(page.data[offset..offset + 2].try_into()?) as usize;
                offset += 2 + len;
                if offset > page.data_end as usize {
                    return Err(CustomError::Corrupt("record overruns page".into()));
                }
            }
            if offset != page.data_end as usize {
                return Err(CustomError::Corrupt(
                    "record count does not match data_end".into(),
                ));
            }
        }
        Ok(page)
    }
    // IMP =>
    /// Implementation details:
    /// If it's a catalog page, provide table_id, table_start_page, table_name_size and table_name as a record: [u8].
    /// Otherwise, provide just the record for a data page, and the length will be added automatically.

    pub fn insert_into_page(&mut self, record: &[u8]) -> Result<()> {
        if self.page_type == PageType::StartPage {
            return Err(CustomError::Err_from_wrong_arg(
                "Cannot insert record into a start page".to_string(),
            ));
        }
        self.insert_record_data(record)
    }

    fn insert_record_data(&mut self, record: &[u8]) -> Result<()> {
        if record.len() > PAGE_SIZE - PAGE_HEADER_SIZE - 2 {
            return Err(CustomError::RecordTooLarge);
        }
        if self.data_end as usize + record.len() + 2 > PAGE_SIZE {
            return Err(CustomError::PageFull);
        }
        self.data[self.data_end as usize..self.data_end as usize + 2]
            .copy_from_slice(&(record.len() as u16).to_be_bytes());
        self.data_end += 2;
        self.data[self.data_end as usize..(self.data_end as usize + record.len())]
            .copy_from_slice(record);
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
            return Err(CustomError::Err_from_wrong_arg(
                "Record no. exceeds record count".to_string(),
            ));
        }
        let mut offset = PAGE_HEADER_SIZE;
        if self.page_type == PageType::StartPage {
            return Err(CustomError::Err_from_wrong_arg(
                "Cannot read record from a start page".to_string(),
            ));
        } else {
            for _ in 0..record_no {
                let record_length = u16::from_be_bytes(self.data[offset..offset + 2].try_into()?);
                offset += 2 + record_length as usize;
            }
            let record_length = u16::from_be_bytes(self.data[offset..offset + 2].try_into()?);
            return Ok(&self.data[offset + 2..offset + 2 + record_length as usize]);
        }
    }

    pub fn get_page_no(&self) -> u32 {
        self.page_no
    }

    pub fn get_page_type(&self) -> PageType {
        self.page_type
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

    pub fn set_next_table_id(&mut self, next_table_id: u32) -> Result<()> {
        if self.page_type == PageType::StartPage {
            self.data[14..18].copy_from_slice(&next_table_id.to_be_bytes());
        } else {
            return Err(CustomError::Err_from_wrong_arg(
                "Cannot set start metadata on a non-start page".to_string(),
            ));
        }
        Ok(())
    }

    pub fn get_next_table_id(&self) -> Result<u32> {
        if self.page_type == PageType::StartPage {
            let mut metadata = [0u8; 4];
            metadata.copy_from_slice(&self.data[14..18]);
            Ok(u32::from_be_bytes(metadata))
        } else {
            Err(CustomError::Err_from_wrong_arg(
                "Cannot get start metadata from a non-start page".to_string(),
            ))
        }
    }

    pub fn get_catalog_page_no(&self) -> Result<u32> {
        if self.page_type == PageType::StartPage {
            let mut catalog_page_no_bytes = [0u8; 4];
            catalog_page_no_bytes.copy_from_slice(&self.data[18..22]);
            Ok(u32::from_be_bytes(catalog_page_no_bytes))
        } else {
            Err(CustomError::Err_from_wrong_arg(
                "Cannot get catalog page no from a non-start page".to_string(),
            ))
        }
    }

    pub fn set_catalog_page_no(&mut self, catalog_page_no: u32) -> Result<()> {
        if self.page_type == PageType::StartPage {
            self.data[18..22].copy_from_slice(&catalog_page_no.to_be_bytes());
            Ok(())
        } else {
            Err(CustomError::Err_from_wrong_arg(
                "Cannot set catalog page no on a non-start page".to_string(),
            ))
        }
    }
}
