use kb_db::{CustomError, codec::Column, database::Database};
use serde_json::{Value, json};
use std::io::{self, BufRead, Read, Write};
use std::path::Path;

fn code(error: &CustomError) -> &'static str {
    match error {
        CustomError::IoError(_) => "IO",
        CustomError::Corrupt(_) | CustomError::ConversionError(_) => "CORRUPT",
        CustomError::Schema(_) => "SCHEMA_MISMATCH",
        CustomError::RecordTooLarge => "RECORD_TOO_LARGE",
        CustomError::TableIdExists(_) | CustomError::TableNameExists(_) => "DUPLICATE_TABLE",
        CustomError::Unsupported(_) => "UNSUPPORTED",
        _ => "INTERNAL",
    }
}
fn send(value: Value) -> io::Result<()> {
    let stdout = io::stdout();
    let mut out = stdout.lock();
    serde_json::to_writer(&mut out, &value)?;
    out.write_all(b"\n")?;
    out.flush()
}
fn tables(db: &Database) -> Value {
    Value::Array(
        db.tables()
            .iter()
            .map(|t| {
                json!({
                    "name": t.table_name(), "columns": t.columns(),
                })
            })
            .collect(),
    )
}
fn request(db: &mut Database, req: &Value) -> Result<(), CustomError> {
    let id = &req["id"];
    if !id.is_u64() {
        return Err(CustomError::Unsupported(
            "id must be an unsigned integer".into(),
        ));
    }
    let kind = req["type"].as_str().unwrap_or("");
    let allowed: &[&str] = match kind {
        "open_catalog" => &["type", "id"],
        "scan_table" => &["type", "id", "table"],
        "create_table" => &["type", "id", "name", "columns"],
        "insert_rows" => &["type", "id", "table", "rows"],
        _ => return Err(CustomError::Unsupported(kind.into())),
    };
    if req
        .as_object()
        .is_none_or(|o| o.keys().any(|k| !allowed.contains(&k.as_str())))
    {
        return Err(CustomError::Unsupported("unknown request fields".into()));
    }
    let string = |key: &str| {
        req[key]
            .as_str()
            .ok_or_else(|| CustomError::Schema(format!("{key} must be a string")))
    };
    match kind {
        "open_catalog" => send(json!({"type":"catalog","id":id,"tables":tables(db)}))?,
        "create_table" => {
            let columns: Vec<Column> = serde_json::from_value(req["columns"].clone())
                .map_err(|e| CustomError::Schema(e.to_string()))?;
            db.create_table(string("name")?.into(), columns)?;
            send(json!({"type":"ok","id":id}))?;
        }
        "insert_rows" => {
            let rows: Vec<Vec<Value>> = serde_json::from_value(req["rows"].clone())
                .map_err(|e| CustomError::Schema(e.to_string()))?;
            let count = db.insert_rows(string("table")?, &rows)?;
            send(json!({"type":"ok","id":id,"count":count}))?;
        }
        "scan_table" => {
            let name = string("table")?;
            let columns = db
                .tables()
                .into_iter()
                .find(|t| t.table_name() == name)
                .ok_or_else(|| CustomError::Schema(format!("unknown table '{name}'")))?
                .columns()
                .to_vec();
            let rows = db.scan_table(name)?;
            if rows.is_empty() {
                send(json!({"type":"rows","id":id,"columns":columns,"batch":[],"done":true}))?;
            }
            for (i, batch) in rows.chunks(256).enumerate() {
                send(
                    json!({"type":"rows","id":id,"columns":columns,"batch":batch,"done":(i+1)*256>=rows.len()}),
                )?;
            }
        }
        _ => unreachable!(),
    }
    Ok(())
}
fn bridge(db: &mut Database) -> Result<(), Box<dyn std::error::Error>> {
    send(
        json!({"type":"hello","protocol":1,"min_protocol":1,"engine":"kb_db","engine_version":env!("CARGO_PKG_VERSION"),"format_version":1}),
    )?;
    let stdin = io::stdin();
    let mut input = stdin.lock();
    let mut read = || -> Result<Option<Value>, Box<dyn std::error::Error>> {
        let mut line = String::new();
        if input
            .by_ref()
            .take(8 * 1024 * 1024 + 1)
            .read_line(&mut line)?
            == 0
        {
            return Ok(None);
        }
        if line.len() > 8 * 1024 * 1024 {
            return Err("protocol line exceeds 8 MiB".into());
        }
        Ok(Some(serde_json::from_str(&line)?))
    };
    let ready = read()?.ok_or("missing ready handshake")?;
    if ready != json!({"type":"ready","protocol":1}) {
        return Err("protocol mismatch: expected ready protocol 1".into());
    }
    while let Some(req) = read()? {
        if let Err(error) = request(db, &req) {
            send(
                json!({"type":"error","id":req["id"],"code":code(&error),"message":error.to_string()}),
            )?;
        }
    }
    Ok(())
}
fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let bridge_mode = args.iter().any(|a| a == "--bridge");
    let path = args
        .iter()
        .position(|a| a == "--db")
        .and_then(|i| args.get(i + 1));
    let Some(path) = path else {
        eprintln!(
            "Usage: kb_db --db /absolute/file.db [--bridge | dump-catalog | scan TABLE | dump-page N | create-table NAME COLUMNS_JSON | insert TABLE ROWS_JSON]"
        );
        std::process::exit(74)
    };
    if !Path::new(path).is_absolute() {
        eprintln!("--db must be absolute");
        std::process::exit(74);
    }
    let mut db = match Database::new(path) {
        Ok(db) => db,
        Err(e) => {
            eprintln!("{e}");
            if bridge_mode {
                let _ =
                    send(json!({"type":"error","id":null,"code":code(&e),"message":e.to_string()}));
            }
            std::process::exit(101);
        }
    };
    if bridge_mode {
        if let Err(e) = bridge(&mut db) {
            eprintln!("{e}");
            std::process::exit(74);
        }
        return;
    }
    let commands: Vec<_> = args
        .iter()
        .enumerate()
        .filter(|(i, _)| args[*i] != "--db" && (*i == 0 || args[*i - 1] != "--db"))
        .map(|(_, a)| a.as_str())
        .collect();
    let result = (|| -> Result<Value, Box<dyn std::error::Error>> {
        Ok(match commands.as_slice() {
            ["dump-catalog"] => tables(&db),
            ["scan", table] => json!(db.scan_table(table)?),
            ["dump-page", no] => json!(db.dump_page(no.parse()?)?.to_vec()),
            ["create-table", name, columns] => {
                db.create_table((*name).into(), serde_json::from_str(columns)?)?;
                json!({"ok":true})
            }
            ["insert", table, rows] => {
                json!({"count":db.insert_rows(table, &serde_json::from_str::<Vec<Vec<Value>>>(rows)?)?})
            }
            _ => return Err("unknown CLI command".into()),
        })
    })();
    match result {
        Ok(value) => println!("{}", value),
        Err(e) => {
            eprintln!("{e}");
            std::process::exit(1);
        }
    }
}
