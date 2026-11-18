# Natural-language query compiler

The NL frontend is a **controlled natural-language compiler**, not a sentence
template matcher and not an LLM. Grammar productions compose independently:
changing the verb, number/order of selected fields, source tables, or filters
does not require adding a new sentence pattern.

## Compiler path

```text
original NL source
  → basic lexer (keywords, words, qualified references, numbers, strings)
  → strict LALR parser
  → typed NL AST
  → catalog-aware semantic lowering
  → shared Select AST
  → existing binder → logical IR → pushdown → Python execution
```

The authoritative executable grammar is
[`frontends/nl_grammar.lark`](../frontends/nl_grammar.lark). The parser uses Lark
with `lexer="basic"`, `parser="lalr"`, `strict=True`, and propagated positions.
The NL AST is defined separately in `frontends/nl_ast.py`. It represents field
phrases, source clauses, comparisons, inclusive ranges, and their source spans.

NL lowering constructs `sql_compiler.ast_nodes.Select` directly. Generated SQL
is shown for explanation, but **is not reparsed to implement NL semantics**.
The existing binder remains responsible for scope, ambiguity, type/operator,
and signed-64-bit checks.

## The requested example

```text
show student names and department names and marks where marks > 80
```

```sql
SELECT student.name, department.dept_name, student.marks
FROM student
JOIN department ON student.dept_id = department.id
WHERE student.marks > 80;
```

Fixture results:

| name | dept_name | marks |
| --- | --- | --- |
| Asha | CSE | 91 |
| Meera | ECE | 86 |

All three storage backends use the same AST/IR. The join work is still 12→6.

## Composable syntax

Simplified structure (the linked Lark file is normative):

```text
query       := [please] command [me] projection [source] [filters] [punctuation]
command     := show | list | display | get | find | give | select | fetch
projection  := [all] field { ("," ["and"] | "and") field }
field       := [the] words
             | [the] table.column
             | [the] words "of" [the] table
             | [the] table "'s" words
source      := from [the] table [ (and | join) [the] table [on equality] ]
filters     := (where | with | whose) comparison { and comparison }
comparison  := field [is | are] operator literal
             | field (is | are) literal
             | field [is | are] between literal and literal
```

Commands/keywords/identifiers are case-insensitive. Text values retain case.
Final `.`, `;`, `?`, or `!` is optional. Articles, politeness, and plural schema
nouns are syntax/alias rules—not whole-query regular expressions.

Field lists preserve order and duplicates. Examples:

- `show student names, department names, and marks where marks above 80`
- `please give me the names and marks from students with the marks > 80.`
- `list names of students whose marks are between 80 and 90`
- `display the student's names where marks are at least 81`
- `get student.name and student.marks from student where name is not "Ravi"`
- `show all students where marks > 80`

Selecting a whole table, or `all columns/fields from <table>`, expands to an
explicit ordered column list. `all` does not mean DISTINCT or remove duplicates.

### Comparison operators

| Shared operator | Accepted examples |
| --- | --- |
| `>` | `>`, `above`, `over`, `greater than`, `more than` |
| `>=` | `>=`, `at least`, `no less than`, `greater than or equal to` |
| `<` | `<`, `below`, `under`, `less than` |
| `<=` | `<=`, `at most`, `no more than`, `less than or equal to` |
| `=` | `=`, `equal to`, `equals`, `exactly`, `is 80` |
| `<>` | `<>`, `!=`, `not equal to`, `is not` |

Optional `is`/`are` may precede an operator. `between 80 and 90` lowers to two
AND terms: `>= 80` and `<= 90`. The AND inside BETWEEN is parsed structurally,
not confused with an additional predicate. OR is allowed inside the single
phrase “greater/less than or equal to”, **not** as a logical disjunction.

Literals are signed integers or quoted text. Single quotes use SQL-style `''`;
double quotes use JSON escapes. Bare text values, floats, booleans, and NULLs
are not guessed or coerced. TEXT comparisons still allow only `=` and `<>`.

## Catalog resolution and join inference

`prepare(source, registry=..., relationships=...)` receives schema metadata
from the composition root. The frontend imports no storage.

- Canonical names and space-separated underscore names are recognized.
- Conservative singular/plural variants are derived from schema nouns.
- An explicit table qualifier supplies context: `department names` can resolve
  the sole `dept_name` field. Ambiguous suffix aliases are rejected.
- Exact canonical column aliases take precedence over friendly suffix aliases.
- With no FROM, uniquely resolved field references establish the needed tables.
  Inferred table order follows catalog order for deterministic plans.
- Explicit FROM defines the scope; NL does not silently add another table.
- Bare `id` in a two-table scope remains ambiguous for the shared binder.

The fixture relationship is explicitly declared in `compose.NL_RELATIONSHIPS`:

```text
student.dept_id = department.id
```

Inference requires **exactly one declared relationship** between the two
required tables. It never invents an `id = id` join. Missing or multiple possible
relationships produce `NL_JOIN_REQUIRED`. An explicit ON works without metadata:

```text
show student names and department names
from student join department
on student.dept_id equals department.id
```

The same lowering is tested on unrelated employee/team schemas, including
plural `salaries`; student/department sentences are not built into the parser.

## Inspector artifacts and diagnostics

The Tokens stage shows original NL lexemes (`COMMAND(show)`, `WORD(student)`,
etc.), not generated SQL tokens. AST shows both the typed NL surface tree and
the lowered shared query tree. The grammar and catalog/join evidence are
inspectable. Every NL node uses an `nl_span` in the user's original text;
binder errors highlight those words, never a synthetic SQL string.

Malformed sentences return `NL_PARSE_UNEXPECTED_TOKEN` or lexical diagnostics.
Unknown tables, missing table context, ambiguous aliases, and missing joins
have explicit `NL_*` diagnostics. Shared binding errors retain their normal
`BIND_*` codes and native NL source spans. No execution occurs after a failure.

Old template code and its TOML registry have been removed. Legacy template-slot
locators can still be displayed when replaying old saved bundles; they are not
a runtime fallback. Restart an older backend after updating; the workspace
advertises NL language version 1 and the console detects missing support.
Regenerate the current NL replay with
`uv run python -m demo.generate --only nl`.

## Deliberate boundaries

This is not unrestricted English or probabilistic intent recognition. There
are no pronoun resolution, arbitrary synonyms, spelling correction, spelled-out
numbers, OR filters, aggregates, sorting, or more than one join. Use numeric
literals, known schema nouns, and the published grammar. Unclear input fails
with a diagnostic rather than executing a guessed query. Projections and input
filter conditions are capped at 64 each.
