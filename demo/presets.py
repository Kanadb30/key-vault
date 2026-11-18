"""Shared, real queries for the console and demo launcher."""

PRESETS = [
    {
        "id": "pushdown",
        "label": "Join + predicate pushdown",
        "description": "Compare 12 candidate pairs with 6 after pushdown.",
        "source": (
            "SELECT student.name, department.dept_name\n"
            "FROM student\n"
            "JOIN department ON student.dept_id = department.id\n"
            "WHERE student.marks > 80;"
        ),
    },
    {
        "id": "starter",
        "label": "Starter query",
        "description": "Scan, filter, and project without a join.",
        "source": "SELECT name\nFROM student\nWHERE marks > 80;",
    },
    {
        "id": "both-inputs",
        "label": "Filter both join inputs",
        "description": "Push one term left and one term right.",
        "source": (
            "SELECT student.name, department.dept_name\n"
            "FROM student\n"
            "JOIN department ON student.dept_id = department.id\n"
            "WHERE student.marks > 80\n"
            "AND department.dept_name <> 'ECE';"
        ),
    },
    {
        "id": "unknown-column",
        "label": "Unknown column",
        "description": "A designed semantic error with a source span.",
        "source": "SELECT grade FROM student;",
    },
    {
        "id": "ambiguous",
        "label": "Ambiguous reference",
        "description": "See why an unqualified id cannot be bound.",
        "source": (
            "SELECT id\nFROM student\n"
            "JOIN department ON student.dept_id = department.id;"
        ),
    },
]
