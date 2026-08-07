use thiserror::Error;

// Its used so that Result<T, E> can now cover String as well as I/O error at the same time.
// plus dont need to write Result<T, CustomE> again and again. Just use Result<T> now.


pub type Result<T> = std::result::Result<T, CustomError>;

#[derive(Error, Debug)]
pub enum CustomError {
    #[error("An Error occurred: {0}")]
    InvalidUser(String),

    #[error("I/O error occurred")]
    IoError(#[from] std::io::Error),
}

