//! Normative format: project/docs/format_v1.md. Bounds checked before slicing.
use crate::catalog::table::{TableId, TableMetadata};
use crate::error::{CustomError, Result};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::collections::HashSet;

#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum ColumnType {
    INTEGER,
    TEXT,
}

#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Column {
    pub name: String,
    #[serde(rename = "type")]
    pub column_type: ColumnType,
}

pub fn validate_schema(name: &str, columns: &[Column]) -> Result<()> {
    fn identifier(name: &str) -> bool {
        let mut chars = name.bytes();
        matches!(chars.next(), Some(b'a'..=b'z' | b'_'))
            && chars.all(|c| c.is_ascii_lowercase() || c.is_ascii_digit() || c == b'_')
    }
    let mut names = HashSet::new();
    if !identifier(name)
        || columns.is_empty()
        || columns.len() > u16::MAX as usize
        || columns
            .iter()
            .any(|c| !identifier(&c.name) || !names.insert(&c.name))
    {
        return Err(CustomError::Schema(
            "lowercase identifiers and nonempty distinct columns required".into(),
        ));
    }
    Ok(())
}

fn put_string(out: &mut Vec<u8>, text: &str) -> Result<()> {
    let len = u16::try_from(text.len()).map_err(|_| CustomError::RecordTooLarge)?;
    out.extend_from_slice(&len.to_be_bytes());
    out.extend_from_slice(text.as_bytes());
    Ok(())
}
struct Reader<'a> {
    data: &'a [u8],
    pos: usize,
}
impl<'a> Reader<'a> {
    fn take(&mut self, n: usize) -> Result<&'a [u8]> {
        let bytes = self
            .data
            .get(
                self.pos
                    ..self
                        .pos
                        .checked_add(n)
                        .ok_or_else(|| CustomError::Corrupt("length overflow".into()))?,
            )
            .ok_or_else(|| CustomError::Corrupt("truncated record".into()))?;
        self.pos += n;
        Ok(bytes)
    }
    fn u16(&mut self) -> Result<u16> {
        Ok(u16::from_be_bytes(self.take(2)?.try_into()?))
    }
    fn u32(&mut self) -> Result<u32> {
        Ok(u32::from_be_bytes(self.take(4)?.try_into()?))
    }
    fn string(&mut self) -> Result<String> {
        let n = self.u16()? as usize;
        String::from_utf8(self.take(n)?.to_vec())
            .map_err(|_| CustomError::Corrupt("invalid UTF-8".into()))
    }
    fn finish(&self) -> Result<()> {
        if self.pos != self.data.len() {
            return Err(CustomError::Corrupt("trailing record bytes".into()));
        }
        Ok(())
    }
}
pub fn encode_catalog(table: &TableMetadata) -> Result<Vec<u8>> {
    let mut out = Vec::new();
    out.extend_from_slice(&table.table_id().id().to_be_bytes());
    out.extend_from_slice(&table.start_page().to_be_bytes());
    out.extend_from_slice(&(table.columns().len() as u16).to_be_bytes());
    for c in table.columns() {
        put_string(&mut out, &c.name)?;
        out.push(if c.column_type == ColumnType::INTEGER {
            0
        } else {
            1
        });
    }
    put_string(&mut out, table.table_name())?;
    if out.len() > 4080 {
        return Err(CustomError::RecordTooLarge);
    }
    Ok(out)
}
pub fn decode_catalog(data: &[u8]) -> Result<TableMetadata> {
    let mut r = Reader { data, pos: 0 };
    let id = r.u32()?;
    let start = r.u32()?;
    let count = r.u16()?;
    let mut columns = Vec::new();
    for _ in 0..count {
        let name = r.string()?;
        let column_type = match r.take(1)?[0] {
            0 => ColumnType::INTEGER,
            1 => ColumnType::TEXT,
            _ => return Err(CustomError::Corrupt("unknown column type".into())),
        };
        columns.push(Column { name, column_type });
    }
    let name = r.string()?;
    r.finish()?;
    validate_schema(&name, &columns).map_err(|e| CustomError::Corrupt(e.to_string()))?;
    Ok(TableMetadata::new(TableId::new(id), start, name, columns))
}
pub fn encode_row(columns: &[Column], row: &[Value]) -> Result<Vec<u8>> {
    if columns.len() != row.len() {
        return Err(CustomError::Schema("row width differs from schema".into()));
    }
    let mut out = Vec::new();
    for (column, value) in columns.iter().zip(row) {
        match column.column_type {
            ColumnType::INTEGER => out.extend_from_slice(
                &value
                    .as_i64()
                    .ok_or_else(|| CustomError::Schema(format!("{} requires i64", column.name)))?
                    .to_be_bytes(),
            ),
            ColumnType::TEXT => put_string(
                &mut out,
                value
                    .as_str()
                    .ok_or_else(|| CustomError::Schema(format!("{} requires TEXT", column.name)))?,
            )?,
        }
    }
    if out.len() > 4080 {
        return Err(CustomError::RecordTooLarge);
    }
    Ok(out)
}
pub fn decode_row(columns: &[Column], data: &[u8]) -> Result<Vec<Value>> {
    let mut r = Reader { data, pos: 0 };
    let mut row = Vec::new();
    for c in columns {
        row.push(match c.column_type {
            ColumnType::INTEGER => Value::from(i64::from_be_bytes(r.take(8)?.try_into()?)),
            ColumnType::TEXT => Value::from(r.string()?),
        });
    }
    r.finish()?;
    Ok(row)
}
