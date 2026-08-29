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

//---------------------------------------------------------------
// Tests for this module -> by chatgpt -> will remove.
//---------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_empty_manager() {
        let manager = CatalogManager::new();

        let table_id = TableId::new(0);

        assert!(manager.get_table_metadata(&table_id).is_err());
    }

    #[test]
    fn test_create_first_table() {
        let mut manager = CatalogManager::new();

        let table_id = manager
            .create_table(10)
            .expect("Failed to create table");

        assert_eq!(table_id.id(), 0);

        let metadata = manager
            .get_table_metadata(&table_id)
            .expect("Failed to retrieve table");

        assert_eq!(metadata.table_id().id(), 0);
        assert_eq!(metadata.start_page(), 10);
    }

    #[test]
    fn test_create_multiple_tables() {
        let mut manager = CatalogManager::new();

        let table1 = manager.create_table(10).unwrap();
        let table2 = manager.create_table(20).unwrap();
        let table3 = manager.create_table(30).unwrap();

        assert_eq!(table1.id(), 0);
        assert_eq!(table2.id(), 1);
        assert_eq!(table3.id(), 2);

        assert_eq!(
            manager.get_table_metadata(&table1).unwrap().start_page(),
            10
        );

        assert_eq!(
            manager.get_table_metadata(&table2).unwrap().start_page(),
            20
        );

        assert_eq!(
            manager.get_table_metadata(&table3).unwrap().start_page(),
            30
        );
    }

    #[test]
    fn test_nonexistent_table() {
        let mut manager = CatalogManager::new();

        manager.create_table(10).unwrap();

        let nonexistent = TableId::new(999);

        assert!(manager.get_table_metadata(&nonexistent).is_err());
    }

    #[test]
    fn test_table_ids_are_sequential() {
        let mut manager = CatalogManager::new();

        let id1 = manager.create_table(100).unwrap();
        let id2 = manager.create_table(200).unwrap();
        let id3 = manager.create_table(300).unwrap();

        assert_eq!(id1.id() + 1, id2.id());
        assert_eq!(id2.id() + 1, id3.id());
    }

    #[test]
    fn test_start_page_zero() {
        let mut manager = CatalogManager::new();

        let table_id = manager
            .create_table(0)
            .expect("Failed to create table");

        let metadata = manager
            .get_table_metadata(&table_id)
            .expect("Failed to retrieve table");

        assert_eq!(metadata.start_page(), 0);
    }
}