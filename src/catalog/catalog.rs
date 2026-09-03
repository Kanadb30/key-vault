use std::collections::HashMap;
use crate::catalog::table::{TableId, TableMetadata};
use crate::error::{CustomError, Result};

pub struct Catalog{
    catalog_items: HashMap<TableId, TableMetadata>,
}

impl Catalog {
    pub fn new() -> Catalog {
        Catalog {
            catalog_items: HashMap::new(),
        }
    }

    pub fn add_table(&mut self, metadata: TableMetadata) -> Result<()>{
        let table_id = metadata.table_id();
        if self.catalog_items.contains_key(table_id) || self.catalog_items.values().any(|m| m.table_name() == metadata.table_name()) {
            return Err(CustomError::Err_from_wrong_arg("Table ID already exists in catalog".to_string()));
        }
        self.catalog_items.insert(*table_id, metadata);
        Ok(())
    }

    pub fn get_table_metadata(&self, table_id: &TableId) -> Result<&TableMetadata> {
        match self.catalog_items.get(table_id) {
            Some(metadata) => Ok(metadata),
            None => Err(CustomError::Err_from_wrong_arg("Table ID not found in catalog".to_string())),
        }
    }

    pub fn get_total_no_of_tables(&self) -> u32 {
        self.catalog_items.len() as u32
    }
}