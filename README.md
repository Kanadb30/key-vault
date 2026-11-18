# SQL Query Compiler and Optimizer

**Compiler Design · B.Tech Year 3 · Project proposal**

## Run the implementation

Four frontends—SQL, a visual builder, grammar-based natural language, and an
Elastic-style DSL—feed one Python compiler and optimizer. Storage is selectable:
fixtures, SQLite, or the Rust `kb_db` engine over a versioned stdio bridge.

This repository includes the complete project. The Rust engine lives in
`key-vault/` as ordinary tracked files, not a submodule; no second clone is
needed. Its Cargo commands now use `--manifest-path key-vault/Cargo.toml`,
or run from the `key-vault/` directory.

```bash
uv venv
uv pip install -r requirements.txt
uv run pytest
uv run python cli.py "SELECT name FROM student WHERE marks > 80;"
make demo
```

Pass `--json` to the CLI to inspect the complete QueryRun bundle, including
tokens, source-located AST, bound references, before/after plans, per-node
counters, result rows, and SQLite evidence. Python tests do not require Rust.
`make test` also builds/tests Rust and runs bridge persistence and the
four-frontend × three-backend matrix. `make test-console` runs browser checks.

### Web console

```bash
make build
bash demo/run_demo.sh
```

Open the URL printed by the launcher, normally **http://127.0.0.1:8001/**.
It selects another free port if the default is occupied, without stopping any
other app. Use `PORT=8010 bash demo/run_demo.sh` to require a particular port.
The demo serves prebuilt static files, not a Vite development server. It supports
all four frontend tabs, storage selection, all seven compiler stages,
before/after plans, measured execution counts, results, SQLite evidence,
diagnostics, generated SQL, NL tokens/AST/lowering evidence, and JSON bundle export/replay.
The Rust process is warmed once at startup when its binary is available; an
unavailable or failed engine never silently switches to fixtures.

The **Data** section owns a session dataset: pick a preloaded set (the 4-row
demo data or a 60-student classroom), insert rows through a per-table form or
pasted JSON, and reset to the pristine rows. Inserts apply to all three
backends, so any engine can query them; restarting the server restores the
preloaded dataset.

For frontend development, run the API with
`uv run uvicorn api.server:app --host 127.0.0.1 --port 8000`
and `npm --prefix console run dev` in another terminal.
See [`console/README.md`](console/README.md) for browser tests and design notes.

### Evidence, contracts, and limits

- [`docs/how_it_works.md`](docs/how_it_works.md): the full narrative — how every
  frontend parses into the shared AST, the seven pipeline stages, verification,
  and the kb_db bridge API, with rendered mermaid diagrams (architecture,
  browser→engine request path, engine lifecycle) tied to the implementing files.
- [`docs/demo_script.md`](docs/demo_script.md): six-minute walkthrough and CLI backup.
- [`frontends/README.md`](frontends/README.md): frontend contracts and DSL surface.
- [`docs/nl_language.md`](docs/nl_language.md): compositional NL grammar, lexer,
  parser, source AST, catalog resolution, and join-inference rules.
- [`docs/protocol.md`](docs/protocol.md), [`docs/format_v1.md`](docs/format_v1.md):
  wire and disk contracts. The engine is append-only, not transactional.
- [`docs/build-status.md`](docs/build-status.md): verification commands and scope.
- `make demo-bundles` regenerates the eight recorded runs under `demo/bundles/`.
  Use **Load bundle** to replay one; it is labeled recorded evidence.

The NL tab compiles controlled natural language using a real lexer and LALR
grammar, not word-for-word templates or an LLM. For example,
`show student names and department names and marks where marks > 80` returns
the two qualifying names, departments, and marks. It supports varied commands,
field lists, plural nouns, quoted text, AND filters, and comparison phrases.
It rejects ambiguity rather than guessing; it is not unrestricted English.
The DSL
is a documented Elastic-style subset with a local `join` extension, not an
Elasticsearch client. All relational operators execute in Python for every
storage backend. Browser integers are limited to JavaScript's safe range; the
CLI supports full signed i64 values.

### Package contracts

`core/` contains shared types; `sql_compiler/` owns semantics; `frontends/`
converts input to AST; `storage/` supplies typed scans; `compose.py` wires them.
`api/` exposes the local service, and `console/` renders compiler evidence.
Each code package has an **Interface / Invariants / Side effects** README.

## Proposal and demo

How does a SQL query become something we can execute? We will compile a small subset of SQL into a relational-algebra plan, rewrite the plan to reduce join work, and run it with a Python interpreter. The plan is our **intermediate representation (IR)** and the tree that the interpreter executes.

| Time | What to show |
| --- | --- |
| 0:00–1:30 | Introduce the starter query and explain the grammar using the SELECT, FROM, and WHERE clauses. |
| 1:30–3:00 | Use the join example to show tokens, the AST, and how names are resolved. |
| 3:00–5:30 | Read the plan trees, trace how the interpreter runs them, and compare join work. |
| 5:30–6:00 | Show the planned error message and explain the SQLite check. |

## 1. Grammar

Start with `SELECT name FROM student WHERE marks > 80;`. Our subset supports one `SELECT` statement, a list of columns, one optional inner equijoin, and an optional `WHERE` with comparisons joined by `AND`.

**Parser rules** (Lark EBNF). `?` means optional, `*` means zero or more repetitions, and `|` separates alternatives. Read `start` first, then expand each clause.

```lark
start: "SELECT"i select_list "FROM"i table_ref join_clause? where_clause? ";"?

select_list: column_ref ("," column_ref)*
table_ref: IDENT
join_clause: "JOIN"i table_ref "ON"i column_ref EQ column_ref
where_clause: "WHERE"i comparison ("AND"i comparison)*

comparison: column_ref (EQ | COMP_OP) literal
column_ref: IDENT ("." IDENT)?
literal: INT | STRING
```

**Lexer rules** define how characters become tokens. The `i` makes keywords case-insensitive. `IDENT` reserves those keywords, and `''` represents an apostrophe inside a string. [Lark grammar reference](https://lark-parser.readthedocs.io/en/stable/grammar.html)

```lark
IDENT: /(?!(?i:select|from|join|on|where|and)\b)[A-Za-z_][A-Za-z0-9_]*/
INT: /[+-]?[0-9]+/
STRING: /'(?:[^'\r\n]|'')*'/
EQ: "="
COMP_OP: /<=|>=|<>|<|>/

%import common.WS
%ignore WS
```

Use `Lark(grammar, parser="lalr", lexer="basic", propagate_positions=True)` to expose a token stream and keep source positions. [Lark API reference](https://lark-parser.readthedocs.io/en/stable/classes.html)

## 2. From SQL to a checked AST

We will use this query for the rest of the walkthrough.

```sql
SELECT student.name, department.dept_name
FROM student JOIN department ON student.dept_id = department.id
WHERE student.marks > 80;
```

```text
SQL → tokens → parse tree → SQL AST → bound AST
    → logical plan → predicate pushdown → Python interpreter → result rows
```

**Lex and parse.** For `WHERE student.marks > 80`, the lexer emits `WHERE`, `IDENT(student)`, `DOT`, `IDENT(marks)`, `COMP_OP(>)`, and `INT(80)`. A Lark `Transformer` turns the parse tree into Python dataclasses. It converts literal text into Python values and keeps source positions on references for diagnostics.

```text
Select
├── columns: [student.name, department.dept_name]
├── from: student
├── join: department on Eq(student.dept_id, department.id)
└── where: [Compare(student.marks, ">", Int(80))]
```

**Bind and validate.** Keep a catalog mapping each table name to its column names and types. Look up every reference in the tables from `FROM` and `JOIN`. An unqualified name must match exactly one column, so plain `id` is ambiguous in the join example. The binder turns `student.marks` into a reference with table `student`, column `marks`, and type `INTEGER`. That table binding tells the optimizer which input a filter depends on.

Use non-null `INTEGER` and `TEXT` columns and signed 64-bit integer literals. Comparisons require matching types, with `=` and `<>` for text and all six operators for integers. The two `ON` columns must have the same type and come from opposite inputs. Store the left input's key first so either operand order works in SQL. Normalize table and column names to lowercase and allow each table to appear once per query.

## 3. Build and optimize the plan

Build `Scan` nodes from the table references, wrap them in `Join` when there are two inputs, add `Filter` for `WHERE`, and finish with `Project` for the select list. The starter query becomes `Project(name, Filter(marks > 80, Scan(student)))`.

```text
Before pushdown                                 After pushdown
Project(name, dept_name)                        Project(name, dept_name)
└── Filter(student.marks > 80)                  └── Join(student.dept_id = department.id)
    └── Join(student.dept_id = department.id)       ├── Filter(student.marks > 80)
        ├── Scan(student)                           │   └── Scan(student)
        └── Scan(department)                        └── Scan(department)
```

**Rewrite rule.** For a `Filter` above an inner `Join`, split the `WHERE` clause into its `AND` terms. For each term, use its bound columns to find the input it depends on. Place that term directly above that input and rebuild the join with the same `ON` condition. Keep the original plan for comparison.

Here `student.marks > 80` depends only on the student row. If a student fails that test, every join pair containing that student would fail it too. Filtering before the join removes those pairs early while preserving the result rows.

## 4. Run the plan in Python

Implement `execute(node, tables, stats)` as a recursive function that returns a list of rows. The root asks each child for its rows, so the scans run before their parent operators. Internally, represent row fields with keys like `("student", "id")` so they stay distinct from `("department", "id")`. Start each run with its own `stats` counter at zero.

| Operator | What the interpreter does |
| --- | --- |
| `Scan(table)` | Read the table's in-memory fixture and attach the table name to each column key. |
| `Filter(terms, child)` | Execute the child once. Keep each row that passes every comparison using its bound column keys. |
| `Join(on, left, right)` | Execute each child once. Loop through every left–right pair, increment `stats.join_pairs` before testing `ON`, and combine the matching rows. |
| `Project(columns, child)` | Execute the child once. Build one tuple per row in select-list order and preserve duplicates. |

Use these same fixtures for both plans and the SQLite check.

```text
student(id, name, marks, dept_id)    department(id, dept_name)
(1, 'Asha',  91, 10)                 (10, 'CSE')
(2, 'Ravi',  80, 20)                 (20, 'ECE')
(3, 'Meera', 86, 20)                 (30, 'ME')
(4, 'Kabir', 67, 30)
```

| Expected trace | Before pushdown | After pushdown |
| --- | --- | --- |
| Student rows reaching the join | 4 | 2 (`Asha` and `Meera`) |
| Candidate pairs tested | 4 × 3 = **12** | 2 × 3 = **6** |
| Rows reaching the final projection | 2 | 2 |

Both plans should return `(Asha, CSE)` and `(Meera, ECE)`. Ravi's mark of 80 fails the strict `>` test. To verify the results, run the source SQL in SQLite and compare both plans' output with SQLite using `Counter(rows)`. This ignores row order and checks how many times each tuple appears.

## 5. Build order and demo evidence

1. **Front end.** Implement the grammar, AST transformer, and binder. Check that `SELECT FROM student;` fails during parsing. Use `SELECT grade FROM student;` to show the planned semantic error below.
2. **Executable IR.** Implement `Scan`, `Filter`, and `Project` first. Show the starter query going from tokens and AST to its plan and the two output rows, `Asha` and `Meera`.
3. **Optimization.** Add the inner join, pushdown rule, and pair counter. Print both plans for the join query and compare their measured counts and result rows.

```text
SELECT grade FROM student;
       ^
Semantic error at 1:8. Unknown column 'grade' in table 'student'.
```
