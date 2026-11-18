"""Core value types shared by sql_compiler, storage, and frontends.

This is the tiny dependency-free module of the dependency-direction rule:
core imports nothing project-local; sql_compiler and storage may import core;
storage must never import sql_compiler; frontends/api depend on both.

Contracts: docs/adapter.md, docs/bundle_schema.md (frozen v1).
Invariants: table/column names are lowercase; Relation rows are positional
and hashable; values are int (INTEGER) or str (TEXT), never None.
Side effects: none.
"""
from core.types import Column, Relation, SchemaRegistry, TableSchema, Type

__all__ = ["Column", "Relation", "SchemaRegistry", "TableSchema", "Type"]
