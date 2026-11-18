use kb_db::{
    CustomError,
    codec::{self, Column, ColumnType},
    database::Database,
    storage::page::{Page, PageType},
};
use serde_json::{Value, json};
use std::{
    fs,
    io::Write,
    process::{Command, Stdio},
    sync::atomic::{AtomicU64, Ordering},
    time::{SystemTime, UNIX_EPOCH},
};

static COUNTER: AtomicU64 = AtomicU64::new(0);
struct Temp(String);
impl Temp {
    fn new() -> Self {
        let root = if std::path::Path::new("/tmp/opencode").exists() {
            "/tmp/opencode".into()
        } else {
            std::env::temp_dir()
        };
        Self(
            std::path::PathBuf::from(root)
                .join(format!(
                    "kb-test-{}-{}-{}.db",
                    std::process::id(),
                    SystemTime::now()
                        .duration_since(UNIX_EPOCH)
                        .unwrap()
                        .as_nanos(),
                    COUNTER.fetch_add(1, Ordering::Relaxed)
                ))
                .to_string_lossy()
                .into_owned(),
        )
    }
}
impl Drop for Temp {
    fn drop(&mut self) {
        let _ = fs::remove_file(&self.0);
    }
}
fn cols() -> Vec<Column> {
    vec![
        Column {
            name: "id".into(),
            column_type: ColumnType::INTEGER,
        },
        Column {
            name: "name".into(),
            column_type: ColumnType::TEXT,
        },
    ]
}

#[test]
fn positional_codec_handles_i64_unicode_and_duplicates() {
    for row in [
        vec![json!(i64::MIN), json!("नमस्ते O'Brien")],
        vec![json!(i64::MAX), json!("")],
    ] {
        let bytes = codec::encode_row(&cols(), &row).unwrap();
        assert_eq!(codec::decode_row(&cols(), &bytes).unwrap(), row);
    }
}
#[test]
fn schema_catalog_codec_round_trip() {
    use kb_db::catalog::table::{TableId, TableMetadata};
    let table = TableMetadata::new(TableId::new(7), 12, "students".into(), cols());
    assert_eq!(
        codec::decode_catalog(&codec::encode_catalog(&table).unwrap()).unwrap(),
        table
    );
}
#[test]
fn rejects_bool_float_null_wrong_width_and_overflow() {
    for row in [
        vec![json!(true), json!("x")],
        vec![json!(1.5), json!("x")],
        vec![Value::Null, json!("x")],
        vec![json!(u64::MAX), json!("x")],
        vec![json!(1)],
    ] {
        assert!(matches!(
            codec::encode_row(&cols(), &row),
            Err(CustomError::Schema(_))
        ));
    }
}
#[test]
fn oversized_record_is_not_page_full() {
    let mut page = Page::new(1, PageType::DataPage);
    assert!(matches!(
        page.insert_into_page(&vec![0; 4081]),
        Err(CustomError::RecordTooLarge)
    ));
    page.insert_into_page(&vec![0; 4080]).unwrap();
    assert!(matches!(
        page.insert_into_page(&[1]),
        Err(CustomError::PageFull)
    ));
}

#[test]
fn all_pinned_eviction_failure_does_not_poison_the_pool() {
    let path = Temp::new();
    let mut pool = kb_db::BufferPool::new(&path.0).unwrap();
    for _ in 0..5 {
        pool.create_page(PageType::DataPage).unwrap();
    }
    assert!(pool.create_page(PageType::DataPage).is_err());
    assert_eq!(pool.total_pages_in_disk().unwrap(), 5);
    pool.unpin(0).unwrap();
    assert_eq!(
        pool.create_page(PageType::DataPage).unwrap().get_page_no(),
        5
    );
    assert_eq!(pool.page_count(), 5);
}
#[test]
fn rejects_invalid_page_record_bounds() {
    let mut page = Page::new(1, PageType::CatalogPage);
    page.insert_into_page(&[1, 2, 3]).unwrap();
    page.data[14..16].copy_from_slice(&100u16.to_be_bytes());
    assert!(matches!(
        Page::create(page.data),
        Err(CustomError::Corrupt(_))
    ));
}
#[test]
fn persistence_spans_more_than_five_pages() {
    let path = Temp::new();
    let rows: Vec<_> = (0..100)
        .map(|i| vec![json!(i), json!("x".repeat(1000))])
        .collect();
    {
        let mut db = Database::new(&path.0).unwrap();
        db.create_table("items".into(), cols()).unwrap();
        db.insert_rows("items", &rows).unwrap();
        assert_eq!(db.scan_table("items").unwrap(), rows);
    }
    let mut db = Database::new(&path.0).unwrap();
    assert_eq!(db.tables()[0].columns(), cols());
    assert_eq!(db.scan_table("items").unwrap(), rows);
    assert!(fs::metadata(&path.0).unwrap().len() > 4096 * 5);
}
#[test]
fn catalog_chains_and_reopens_with_many_schemas() {
    let path = Temp::new();
    let columns = vec![
        Column {
            name: format!("c{}", "a".repeat(200)),
            column_type: ColumnType::INTEGER
        };
        1
    ];
    {
        let mut db = Database::new(&path.0).unwrap();
        for i in 0..100 {
            db.create_table(format!("table_{i}"), columns.clone())
                .unwrap();
        }
    }
    let db = Database::new(&path.0).unwrap();
    assert_eq!(db.tables().len(), 100);
}
#[test]
fn invalid_batch_does_not_partially_insert() {
    let path = Temp::new();
    let mut db = Database::new(&path.0).unwrap();
    db.create_table("items".into(), cols()).unwrap();
    assert!(
        db.insert_rows(
            "items",
            &[vec![json!(1), json!("ok")], vec![json!(true), json!("bad")]]
        )
        .is_err()
    );
    assert!(db.scan_table("items").unwrap().is_empty());
}
#[test]
fn duplicate_tables_and_oversized_rows_are_recoverable() {
    let path = Temp::new();
    let mut db = Database::new(&path.0).unwrap();
    db.create_table("items".into(), cols()).unwrap();
    assert!(matches!(
        db.create_table("items".into(), cols()),
        Err(CustomError::TableNameExists(_))
    ));
    assert!(matches!(
        db.insert_rows("items", &[vec![json!(1), json!("a".repeat(4080))]]),
        Err(CustomError::RecordTooLarge)
    ));
    db.insert_rows(
        "items",
        &[vec![json!(1), json!("ok")], vec![json!(1), json!("ok")]],
    )
    .unwrap();
    assert_eq!(db.scan_table("items").unwrap().len(), 2);
}
#[test]
fn refuses_legacy_wrong_version_and_truncation() {
    for kind in 0..3 {
        let path = Temp::new();
        let mut page = Page::new(0, PageType::StartPage).data;
        if kind == 0 {
            page[22] = 0;
        } else if kind == 1 {
            page[26..30].copy_from_slice(&2u32.to_be_bytes());
        }
        fs::write(&path.0, if kind == 2 { &page[..4000] } else { &page }).unwrap();
        assert!(matches!(
            Database::new(&path.0),
            Err(CustomError::Corrupt(_))
        ));
    }
}
#[test]
fn rejects_cycles_without_hanging() {
    let path = Temp::new();
    {
        let mut db = Database::new(&path.0).unwrap();
        db.create_table("items".into(), cols()).unwrap();
    }
    let mut bytes = fs::read(&path.0).unwrap();
    bytes[4096 + 10..4096 + 14].copy_from_slice(&1u32.to_be_bytes());
    fs::write(&path.0, bytes).unwrap();
    assert!(matches!(
        Database::new(&path.0),
        Err(CustomError::Corrupt(_))
    ));
}
#[test]
fn protocol_recovers_after_error_and_echoes_ids() {
    let path = Temp::new();
    let mut child = Command::new(env!("CARGO_BIN_EXE_kb_db"))
        .args(["--bridge", "--db", &path.0])
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .unwrap();
    {
        let mut input = child.stdin.take().unwrap();
        for request in [
            json!({"type":"ready","protocol":1}),
            json!({"id":1,"type":"invalid"}),
            json!({"id":2,"type":"create_table","name":"items","columns":cols()}),
            json!({"id":3,"type":"insert_rows","table":"items","rows":[[1,"Asha"]]}),
            json!({"id":4,"type":"scan_table","table":"items"}),
        ] {
            writeln!(input, "{request}").unwrap();
        }
    }
    let output = child.wait_with_output().unwrap();
    assert!(output.status.success(), "{:?}", output);
    let frames: Vec<Value> = String::from_utf8(output.stdout)
        .unwrap()
        .lines()
        .map(|line| serde_json::from_str(line).unwrap())
        .collect();
    assert_eq!(frames[0]["protocol"], 1);
    assert_eq!(frames[1]["code"], "UNSUPPORTED");
    assert_eq!(frames.last().unwrap()["batch"], json!([[1, "Asha"]]));
    assert_eq!(frames.last().unwrap()["id"], 4);
    assert_eq!(frames.last().unwrap()["done"], true);
}
