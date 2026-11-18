"""Catalog-aware NL AST → shared query AST. Relationships are declared, not guessed."""
from dataclasses import dataclass

from core.types import SchemaRegistry
from sql_compiler import ast_nodes as ast
from sql_compiler.errors import CompilerError, ErrorEnvelope
from . import nl_ast as nl


def _words(name):
    return tuple(name.lower().replace("_", " ").split())


def _forms(words):
    """Conservative inflections of schema nouns; never stem a query arbitrarily."""
    result = {words}
    last = words[-1]
    if last.endswith("ies") and len(last) > 3:
        result.add((*words[:-1], last[:-3] + "y"))
    elif last.endswith(("ches", "shes", "xes", "zes")):
        result.add((*words[:-1], last[:-2]))
    elif last.endswith("s") and not last.endswith(("ss", "us", "is")):
        result.add((*words[:-1], last[:-1]))
    else:
        plural = (last[:-1] + "ies" if last.endswith("y") and len(last) > 1 and last[-2] not in "aeiou"
                  else last + "es" if last.endswith(("s", "x", "z", "ch", "sh")) else last + "s")
        result.add((*words[:-1], plural))
    return result


def _aliases(name, *, suffix=False):
    canonical = {_words(name), (name.lower(),)}
    aliases = {words: 0 for words in canonical}
    for words in canonical:
        for form in _forms(words):
            aliases.setdefault(form, 1)
    if suffix and len(_words(name)) > 1:
        short = (_words(name)[-1],)
        aliases.setdefault(short, 2)
        for form in _forms(short):
            aliases.setdefault(form, 3)
    return aliases


@dataclass(frozen=True)
class _Field:
    owner: str | None
    words: tuple[str, ...]
    entity: bool
    source: nl.Field


class Lowerer:
    def __init__(self, registry: SchemaRegistry, relationships=(), *, source=""):
        self.catalog = registry.tables()
        self.relationships = relationships
        self.source = source
        self.tables = {name: _aliases(name) for name in self.catalog}
        self.evidence = []

    def error(self, code, message, locator):
        raise CompilerError(ErrorEnvelope("parse", code, message, locator.to_dict(), "nl_frontend"))

    def table(self, words, locator):
        words = tuple(word.lower() for word in words)
        matches = [(aliases[words], table) for table, aliases in self.tables.items() if words in aliases]
        if not matches:
            self.error("NL_UNKNOWN_TABLE", f"Unknown table phrase '{' '.join(words)}'. Available tables: {', '.join(self.catalog)}", locator)
        best = min(rank for rank, _ in matches)
        names = [name for rank, name in matches if rank == best]
        if len(names) != 1:
            self.error("NL_AMBIGUOUS_TABLE", "Table phrase is ambiguous: " + ", ".join(names), locator)
        return names[0]

    def describe(self, field):
        words = tuple(word.lower() for word in field.words)
        if field.owner is not None:
            return _Field(self.table(field.owner, field.locator), words, False, field)
        prefixes = [
            (len(alias), -rank, table)
            for table, aliases in self.tables.items() for alias, rank in aliases.items()
            if words[:len(alias)] == alias
        ]
        if prefixes:
            length, score = max((length, score) for length, score, _ in prefixes)
            names = {table for n, rank, table in prefixes if (n, rank) == (length, score)}
            if len(names) != 1:
                self.error("NL_AMBIGUOUS_TABLE", "Qualify this field with an exact table name", field.locator)
            return _Field(next(iter(names)), words[length:], len(words) == length, field)
        return _Field(None, words, words in {("columns",), ("fields",), ("records",)}, field)

    def candidates(self, words, scope):
        matches = [
            (rank, table, column.name)
            for table in scope for column in self.catalog[table].columns
            for alias, rank in _aliases(column.name, suffix=True).items() if alias == words
        ]
        if not matches:
            return []
        best = min(rank for rank, _, _ in matches)
        return [(table, column) for rank, table, column in matches if rank == best]

    def scope(self, query, fields):
        if query.source is not None:
            names = [self.table(table.words, table.locator) for table in query.source.tables]
            if len(set(names)) != len(names):
                self.error("NL_DUPLICATE_TABLE", "A table may appear only once; aliases/self-joins are not supported", query.source.locator)
            return names
        needed = {field.owner for field in fields if field.owner}
        for field in fields:
            if field.owner or field.entity:
                continue
            matches = self.candidates(field.words, self.catalog)
            tables = {table for table, _ in matches}
            if len(tables) == 1:
                needed.update(tables)
        if not needed:
            for field in fields:
                candidates = self.candidates(field.words, self.catalog)
                if len({table for table, _ in candidates}) > 1:
                    self.error("NL_AMBIGUOUS_TABLE",
                        "Cannot infer a table for this field. Add FROM or qualify it: " +
                        ", ".join(f"{table}.{column}" for table, column in candidates), field.source.locator)
            self.error("NL_TABLE_REQUIRED", "Cannot infer a table. Add 'from <table>' or use a known table/column name", query.projection.locator)
        # Stable catalog order, not a guess based on English word order.
        return [table for table in self.catalog if table in needed]

    def column(self, field, scope):
        if field.entity:
            self.error("NL_EXPECTED_COLUMN", "Use a column name in a comparison or join condition, not a whole table", field.source.locator)
        search = [field.owner] if field.owner else scope
        matches = self.candidates(field.words, search)
        if len(matches) > 1:
            columns = {name for _, name in matches}
            if len(columns) == 1 and field.owner is None:
                # Preserve ambiguity for the shared binder's standard diagnostic.
                return ast.ColumnRef(None, next(iter(columns)), field.source.locator)
            self.error("NL_AMBIGUOUS_FIELD",
                "Field phrase is ambiguous. Use an exact name: " +
                ", ".join(f"{table}.{column}" for table, column in matches), field.source.locator)
        if matches:
            owner, column = matches[0]
        else:
            owner, column = field.owner, "_".join(field.words)
        self.evidence.append({
            "phrase": self.source[field.source.locator.char_start:field.source.locator.char_end] if self.source else " ".join(field.source.words),
            "resolved": f"{owner}.{column}" if owner else column,
            "status": "catalog field" if matches else "deferred to shared binder",
            "locator": field.source.locator.to_dict(),
        })
        return ast.ColumnRef(owner, column, field.source.locator)

    def lower(self, query):
        projected = [self.describe(field) for field in query.projection.fields]
        predicates = [self.describe(condition.field) for condition in query.conditions]
        scope = self.scope(query, projected + predicates)
        if len(scope) > 2:
            self.error("NL_TOO_MANY_TABLES", "The shared compiler supports at most one join (two tables)", query.locator)
        columns = []
        for field in projected:
            if field.entity:
                owners = [field.owner] if field.owner else scope
                for owner in owners:
                    columns.extend(ast.ColumnRef(owner, column.name, field.source.locator)
                                   for column in self.catalog[owner].columns)
            else:
                columns.append(self.column(field, scope))
        if len(columns) > 64 or len(query.conditions) > 64:
            self.error("NL_QUERY_TOO_LARGE", "Use at most 64 projected fields and 64 filter conditions", query.locator)
        conditions = []
        for condition, field in zip(query.conditions, predicates):
            column = self.column(field, scope)
            if isinstance(condition, nl.Between):
                terms = [(">=", condition.lower), ("<=", condition.upper)]
            else:
                terms = [(condition.operator.value, condition.literal)]
            for op, literal in terms:
                value = (ast.IntLiteral(literal.value, literal.locator) if literal.kind == "integer"
                         else ast.StrLiteral(literal.value, literal.locator))
                conditions.append(ast.Compare(column, op, value, condition.locator))

        join, relationship = None, None
        if len(scope) == 2:
            if query.source and query.source.on:
                left, right = [self.column(self.describe(field), scope) for field in query.source.on]
                relationship = {"source": "explicit ON", "left": left.name, "right": right.name}
            else:
                matches = {}
                for a, ac, b, bc in self.relationships:
                    if {a, b} == set(scope):
                        matches[frozenset(((a, ac), (b, bc)))] = (a, ac, b, bc)
                if len(matches) != 1:
                    self.error("NL_JOIN_REQUIRED",
                        "Cannot infer a unique join for these tables. Use 'from <table> join <table> on table.column = table.column'",
                        query.source.locator if query.source else query.locator)
                a, ac, b, bc = next(iter(matches.values()))
                left = ast.ColumnRef(a, ac, query.locator)
                right = ast.ColumnRef(b, bc, query.locator)
                relationship = {"source": "declared relationship", "left": f"{a}.{ac}", "right": f"{b}.{bc}"}
            join = ast.JoinClause(scope[1], query.source.tables[1].locator if query.source else query.locator,
                                  left, right, query.source.locator if query.source else query.locator)
        result = ast.Select(tuple(columns), ast.TableRef(scope[0], query.source.tables[0].locator if query.source else query.locator),
                            join, tuple(conditions), query.locator)
        evidence = {"tables": scope, "table_source": "explicit FROM" if query.source else "catalog inference",
                    "fields": self.evidence, "join": relationship}
        return result, evidence


def to_sql(query):
    """Display artifact only. This SQL is never reparsed to implement NL semantics."""
    def column(ref):
        return f"{ref.qualifier}.{ref.name}" if ref.qualifier else ref.name
    def value(literal):
        return str(literal.value) if isinstance(literal, ast.IntLiteral) else "'" + literal.value.replace("'", "''") + "'"
    sql = "SELECT " + ", ".join(column(ref) for ref in query.columns) + " FROM " + query.from_table.name
    if query.join:
        sql += f" JOIN {query.join.table} ON {column(query.join.on_left)} = {column(query.join.on_right)}"
    if query.where:
        sql += " WHERE " + " AND ".join(f"{column(term.column)} {term.op} {value(term.literal)}" for term in query.where)
    return sql + ";"
