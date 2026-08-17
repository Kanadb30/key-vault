use thiserror::Error;

pub type Result<T> = std::result::Result<T, CustomError>;

#[derive(Error, Debug)]
pub enum CustomError {
    #[error("An Error occurred: {0}")]
    Err_from_wrong_arg(String),

    #[error("I/O error occurred")]
    IoError(#[from] std::io::Error),

    #[error("Conversion Error Occurred")]
    ConversionError(#[from] std::array::TryFromSliceError),
}
