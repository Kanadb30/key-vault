use crate::catalog::manager::CatalogManager;
use crate::catalog::table::TableMetadata;
use crate::storage::buffer_pool::BufferPool;
use crate::error::{Result, CustomError};
use crate::storage::page::{PageType, PAGE_HEADER_SIZE};

pub struct Database {
    catalog_manager: CatalogManager,
    buffer_pool: BufferPool,
}

impl Database {
    pub fn new(db_name: &str) -> Result<Database> {
        let mut b_p = BufferPool::new(db_name)?;
        let (next_table_id, mut catalog_page_no) = match b_p.fetch_page(0) {
            Ok(page) => {
                let is_valid_start_page = page.get_page_no() == 0
                    && page.get_page_type() == PageType::StartPage
                    && page.get_data_end() >= PAGE_HEADER_SIZE as u16;

                if !is_valid_start_page {
                    return Err(CustomError::Err_from_wrong_arg("The first page is missing or corrupted, but other pages exist".to_string()));
                }
                (page.get_next_table_id()?, page.get_catalog_page_no()?)
            }
            Err(_) => {
                // If the first page doesn't exist, create it as a start page
                if b_p.total_pages_in_disk()? > 0 {
                    return Err(CustomError::Err_from_wrong_arg("The first page is missing or corrupted, but other pages exist".to_string()));
                }
                b_p.create_page(PageType::StartPage)?;
                (0, u32::MAX)
            }
        };
        let mut c_m = CatalogManager::new(next_table_id);
        while catalog_page_no != u32::MAX {
            let catalog_page = b_p.fetch_page(catalog_page_no)?;
            let mut record_count = catalog_page.get_record_count();
            while record_count > 0 {
                // Process each record in the catalog page
                let record = catalog_page.read_record(record_count - 1)?;
                let table_id = u32::from_be_bytes(record[0..4].try_into()?);
                let table_start_page = u32::from_be_bytes(record[4..8].try_into()?);
                let table_name_size = u16::from_be_bytes(record[8..10].try_into()?);
                let table_name = String::from_utf8(record[10..(10 + table_name_size as usize)].to_vec())
                    .map_err(|_| CustomError::Err_from_wrong_arg("Invalid UTF-8 in table name".to_string()))?;
                let table_metadata = TableMetadata::new(crate::catalog::table::TableId::new(table_id), table_start_page, table_name);
                c_m.add_table(table_metadata)?;
                record_count -= 1;
                
            }
            let unpin_page_no = catalog_page.get_page_no(); 
            catalog_page_no = catalog_page.get_next_page_no();
            b_p.unpin(unpin_page_no)?;
        }

        b_p.unpin(0)?;
        
        Ok(Database {
            catalog_manager: c_m,
            buffer_pool: b_p,
        })
    }

    // TODO: Implement methods for creating tables, inserting records, querying records, etc.

    // fn create_table(&mut self, table_name: &str) -> Result<u32> {
    //     let catalog_page_no = self.buffer_pool.fetch_page(0)?.get_catalog_page_no()?;
    //     if catalog_page_no == u32::MAX {
    //         // first table creation
    //         let new_catalog_page_no = self.buffer_pool.create_page(PageType::CatalogPage)?.get_page_no();
            
    //     }

    // }

    // fn create_table(&mut self, table_name: &str) -> Result<u32> {
    // }

    
}

