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

// Test files -> by chatgpt -> will remove.

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_database_metadata_round_trip() {
        let metadata = DatabaseMetadata::new(5);

        let serialized = metadata.serialize();

        let restored = DatabaseMetadata::deserialize(&serialized)
            .expect("Failed to deserialize metadata");

        assert_eq!(restored.catalog_page_no(), 5);
    }

    #[test]
    fn test_database_metadata_big_endian() {
        let metadata = DatabaseMetadata::new(0x12345678);

        let serialized = metadata.serialize();

        assert_eq!(
            serialized,
            [0x12, 0x34, 0x56, 0x78]
        );
    }

    #[test]
    fn test_database_metadata_invalid_length() {
        let data = [0x12, 0x34, 0x56];

        let result = DatabaseMetadata::deserialize(&data);

        assert!(result.is_err());
    }

    #[test]
    fn test_database_metadata_zero() {
        let metadata = DatabaseMetadata::new(0);

        let serialized = metadata.serialize();

        assert_eq!(serialized, [0, 0, 0, 0]);

        let restored = DatabaseMetadata::deserialize(&serialized)
            .expect("Failed to deserialize metadata");

        assert_eq!(restored.catalog_page_no(), 0);
    }
}