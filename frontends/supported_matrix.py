SUPPORTED = {
    "version": 1,
    "types": {"INTEGER": ["=", "<>", "<", "<=", ">", ">="], "TEXT": ["=", "<>"]},
    "max_joins": 1,
    "conjunction": "AND",
    "unsupported": ["OR", "ORDER BY", "LIMIT", "aggregates", "NULL", "multiple joins"],
    "dsl_rejected": ["should", "must_not", "nested bool", "wildcards", "aggregations", "boolean values"],
}
