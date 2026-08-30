use crate::error::{CustomError, Result};

pub struct DatabaseMetadata {
    catalog_page_no: u32,
}

impl DatabaseMetadata {
    pub fn new(catalog_page_no: u32) -> DatabaseMetadata {
        DatabaseMetadata { catalog_page_no }
    }

    pub fn catalog_page_no(&self) -> u32 {
        self.catalog_page_no
    }

    pub fn serialize(&self) -> [u8; 4] {
        self.catalog_page_no.to_be_bytes()
    }

    pub fn deserialize(data: &[u8]) -> Result<DatabaseMetadata> {
        if data.len() != 4 {
            return Err(CustomError::Err_from_wrong_arg("Invalid data length for DatabaseMetadata".to_string()));
        }
        let catalog_page_no = u32::from_be_bytes(data.try_into()?);
        Ok(DatabaseMetadata { catalog_page_no })
    }
}

