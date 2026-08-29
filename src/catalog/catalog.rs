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
        if self.catalog_items.contains_key(table_id) {
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
}


//---------------------------------------------------------------
// Tests for this module -> by chatgpt -> will remove.
//---------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_empty_catalog() {
        let catalog = Catalog::new();

        let table_id = TableId::new(1);

        assert!(catalog.get_table_metadata(&table_id).is_err());
    }

    #[test]
    fn test_add_and_get_table() {
        let mut catalog = Catalog::new();

        let table_id = TableId::new(1);
        let metadata = TableMetadata::new(table_id, 10);

        catalog
            .add_table(metadata)
            .expect("Failed to add table");

        let stored = catalog
            .get_table_metadata(&table_id)
            .expect("Failed to retrieve table");

        assert_eq!(stored.table_id().id(), 1);
        assert_eq!(stored.start_page(), 10);
    }

    #[test]
    fn test_multiple_tables() {
        let mut catalog = Catalog::new();

        let metadata1 = TableMetadata::new(TableId::new(1), 10);
        let metadata2 = TableMetadata::new(TableId::new(2), 20);
        let metadata3 = TableMetadata::new(TableId::new(3), 30);

        catalog.add_table(metadata1).unwrap();
        catalog.add_table(metadata2).unwrap();
        catalog.add_table(metadata3).unwrap();

        assert_eq!(
            catalog.get_table_metadata(&TableId::new(1))
                .unwrap()
                .start_page(),
            10
        );

        assert_eq!(
            catalog.get_table_metadata(&TableId::new(2))
                .unwrap()
                .start_page(),
            20
        );

        assert_eq!(
            catalog.get_table_metadata(&TableId::new(3))
                .unwrap()
                .start_page(),
            30
        );
    }

    #[test]
    fn test_nonexistent_table() {
        let mut catalog = Catalog::new();

        let metadata = TableMetadata::new(TableId::new(1), 10);

        catalog.add_table(metadata).unwrap();

        let result = catalog.get_table_metadata(&TableId::new(999));

        assert!(result.is_err());
    }

    #[test]
    fn test_duplicate_table_id_rejected() {
        let mut catalog = Catalog::new();

        let metadata1 = TableMetadata::new(TableId::new(1), 10);
        let metadata2 = TableMetadata::new(TableId::new(1), 20);

        catalog
            .add_table(metadata1)
            .expect("First insertion should succeed");

        let result = catalog.add_table(metadata2);

        assert!(result.is_err());

        // Original metadata must remain unchanged.
        let stored = catalog
            .get_table_metadata(&TableId::new(1))
            .expect("Original table should still exist");

        assert_eq!(stored.start_page(), 10);
    }

    #[test]
    fn test_table_id_zero() {
        let mut catalog = Catalog::new();

        let metadata = TableMetadata::new(TableId::new(0), 0);

        catalog
            .add_table(metadata)
            .expect("Table with ID 0 should be accepted");

        let stored = catalog
            .get_table_metadata(&TableId::new(0))
            .expect("Failed to retrieve table");

        assert_eq!(stored.table_id().id(), 0);
        assert_eq!(stored.start_page(), 0);
    }
}