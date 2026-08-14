
// Strated a new project today dont know if I will complete or not.
// Lets seee.
mod customErrors;
mod page;
mod diskManager;
mod BufferPool;


use crate::customErrors::CustomError;
use crate::customErrors::Result;
use crate::BufferPool::{BufferPool as BP, BUFFER_POOL_CAPACITY};
use crate::diskManager::DiskManager;
use crate::page::{PAGE_SIZE, Page};



fn main() {

    // ============================================================
    // CLEAN SETUP
    // ============================================================

    let db_name = "buffer_pool_test";

    // Create a fresh database.
    let mut dm = DiskManager::new_db(db_name).unwrap();

    println!("Database created.");

    // Create 6 pages.
    //
    // BufferPool capacity is currently 5,
    // so loading all 6 will force an eviction.
    for i in 0..6 {
        let mut page = dm.create_page().unwrap();

        page.insert_record(format!("page_{}", i).as_bytes()).unwrap();

        dm.write_page(page.page_no, &page.data).unwrap();

        println!("Created page {}", page.page_no);
    }

    assert_eq!(dm.total_pages().unwrap(), 6);

    drop(dm);

    println!("\nDatabase setup complete.");


    // ============================================================
    // TEST 1
    // Basic BufferPool creation
    // ============================================================

    let mut bp = BP::new(db_name).unwrap();

    println!("\nBufferPool created.");

    assert_eq!(bp.page_table.len(), 0);

    println!("Initial page_table is empty.");


    // ============================================================
    // TEST 2
    // Fetch page 0
    //
    // fetch_page() internally pins the page.
    // We do NOT call pin() because it is private.
    // ============================================================

    {
        let page = bp.fetch_page(0).unwrap();

        println!("\nFetched page 0:");
        println!("page_no      = {}", page.page_no);
        println!("record_count = {}", page.record_count);

        assert_eq!(page.page_no, 0);
        assert_eq!(page.record_count, 1);

        assert_eq!(
            page.read_record(0).unwrap(),
            b"page_0"
        );
    }

    // The reference is now gone.
    //
    // But the DATABASE pin is still present because
    // fetch_page() pinned page 0 and we have not unpinned it yet.

    println!("Page 0 is pinned internally.");


    // ============================================================
    // TEST 3
    // Verify unpin works
    // ============================================================

    bp.unpin(0).unwrap();

    println!("Page 0 successfully unpinned.");


    // ============================================================
    // TEST 4
    // Fetch page 0 again
    //
    // This should be a BufferPool hit, not a disk load.
    // ============================================================

    {
        let page = bp.fetch_page(0).unwrap();

        println!("\nFetched page 0 again.");

        assert_eq!(page.page_no, 0);
        assert_eq!(page.record_count, 1);
    }

    // Release the pin created by this fetch.
    bp.unpin(0).unwrap();

    println!("Second fetch successful.");


    // ============================================================
    // TEST 5
    // Mutable fetch
    //
    // fetch_page_mut() should:
    // 1. fetch the page
    // 2. pin it
    // 3. mark it dirty
    // ============================================================

    {
        let page = bp.fetch_page_mut(0).unwrap();

        page.insert_record(b"modified").unwrap();

        println!("\nModified page 0 through BufferPool.");

        assert_eq!(page.record_count, 2);
    }

    // IMPORTANT:
    // fetch_page_mut() currently leaves the page pinned.
    // Release that pin manually.
    bp.unpin(0).unwrap();

    println!("Modified page 0 unpinned.");


    // ============================================================
    // TEST 6
    // Verify mutation remains in BufferPool memory
    // ============================================================

    {
        let page = bp.fetch_page(0).unwrap();

        println!("\nPage 0 after mutation:");
        println!("record_count = {}", page.record_count);

        assert_eq!(page.record_count, 2);

        assert_eq!(
            page.read_record(1).unwrap(),
            b"modified"
        );
    }

    bp.unpin(0).unwrap();

    println!("Mutation exists in BufferPool.");


    // ============================================================
    // TEST 7
    // Verify dirty page is NOT yet persisted
    //
    // We deliberately open a separate DiskManager.
    // ============================================================

    {
        let mut dm = DiskManager::open_db(db_name).unwrap();

        let page = dm.read_page(0).unwrap();

        println!("\nPage 0 directly from disk BEFORE flush:");
        println!("record_count = {}", page.record_count);

        assert_eq!(page.record_count, 1);

        assert_eq!(
            page.read_record(0).unwrap(),
            b"page_0"
        );
    }

    println!("Disk still contains the old version.");


    // ============================================================
    // TEST 8
    // Flush BufferPool
    // ============================================================

    bp.flush().unwrap();

    println!("\nBufferPool flushed.");


    // ============================================================
    // TEST 9
    // Verify dirty page reached disk
    // ============================================================

    {
        let mut dm = DiskManager::open_db(db_name).unwrap();

        let page = dm.read_page(0).unwrap();

        println!("\nPage 0 directly from disk AFTER flush:");
        println!("record_count = {}", page.record_count);

        assert_eq!(page.record_count, 2);

        assert_eq!(
            page.read_record(0).unwrap(),
            b"page_0"
        );

        assert_eq!(
            page.read_record(1).unwrap(),
            b"modified"
        );
    }

    println!("Dirty page successfully persisted.");


    // ============================================================
    // TEST 10
    // Fill BufferPool
    //
    // Capacity = 5.
    //
    // Pages 0,1,2,3,4 should occupy the pool.
    // ============================================================

    {
        let page = bp.fetch_page(0).unwrap();
        assert_eq!(page.page_no, 0);
    }
    bp.unpin(0).unwrap();

    {
        let page = bp.fetch_page(1).unwrap();
        assert_eq!(page.page_no, 1);
    }
    bp.unpin(1).unwrap();

    {
        let page = bp.fetch_page(2).unwrap();
        assert_eq!(page.page_no, 2);
    }
    bp.unpin(2).unwrap();

    {
        let page = bp.fetch_page(3).unwrap();
        assert_eq!(page.page_no, 3);
    }
    bp.unpin(3).unwrap();

    {
        let page = bp.fetch_page(4).unwrap();
        assert_eq!(page.page_no, 4);
    }
    bp.unpin(4).unwrap();

    println!("\nBufferPool filled.");

    assert_eq!(bp.page_table.len(), 5);


    // ============================================================
    // TEST 11
    // LRU ordering
    //
    // fetch_page(0) makes page 0 the newest.
    //
    // Therefore page 1 should become the oldest.
    // ============================================================

    {
        let page = bp.fetch_page(0).unwrap();
        assert_eq!(page.page_no, 0);
    }
    bp.unpin(0).unwrap();

    println!("\nLRU order after accessing page 0:");

    for page_no in &bp.lru {
        print!("{} ", page_no);
    }

    println!();


    // ============================================================
    // TEST 12
    // Force eviction by loading page 5.
    //
    // Page 1 should be the LRU candidate.
    // ============================================================

    {
        let page = bp.fetch_page(5).unwrap();

        println!("\nFetched page 5.");
        assert_eq!(page.page_no, 5);
    }

    bp.unpin(5).unwrap();

    println!("Page 5 loaded successfully.");

    assert_eq!(bp.page_table.len(), 5);

    // Page 1 should have been evicted.
    assert!(
        !bp.page_table.contains_key(&1),
        "Page 1 should have been evicted as the LRU page"
    );

    // Page 0 should still exist because we accessed it recently.
    assert!(
        bp.page_table.contains_key(&0),
        "Page 0 should still be present"
    );

    // Page 5 must obviously exist.
    assert!(
        bp.page_table.contains_key(&5),
        "Page 5 should be present"
    );

    println!("LRU eviction behaved correctly.");


    // ============================================================
    // TEST 13
    // PINNED PAGE MUST NOT BE EVICTED
    //
    // We need a full pool again.
    // ============================================================

    // Fetch page 1 again.
    //
    // This will load it from disk because it was evicted.
    {
        let page = bp.fetch_page(1).unwrap();
        assert_eq!(page.page_no, 1);
    }

    bp.unpin(1).unwrap();


    // At this point we have five pages again.
    assert_eq!(bp.page_table.len(), 5);


    // Make page 0 pinned.
    //
    // fetch_page() increments its pin count.
    let page = bp.fetch_page(0).unwrap();

    println!("\nPage 0 fetched and intentionally left pinned.");

    assert_eq!(page.page_no, 0);


    // IMPORTANT:
    //
    // We cannot use `bp` again while `page` is alive because
    // `page` is a reference into bp.
    //
    // Therefore we end this scope first.
    let _ = page;


    // Page 0 is STILL database-pinned.
    //
    // We have deliberately NOT called:
    //
    // bp.unpin(0)
    //
    // yet.


    // ============================================================
    // TEST 14
    // Force another eviction.
    //
    // Page 0 must NOT be evicted because it is pinned.
    // ============================================================

    {
        let page = bp.fetch_page(5).unwrap();

        println!("\nFetched page 5 while page 0 is pinned.");

        assert_eq!(page.page_no, 5);
    }

    bp.unpin(5).unwrap();

    assert!(
        bp.page_table.contains_key(&0),
        "Pinned page 0 must NOT be evicted"
    );

    println!("Pinned page 0 correctly protected from eviction.");


    // ============================================================
    // TEST 15
    // Release page 0
    // ============================================================

    bp.unpin(0).unwrap();

    println!("Page 0 successfully unpinned.");


    // ============================================================
    // TEST 16
    // Invalid unpin
    //
    // Page 0 is currently already unpinned.
    // ============================================================

    let result = bp.unpin(0);

    println!("\nInvalid unpin result: {:?}", result);

    assert!(
        result.is_err(),
        "Unpinning an already-unpinned page should fail"
    );

    println!("Invalid unpin correctly rejected.");


    // ============================================================
    // FINAL
    // ============================================================

    println!("\n========================================");
    println!("ALL BUFFER POOL TESTS PASSED");
    println!("========================================");
}