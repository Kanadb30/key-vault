
// Strated a new project today dont know if I will complete or not.
// Lets seee.
mod customErrors;
mod page;
mod diskManager;
mod BufferPool;

use crate::customErrors::CustomError;
use crate::customErrors::Result;

use crate::diskManager::DiskManager;
use crate::page::{PAGE_SIZE, Page};



fn main() {
   let bp = BufferPool::BufferPool::new("test_db");
}

