# Six-minute demonstration

## Before presenting

```bash
uv pip install -r requirements.txt
make build
make test
make demo-bundles
PLAYWRIGHT_CHROMIUM_EXECUTABLE=/path/to/chromium make test-console
bash demo/run_demo.sh
```

Open the **printed** URL, normally `http://127.0.0.1:8001/`.
`/api/health` must identify `app: sql-compiler`, not another project's API.
Keep the canonical fixture backend selected for the graded walkthrough.

## Walkthrough

| Time | Evidence |
| --- | --- |
| 0:00–1:30 | SQL tab, starter preset: grammar, tokens, AST, two result rows. |
| 1:30–3:00 | Join preset: bound references; explain why unqualified id is ambiguous. |
| 3:00–5:30 | Pushdown: same predicate moves left. Candidate pairs 12→6; left rows 4→2; result rows unchanged. |
| 5:30–6:00 | Unknown-column preset: source span; SQLite verification on a valid query. |

Exactly two rehearsed live edits: a valid `marks > 90` query, then
`SELECT grade FROM student;`. Presets cover the rest. Replay backup:
**Load bundle** → a JSON file under `demo/bundles/`; the UI labels it recorded.

## Portfolio extension

Use the default example in Builder, Natural language, and Elastic DSL.
Each returns Asha/CSE and Meera/ECE through the same IR. Inspect generated SQL,
the NL token stream, surface AST, catalog-lowering evidence, and a DSL JSON-path rejection. Select **Rust kb_db** storage
and rerun; measured join work remains 12→6 because Python still owns operators.

NL extension example: type
`show student names and department names and marks where marks > 80`.
Unlike the old template frontend, this composes a third projection. It returns
Asha/CSE/91 and Meera/ECE/86. Change the verb, field list, or comparison phrase;
inspect the actual NL tokens and both ASTs. The supported grammar and limits
are documented in `docs/nl_language.md`.

Data extension example: switch **Dataset** to *Classroom · 60 students* and
rerun the same join — candidate pairs become 360→138 with 23 result rows.
Then add a row under **student** (for example `5, Zara, 95, 20`) and query it
from any backend, including Rust kb_db. **Reset** restores the pristine set;
restarting the server also does. Inserts are validated against the catalog and
rejected with designed errors, never guessed.

Native persistence example:

```bash
key-vault/target/debug/kb_db --db /absolute/demo.db dump-catalog
```

The app's seeded database is intentionally temporary; use the native CLI with
an explicit database path for persistence experiments.

## CLI backup

`make demo` prints the graded walkthrough without a browser or Rust.

```bash
uv run python cli.py "show name from student where marks > 80" --frontend nl
uv run python cli.py "SELECT name FROM student WHERE marks > 80;" --backend kb_db
```

Automated startup checks are not a substitute for rehearsing the actual
projector/browser setup twice. Reboot and projector rehearsals remain manual.
