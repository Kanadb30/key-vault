# Query frontends

## Interface

`prepare(source)` returns `Prepared(ast, sql, artifact)` for builder, NL, and
Elastic-style DSL inputs. SQL uses the compiler's Lark parser directly.
`supported_matrix.py` publishes the operator/type surface to the console.

Builder input is JSON with `table`, ordered `columns`, optional
`join: {table, left, right}`, and `filters: [{column, op, value}]`.
The visual form authors that structure; Python generates SQL and parses it.

NL is a grammar-based compiler, not a template matcher:

```text
NL text → basic lexer → strict LALR parser → NL AST
        → catalog-aware lowering → shared query AST → binder → IR
```

`nl_grammar.lark` defines the language; `nl_parser.py` exposes real source
tokens and constructs the dataclasses in `nl_ast.py`. `nl_lowering.py`
resolves schema-derived noun forms and declared relationships. Its generated
SQL is a readable artifact, **not** reparsed to implement NL semantics.

`nl_frontend.prepare(source, registry=..., relationships=...)` requires an
injected schema registry. The composition root supplies the fixture catalog
and its declared student/department relationship; no storage is imported here.

Examples, composable rather than whole-sentence matches:

- `show student names and department names and marks where marks > 80`
- `please give me the names and marks from students with the marks above 80.`
- `list names of students whose marks are between 80 and 90`
- `display all students where name is not "Ravi"`

See [`docs/nl_language.md`](../docs/nl_language.md) for syntax, inference,
ambiguity rules, diagnostics, and limits.

DSL example:

```json
{
  "version": 1,
  "table": "student",
  "_source": ["name"],
  "query": {"bool": {"filter": [{"range": {"marks": {"gt": 80}}}]}}
}
```

`term` means equality; `range` supports integer `gt/gte/lt/lte`. A documented
local `join: {table, left, right}` extension expresses the compiler's single
equijoin. This is not a full Elasticsearch API.

## Invariants

No storage imports. All frontends converge on the same AST, binder, IR,
optimizer, and interpreter. Builder reparses generated SQL; NL and DSL lower
directly to the shared AST. Diagnostics retain builder fields, real NL source
spans, or JSON paths. Missing/ambiguous joins are rejected, never guessed from
same-name columns.
OR/should, must_not, nested bool, wildcards, aggregates, booleans, floats, and
NULLs are rejected rather than silently dropped.

## Side effects

Loads the local Lark grammar. No network calls or LLMs.
