pub mod error;
pub mod storage;
pub mod catalog;

pub use crate::error::{CustomError, Result};
pub use crate::storage::buffer_pool::{BufferPool, BUFFER_POOL_CAPACITY};
pub use crate::storage::disk_manager::DiskManager;
pub use crate::storage::page::{Page, PAGE_SIZE};
