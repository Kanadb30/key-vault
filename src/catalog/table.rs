
pub struct TableId {
    id: u32,
}

impl TableId {
    pub fn new(id: u32) -> TableId {
        TableId { id }
    }

    pub fn id(&self) -> u32 {
        self.id
    }
}

pub struct TableMetadata {
    table_id: TableId,
    start_page: u32,
}

impl TableMetadata {
    pub fn new(table_id: TableId, start_page: u32) -> TableMetadata {
        TableMetadata { table_id, start_page }
    }

    pub fn table_id(&self) -> &TableId {
        &self.table_id
    }

    pub fn start_page(&self) -> u32 {
        self.start_page
    }
}

// --------------------------------------------------------------------------------------
// Tests for this module -> by chatgpt -> will remove.
// --------------------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_table_id() {
        let table_id = TableId::new(123);

        assert_eq!(table_id.id(), 123);
    }

    #[test]
    fn test_table_id_zero() {
        let table_id = TableId::new(0);

        assert_eq!(table_id.id(), 0);
    }

    #[test]
    fn test_table_metadata() {
        let table_id = TableId::new(123);
        let metadata = TableMetadata::new(table_id, 999);

        assert_eq!(metadata.table_id().id(), 123);
        assert_eq!(metadata.start_page(), 999);
    }

    #[test]
    fn test_table_metadata_first_page_zero() {
        let table_id = TableId::new(1);
        let metadata = TableMetadata::new(table_id, 0);

        assert_eq!(metadata.table_id().id(), 1);
        assert_eq!(metadata.start_page(), 0);
    }

    #[test]
    fn test_multiple_table_ids() {
        let table1 = TableId::new(1);
        let table2 = TableId::new(2);
        let table3 = TableId::new(123);

        assert_eq!(table1.id(), 1);
        assert_eq!(table2.id(), 2);
        assert_eq!(table3.id(), 123);
    }
}