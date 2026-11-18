from sql_compiler.ast_nodes import BuilderNode
from sql_compiler.parser import SQLParser
from . import Prepared
from .common import document, fail, identifier, literal, remap
from .supported_matrix import SUPPORTED


def prepare(source):
    data = document(source)
    loc = lambda node: BuilderNode(node_id=node)
    if set(data) - {"table", "columns", "join", "filters"}:
        fail("BUILDER_UNSUPPORTED", "Builder supports table, columns, one join, and AND filters", loc("query"))
    table = identifier(data.get("table"), loc("table"), qualified=False)
    columns = data.get("columns")
    if not isinstance(columns, list) or not columns or len(columns) > 64:
        fail("BUILDER_COLUMNS", "Select between 1 and 64 columns", loc("columns"))
    sql = "SELECT " + ", ".join(identifier(c, loc("columns")) for c in columns) + " FROM " + table
    join = data.get("join")
    if join is not None:
        if not isinstance(join, dict) or set(join) != {"table", "left", "right"}:
            fail("BUILDER_JOIN", "A join needs table, left, and right column names", loc("join"))
        sql += f" JOIN {identifier(join['table'], loc('join'), qualified=False)} ON {identifier(join['left'], loc('join'))} = {identifier(join['right'], loc('join'))}"
    conditions = data.get("filters", [])
    if not isinstance(conditions, list) or len(conditions) > 64:
        fail("BUILDER_FILTERS", "Use at most 64 AND filters", loc("filters"))
    terms = []
    for i, condition in enumerate(conditions):
        where = loc(f"filters[{i}]")
        if not isinstance(condition, dict) or set(condition) != {"column", "op", "value"}:
            fail("BUILDER_FILTERS", "Each filter needs column, op, and value", where)
        if condition["op"] not in SUPPORTED["types"]["INTEGER"]:
            fail("BUILDER_OPERATOR", "Unsupported comparison operator", where)
        terms.append(f"{identifier(condition['column'], where)} {condition['op']} {literal(condition['value'], where)}")
    if terms:
        sql += " WHERE " + " AND ".join(terms)
    sql += ";"
    def locate(path):
        import re
        match = re.search(r"\.where\[(\d+)\]", path)
        return loc(f"filters[{match[1]}]" if match else "columns" if ".columns" in path else "join" if ".join" in path else "table" if ".from_table" in path else "query")
    ast = remap(SQLParser().parse(sql), locate)
    return Prepared(ast, sql, {"generated_sql": sql, "builder": data})
