# Format v1

Authoritative full contract: parent project `docs/format_v1.md`.

Every 4096-byte page starts with the unchanged 14-byte big-endian header:
`page_no:u32 | type:u16 | data_end:u16 | record_count:u16 | next_page:u32`.
Types: start=0, data=1, catalog=2; `u32::MAX` is the no-next sentinel.

Start-page metadata is `next_table_id` at 14, catalog head at 18, ASCII `KBDB`
at 22, and BE u32 format version `1` at 26. Its record area remains empty.
Legacy/missing magic and unsupported versions are refused.

Both catalog and data records are `length:u16 | payload`, advancing by
`length+2`. Catalog payload:
`table_id:u32 | start_page:u32 | col_count:u16 | [name_len:u16 | UTF8 name | type:u8]* | table_name_len:u16 | UTF8 table_name`.
Column type 0=INTEGER, 1=TEXT.

Rows are schema-positional: INTEGER is BE i64; TEXT is BE u16 byte length plus
UTF-8. Maximum payload 4080 bytes. Records do not span pages; pages form chains.
Open validates alignment, headers, record bounds, schema, row chains, and cycles.

## Legacy design notes (v0, not the implemented v1 format)

The original notes below are preserved as design history only.

<!-- So i have two page_layouts in my mind. one that i have read about and that i feel will fit in this siple db and is easy to implement.

1) The one about which i have read about : 
    - Header : PAGE <Page_no> checksum 
    - reamaining size
    - pointers to data and length of data
    - empty space
    - data filled from bottom

2) the one that i feel easy to implement :
    - Header : PAGE <Page_no> data_end record_count
    - data -> size of data , data
    - empty space

        PAGE_SIZE = 4096

┌──────────────────────────────────────┐
│ page_no       4 bytes BE             │
│ data_end      2 bytes BE             │
│ record_count  2 bytes BE             │
├──────────────────────────────────────┤ ← data_end initially = 8
│ record_length 2 bytes BE             │
│ record_data                          │
│ record_length 2 bytes BE             │
│ record_data                          │
│ ...                                  │
├──────────────────────────────────────┤
│              FREE SPACE              │
└──────────────────────────────────────┘
     -->


Updated layout : 

types of pages : 

1) start : page 0
2) catalogs
3) data

catalog :

┌─────────────────────────────────────────────────────────────────────────────┐
│ page_no               4 bytes BE                                            │
│ page_type             2 bytes BE                                            │
│ data_end              2 bytes BE                                            │
│ record_count          2 bytes BE                                            │
│ next_catalog_page_no  4 bytes BE                                            │
├─────────────────────────────────────────────────────────────────────────────┤  ← data_end initially = 14
│ table_id              4 bytes BE                                            │
│ table_start_page_no   4 bytes BE                                            │
│ table_name_size       2 bytes BE                                            │
│ table_name            <table_name_size bytes>                               │
│ ...                                                                         │
│ table_id              4 bytes BE                                            │
│ table_start_page_no   4 bytes BE                                            │
│ table_name_size       2 bytes BE                                            │
│ table_name            <table_name_size bytes>                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                               FREE SPACE                                    │
└─────────────────────────────────────────────────────────────────────────────┘

data :

┌─────────────────────────────────────────────────────────────────────────────┐
│ page_no               4 bytes BE                                            │
│ page_type             2 bytes BE                                            │
│ data_end              2 bytes BE                                            │
│ record_count          2 bytes BE                                            │
│ next_data_page_no     4 bytes BE                                            │
├─────────────────────────────────────────────────────────────────────────────┤  ← data_end initially = 14
│ record_length         2 bytes BE                                            │
│ record_data           <record_length_size bytes>                            │
│ record_length         2 bytes BE                                            │
│ record_data           <record_length_size bytes>                            │
│ ...                                                                         │
│ record_length         2 bytes BE                                            │
│ record_data           <record_length_size bytes>                            │
│ record_length         2 bytes BE                                            │
│ record_data           <record_length_size bytes>                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                               FREE SPACE                                    │
└─────────────────────────────────────────────────────────────────────────────┘

start : 
page_type : 
    - 00 -> start
    - 01 -> catalog
    - 02 -> data
    
Page 0

┌──────────────────────────────┐
│ page_no          4 bytes BE  │
│ page_type        2 bytes BE  │
│ data_end         2 bytes BE  │
│ record_count     2 bytes BE  │
│ next_page_no     4 bytes BE  │
├──────────────────────────────┤
│ DatabaseMetadata             │
│ next_table_id   4 bytes      |
│ catalog_page_no 4 bytes      |
├──────────────────────────────┤
│ FREE SPACE                   │
└──────────────────────────────┘
