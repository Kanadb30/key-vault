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
#[derive(Debug, Clone, PartialEq, Eq, Hash)]
pub struct TableMetadata {
    table_id: TableId,
    start_page: u32,
    table_name: String,
    columns: Vec<crate::codec::Column>,
}

impl TableMetadata {
    pub fn new(
        table_id: TableId,
        start_page: u32,
        table_name: String,
        columns: Vec<crate::codec::Column>,
    ) -> TableMetadata {
        TableMetadata {
            table_id,
            start_page,
            table_name,
            columns,
        }
    }
    pub fn columns(&self) -> &[crate::codec::Column] {
        &self.columns
    }

    pub fn table_id(&self) -> &TableId {
        &self.table_id
    }

    pub fn start_page(&self) -> u32 {
        self.start_page
    }

    pub fn table_name(&self) -> &String {
        &self.table_name
    }
}
