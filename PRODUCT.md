# SQL Query Compiler and Optimizer

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Confirmed: FastAPI with a prebuilt Vite + React + TypeScript console and plain
CSS. Python/Lark owns compilation; the browser renders QueryRun bundles.

## Users

The author demonstrating a third-year Compiler Design project, a course
evaluator following a six-minute walkthrough, and portfolio readers inspecting
the compiler's implementation and evidence.

## Product Purpose

Show how a query becomes an AST, a bound query, and an executable relational
plan; demonstrate predicate pushdown with measured work and verified rows.

## Operating Context

Local, projector-friendly course demo, with a CLI fallback. The canonical
fixture query reduces candidate join pairs from 12 to 6 and returns Asha/CSE
and Meera/ECE. Keep startup small and avoid network dependencies in the demo.

## Capabilities and Constraints

- One shared compiler pipeline and versioned QueryRun bundle.
- SQL, the form-based visual builder, a grammar-based controlled-NL compiler, and the
  Elastic-style DSL are implemented and share the compiler AST and IR.
- NL has its own lexer, LALR grammar, and surface AST. Catalog-aware lowering
  resolves fields and unique declared relationships; it does not use an LLM,
  match complete sentence templates, or guess ambiguous joins.
- Fixture storage, SQLite, and Rust over NDJSON stdio are selectable backends.
  Engine availability is probed at startup and failures remain explicit.
- The console owns a session dataset: two preloaded fixture sets, per-table
  row inserts (form or JSON) applied to all three stores, and a reset.
  Switching datasets rebuilds the stores; restarting the server restores the
  preloaded data. Replay bundles and the CLI stay on immutable default data.
- One optional inner equijoin, AND comparisons, non-null INTEGER/TEXT, signed
  64-bit integers; no OR, aggregates, ordering, or multiple joins in v1.
- Every displayed result, metric, plan, and error comes from the compiler
  bundle. Do not silently manufacture success states or substitute data.

## Brand Commitments

The planned console is Kibana-style: a query workbench and compiler inspector,
not a marketing page. The user confirmed a readable, projector-friendly
inspector as the first-console priority.

## Evidence on Hand

`README.md` contains the graded proposal and fixture dataset.
`tests/spine/` verifies compiler behavior, storage semantics, SQLite checks,
and golden demo evidence. `docs/` contains the frozen v1 contracts.

## Product Principles

1. Keep the graded compiler independent of Rust and the console.
2. Make every headline number traceable to recorded execution evidence.
3. Treat errors as inspectable results with source locations.
4. Distinguish implemented features from planned or unavailable integrations.

## Open Decisions

Deadline and whether the console replaces the original CLI demo medium are
not yet confirmed. They do not block the first console build.
