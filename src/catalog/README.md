# Schema catalog

## Interface

TableMetadata contains a table ID, data-chain head, name, and ordered columns.
CatalogManager assigns IDs; its recovery-only add path restores persisted IDs.
Catalog provides lookup and iteration.

## Invariants

IDs and names are unique, and distinct collision variants are returned.
Database/codec validate names, column order/types, and persisted record bounds.
Only the normal create path advances the next table ID.

## Side effects

Local metadata mutation only; Database owns catalog-page persistence.
