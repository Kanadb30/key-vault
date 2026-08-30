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
│ catalog_page_no   4 bytes    │
├──────────────────────────────┤
│ FREE SPACE                   │
└──────────────────────────────┘