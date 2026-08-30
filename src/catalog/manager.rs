use crate::catalog::{Catalog, TableId, TableMetadata};
use crate::error::{Result, CustomError};

pub struct CatalogManager {
    next_table_id: u32,
    catalog: Catalog,
}

impl CatalogManager {
    pub fn new() -> CatalogManager {
        CatalogManager { 
            next_table_id: 0,
            catalog: Catalog::new() 
        }
    }

    pub fn create_table(&mut self, start_page: u32) -> Result<TableId> {
        if self.next_table_id == u32::MAX {
            return Err(CustomError::Err_from_wrong_arg("Maximum number of tables reached".to_string()));
        }
        let table_id = TableId::new(self.next_table_id);
        let metadata = TableMetadata::new(table_id, start_page);
        self.catalog.add_table(metadata)?;
        self.next_table_id += 1;
        Ok(table_id)
    }

    pub fn get_table_metadata(&self, table_id: &TableId) -> Result<&TableMetadata> {
        self.catalog.get_table_metadata(table_id)
    }
}

