use thiserror::Error;

pub type Result<T> = std::result::Result<T, CustomError>;

#[derive(Error, Debug)]
pub enum CustomError {
    #[error("Corrupt database: {0}")]
    Corrupt(String),
    #[error("Schema mismatch: {0}")]
    Schema(String),
    #[error("Record too large for a page (maximum 4080 bytes)")]
    RecordTooLarge,
    #[error("Page full")]
    PageFull,
    #[error("Unsupported request: {0}")]
    Unsupported(String),
    #[error("An Error occurred: {0}")]
    #[allow(non_camel_case_types)]
    Err_from_wrong_arg(String),

    #[error("Table ID {0} already exists in catalog")]
    TableIdExists(u32),

    #[error("Table name '{0}' already exists in catalog")]
    TableNameExists(String),

    #[error("I/O error occurred")]
    IoError(#[from] std::io::Error),

    #[error("Conversion Error Occurred")]
    ConversionError(#[from] std::array::TryFromSliceError),
}
