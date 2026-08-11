
// Strated a new project today dont know if I will complete or not.
// Lets seee.
mod page;
mod diskManager;
mod customErrors;

use crate::customErrors::CustomError;
use crate::customErrors::Result;

use crate::page::{PAGE_SIZE, Page};

fn main() {
    // 1. Create an empty page
    let mut page = Page::new(0);

    println!("Initial page:");
    println!("page_no      = {}", page.page_no);
    println!("data_end     = {}", page.data_end);
    println!("record_count = {}", page.record_count);

    // 2. Insert some records
    page.insert_record(b"hello").unwrap();
    page.insert_record(b"rust").unwrap();
    page.insert_record(b"database").unwrap();

    println!("\nAfter inserting records:");
    println!("page_no      = {}", page.page_no);
    println!("data_end     = {}", page.data_end);
    println!("record_count = {}", page.record_count);

    // 3. Read records back
    let record0 = page.read_record(0).unwrap();
    let record1 = page.read_record(1).unwrap();
    let record2 = page.read_record(2).unwrap();

    println!("\nRecords:");
    println!("record 0 = {:?}", String::from_utf8(record0.to_vec()).unwrap());
    println!("record 1 = {:?}", String::from_utf8(record1.to_vec()).unwrap());
    println!("record 2 = {:?}", String::from_utf8(record2.to_vec()).unwrap());

    // 4. Try reading a record that doesn't exist
    match page.read_record(3) {
        Ok(record) => {
            println!("Unexpected record: {:?}", record);
        }
        Err(e) => {
            println!("\nCorrectly rejected record 3: {:?}", e);
        }
    }

    // 5. Test serialization/deserialization
    //
    // `page.data` is our serialized page representation.
    let raw_page = page.data;

    let restored_page = Page::create(raw_page).unwrap();

    println!("\nRestored page:");
    println!("page_no      = {}", restored_page.page_no);
    println!("data_end     = {}", restored_page.data_end);
    println!("record_count = {}", restored_page.record_count);

    // 6. Verify records survive deserialization
    let restored0 = restored_page.read_record(0).unwrap();
    let restored1 = restored_page.read_record(1).unwrap();
    let restored2 = restored_page.read_record(2).unwrap();

    println!("\nRecords after deserialization:");
    println!(
        "record 0 = {:?}",
        String::from_utf8(restored0.to_vec()).unwrap()
    );
    println!(
        "record 1 = {:?}",
        String::from_utf8(restored1.to_vec()).unwrap()
    );
    println!(
        "record 2 = {:?}",
        String::from_utf8(restored2.to_vec()).unwrap()
    );
}


