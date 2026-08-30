
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
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
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
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

