So i have two page_layouts in my mind. one that i have read about and that i feel will fit in this siple db and is easy to implement.

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
    
