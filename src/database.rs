use crate::catalog::manager::CatalogManager;
use crate::storage::buffer_pool::BufferPool;
use crate::error::{Result, CustomError};
use crate::storage::page::{PageType, Page, PAGE_HEADER_SIZE};

pub struct Database {
    catalog_manager: CatalogManager,
    buffer_pool: BufferPool,
}

impl Database {
    pub fn new(db_name: &str) -> Result<Database> {
        let mut b_p = BufferPool::new(db_name)?;
        let mut next_table_id = 0; // Initialize next_table_id to 0
        let start_page = match b_p.fetch_page(0) {
            Ok(page) => {
                let is_valid_start_page = page.get_page_no() == 0
                    && page.get_page_type() == PageType::StartPage
                    && page.get_data_end() >= PAGE_HEADER_SIZE as u16;

                if !is_valid_start_page {
                    return Err(CustomError::Err_from_wrong_arg("The first page is missing or corrupted, but other pages exist".to_string()));
                }
                next_table_id = page.get_next_table_id()?; //update next_table_id if already exists.
            }
            Err(_) => {
                // If the first page doesn't exist, create it as a start page
                if b_p.total_pages_in_disk()? > 0 {
                    return Err(CustomError::Err_from_wrong_arg("The first page is missing or corrupted, but other pages exist".to_string()));
                }
                b_p.create_page(PageType::StartPage)?;
            }
        };
        b_p.unpin(0)?;
        let c_m = CatalogManager::new(next_table_id);
        Ok(Database {
            catalog_manager: c_m,
            buffer_pool: b_p,
        })
    }
}

