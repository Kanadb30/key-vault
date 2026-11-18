from sql_compiler import ast_nodes as ast
from . import Prepared
from .common import document, fail, identifier, literal

OPS = {"gt": ">", "gte": ">=", "lt": "<", "lte": "<="}


def prepare(source):
    data = document(source)
    loc = lambda path: ast.JsonPointer(pointer=path)
    if type(data.get("version")) is not int or data["version"] != 1:
        fail("DSL_VERSION", "Set version to the integer 1", loc("$.version"))
    for key in data:
        if key not in {"version", "table", "_source", "join", "query"}:
            fail("DSL_UNSUPPORTED_OPERATOR", f"Unsupported field '{key}'", loc(f"$.{key}"))
    table = identifier(data.get("table"), loc("$.table"), qualified=False)
    def column(name, path):
        name = identifier(name, loc(path))
        parts = name.split(".")
        return ast.ColumnRef(parts[0] if len(parts) == 2 else None, parts[-1], loc(path))
    columns = data.get("_source")
    if not isinstance(columns, list) or not columns or len(columns) > 64:
        fail("DSL_PROJECTION", "_source must list between 1 and 64 columns", loc("$._source"))
    projection = tuple(column(name, f"$._source[{i}]") for i, name in enumerate(columns))
    join, join_sql = None, ""
    if "join" in data:
        j = data["join"]
        if not isinstance(j, dict) or set(j) != {"table", "left", "right"}:
            fail("DSL_JOIN", "join needs table, left, and right", loc("$.join"))
        name = identifier(j["table"], loc("$.join.table"), qualified=False)
        join = ast.JoinClause(name, loc("$.join.table"), column(j["left"], "$.join.left"), column(j["right"], "$.join.right"), loc("$.join"))
        join_sql = f" JOIN {name} ON {identifier(j['left'])} = {identifier(j['right'])}"
    query = data.get("query", {"bool": {"filter": []}})
    if not isinstance(query, dict) or set(query) != {"bool"} or not isinstance(query["bool"], dict):
        fail("DSL_UNSUPPORTED_OPERATOR", "query must contain bool.filter", loc("$.query"))
    for key in query["bool"]:
        if key != "filter":
            fail("DSL_UNSUPPORTED_OPERATOR", f"'{key}' is not supported; use bool.filter (AND)", loc(f"$.query.bool.{key}"))
    filters = query["bool"].get("filter", [])
    if not isinstance(filters, list) or len(filters) > 64:
        fail("DSL_FILTER", "bool.filter must be an array of at most 64 terms", loc("$.query.bool.filter"))
    comparisons, sql_terms = [], []
    for i, entry in enumerate(filters):
        path = f"$.query.bool.filter[{i}]"
        if not isinstance(entry, dict) or len(entry) != 1 or next(iter(entry)) not in ("term", "range"):
            fail("DSL_UNSUPPORTED_OPERATOR", "Each filter must be term or range; nested bool and OR are not supported", loc(path))
        kind, body = next(iter(entry.items()))
        if not isinstance(body, dict) or len(body) != 1:
            fail("DSL_FILTER", "Each filter must reference exactly one field", loc(path))
        name, value = next(iter(body.items()))
        path += f".{kind}.{name}"
        ref = column(name, path)
        operators = {"=": value} if kind == "term" else value
        if not isinstance(operators, dict) or not operators:
            fail("DSL_FILTER", "range needs gt, gte, lt, or lte bounds", loc(path))
        for op, bound in operators.items():
            if kind == "range" and (op not in OPS or type(bound) is not int):
                fail("DSL_TYPE_MISMATCH", "range supports only integer gt/gte/lt/lte bounds", loc(path + "." + op))
            op_sql = OPS[op] if kind == "range" else op
            text = literal(bound, loc(path))
            node = ast.IntLiteral(bound, loc(path)) if type(bound) is int else ast.StrLiteral(bound, loc(path))
            comparisons.append(ast.Compare(ref, op_sql, node, loc(path)))
            sql_terms.append(f"{identifier(name)} {op_sql} {text}")
    sql = "SELECT " + ", ".join(identifier(c) for c in columns) + " FROM " + table + join_sql
    sql += (" WHERE " + " AND ".join(sql_terms) if sql_terms else "") + ";"
    select = ast.Select(projection, ast.TableRef(table, loc("$.table")), join, tuple(comparisons), loc("$"))
    return Prepared(select, sql, {"generated_sql": sql, "dsl_version": 1})
