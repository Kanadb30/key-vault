import json

import pytest
from fastapi.testclient import TestClient

from api.query_service import QueryService
from api.server import create_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("KB_DB_BIN", str(tmp_path / "missing-engine"))
    with TestClient(create_app(dist=tmp_path / "not-built")) as client:
        yield client


def test_health_does_not_claim_a_live_engine(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {
        "v": 1, "app": "sql-compiler", "status": "ok", "backend": "fixtures", "engine_available": False,
    }
    assert response.headers["cache-control"] == "no-store"


def test_workspace_contains_schema_presets_and_real_initial_bundle(client):
    response = client.get("/api/workspace")
    assert response.status_code == 200
    data = response.json()
    assert data["v"] == 1
    assert [table["name"] for table in data["catalog"]] == ["student", "department"]
    assert data["engine"]["available"] is False
    assert [frontend["id"] for frontend in data["frontends"] if frontend["available"]] == ["sql", "builder", "nl", "elastic"]
    assert data["initial_bundle"]["metrics"]["join_pairs_tried"] == {"pre": 12, "post": 6}
    assert data["initial_bundle"]["rows"]["rows"] == [["Asha", "CSE"], ["Meera", "ECE"]]
    assert data["initial_bundle"]["sqlite_cross_check"]["passed"]


def test_query_endpoint_returns_the_same_bundle_contract(client, join_sql):
    response = client.post("/api/query", json={"v": 1, "frontend_id": "sql", "source": join_sql})
    assert response.status_code == 200
    data = response.json()
    assert data["bundle"]["run_schema_version"] == data["v"] == 1
    assert data["bundle"]["inputs"]["verbatim"] == join_sql
    assert data["bundle"]["errors"] == []
    assert data["bundle"]["sqlite_cross_check"]["passed"]


def test_semantic_error_is_a_valid_query_result_not_http_500(client):
    response = client.post("/api/query", json={"source": "SELECT grade FROM student;"})
    assert response.status_code == 200
    assert response.json()["bundle"]["errors"][0]["code"] == "BIND_UNKNOWN_COLUMN"


def test_missing_engine_never_silently_uses_fixtures(client):
    response = client.post("/api/query", json={"source": "SELECT name FROM student;", "backend": "kb_db"})
    assert response.status_code == 200
    data = response.json()
    assert not data["engine"]["available"]
    assert data["bundle"]["provenance"]["backend"] == "kb_db"
    assert data["bundle"]["errors"][0]["code"] == "BRIDGE_UNAVAILABLE"
    assert data["bundle"]["rows"] is None


@pytest.mark.parametrize("frontend", ["sql", "builder", "nl", "elastic"])
def test_all_frontend_requests_work_through_http(client, frontend):
    workspace = client.get("/api/workspace").json()
    response = client.post("/api/query", json={
        "frontend_id": frontend, "source": workspace["examples"][frontend],
    })
    bundle = response.json()["bundle"]
    assert bundle["errors"] == []
    assert bundle["inputs"]["frontend_id"] == frontend
    assert bundle["rows"]["rows"] == [["Asha", "CSE"], ["Meera", "ECE"]]
    assert bundle["sqlite_cross_check"]["passed"]


def test_nl_http_accepts_composed_projection_and_emits_compiler_artifacts(client):
    source = "show student names and department names and marks where marks > 80"
    response = client.post("/api/query", json={"frontend_id": "nl", "source": source})
    assert response.status_code == 200
    bundle = response.json()["bundle"]
    assert bundle["errors"] == []
    assert bundle["rows"]["rows"] == [["Asha", "CSE", 91], ["Meera", "ECE", 86]]
    assert bundle["stages"][0]["artifact"]["tokens"][0]["type"] == "COMMAND"
    assert bundle["stages"][1]["artifact"]["nl_ast"]["projection"]["fields"][2]["words"] == ["marks"]
    assert client.get("/api/workspace").json()["nl_language"]["parser"] == "Lark LALR"


@pytest.mark.parametrize("payload", [
    {}, {"source": ""}, {"source": "a" * 16385}, {"source": 42},
    {"v": 2, "source": "SELECT name FROM student;"},
    {"v": True, "source": "SELECT name FROM student;"},
    {"v": 1.0, "source": "SELECT name FROM student;"},
    {"frontend_id": "unknown", "source": "{}"},
    {"source": "SELECT name FROM student;", "verify": "false"},
    {"source": "SELECT name FROM student;", "backend": "rust"},
])
def test_invalid_requests_return_structured_errors(client, payload):
    response = client.post("/api/query", json=payload)
    assert response.status_code == 422
    assert response.json()["errors"][0]["code"] == "REQUEST_INVALID"
    assert response.json()["errors"][0]["origin"] == "console"
    assert "detail" not in response.json()


def test_bad_json_is_a_structured_error(client):
    response = client.post("/api/query", content="{", headers={"Content-Type": "application/json"})
    assert response.status_code == 422
    assert response.json()["errors"][0]["code"] == "REQUEST_INVALID"


def test_request_body_is_bounded(client):
    response = client.post(
        "/api/query", content=json.dumps({"source": "x" * (129 * 1024)}),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 413
    assert response.json()["errors"][0]["code"] == "REQUEST_TOO_LARGE"


def test_verification_can_be_disabled_over_http(client):
    bundle = client.post("/api/query", json={
        "source": "SELECT name FROM student;", "verify": False,
    }).json()["bundle"]
    assert bundle["sqlite_cross_check"] is None
    assert bundle["stages"][-1]["status"] == "skipped"


@pytest.mark.parametrize("value", [9007199254740992, -9007199254740992, 9223372036854775807])
def test_console_never_silently_rounds_i64_values(client, value):
    bundle = client.post("/api/query", json={
        "source": f"SELECT name FROM student WHERE marks = {value};",
    }).json()["bundle"]
    assert bundle["errors"][0]["code"] == "CONSOLE_INTEGER_PRECISION"
    assert bundle["errors"][0]["origin"] == "console"
    assert bundle["rows"] is None
    assert bundle["plans"] is None


def test_unexpected_service_failure_is_a_structured_500(tmp_path, monkeypatch):
    def fail(*args):
        raise OSError("private filesystem detail")
    monkeypatch.setattr(QueryService, "run", fail)
    with TestClient(create_app(dist=tmp_path / "missing"), raise_server_exceptions=False) as client:
        response = client.post("/api/query", json={"source": "SELECT name FROM student;"})
    assert response.status_code == 500
    assert response.json()["errors"][0]["code"] == "INTERNAL"
    assert "private filesystem detail" not in response.text


def test_insert_endpoint_updates_the_catalog_and_every_backend(client):
    response = client.post("/api/data/insert", json={"v": 1, "table": "student", "rows": [[5, "Zara", 95, 20]]})
    assert response.status_code == 200
    data = response.json()
    assert data["v"] == 1
    assert [table["row_count"] for table in data["catalog"]] == [5, 3]
    query = client.post("/api/query", json={"v": 1, "frontend_id": "nl", "source": "show names from students where marks above 90"})
    assert query.json()["bundle"]["rows"]["rows"] == [["Asha"], ["Zara"]]
    query = client.post("/api/query", json={"v": 1, "backend": "sqlite", "frontend_id": "sql", "source": "SELECT name FROM student WHERE marks > 90;"})
    assert query.json()["bundle"]["rows"]["rows"] == [["Asha"], ["Zara"]]
    assert query.json()["bundle"]["sqlite_cross_check"]["passed"]


def test_insert_endpoint_rejects_bad_rows_with_designed_errors(client):
    cases = [
        ({"v": 1, "table": "ghost", "rows": [[1, "x"]]}, 400, "DATA_UNKNOWN_TABLE"),
        ({"v": 1, "table": "student", "rows": [[5, "Zara", 95]]}, 400, "DATA_INVALID_ROW"),
        ({"v": 1, "table": "student", "rows": [[5, "Zara", 2**60, 20]]}, 400, "DATA_INTEGER_PRECISION"),
        ({"v": 1, "table": "student", "rows": []}, 422, None),
        ({"v": 1, "table": "student", "rows": [[5, "Zara", 95.5, 20]]}, 422, None),
        ({"v": 1, "table": "student", "rows": [[5, "Zara", True, 20]]}, 422, None),
        ({"v": 1, "table": "student", "rows": [[5, "Zara", 95, 20], [6, "Two", 96]]}, 422, None),
        ({"v": 1, "table": "Student", "rows": [[5, "Zara", 95, 20]]}, 422, None),
    ]
    for body, status, code in cases:
        response = client.post("/api/data/insert", json=body)
        assert response.status_code == status, body
        if code:
            assert response.json()["errors"][0]["code"] == code, body
    catalog = client.get("/api/workspace").json()["catalog"]
    assert [table["row_count"] for table in catalog] == [4, 3]  # nothing partially applied


def test_dataset_endpoint_switches_and_reports_choices(client):
    response = client.get("/api/workspace")
    data = response.json()
    assert data["dataset"] == "default-v1"
    assert [item["id"] for item in data["datasets"]] == ["default-v1", "classroom-60"]
    switch = client.post("/api/data/dataset", json={"v": 1, "dataset": "classroom-60"})
    assert switch.status_code == 200
    assert switch.json()["dataset"] == "classroom-60"
    assert [table["row_count"] for table in switch.json()["catalog"]] == [60, 6]
    query = client.post("/api/query", json={"v": 1, "source": "SELECT student.name, department.dept_name FROM student JOIN department ON student.dept_id = department.id WHERE student.marks > 80;"})
    bundle = query.json()["bundle"]
    assert bundle["rows"]["count"] == 23
    assert bundle["metrics"]["join_pairs_tried"] == {"pre": 360, "post": 138}
    assert bundle["sqlite_cross_check"]["passed"]
    bad = client.post("/api/data/dataset", json={"v": 1, "dataset": "nope"})
    assert bad.status_code == 400
    assert bad.json()["errors"][0]["code"] == "DATA_UNKNOWN_DATASET"
    reselect = client.post("/api/data/dataset", json={"v": 1, "dataset": "default-v1"})
    assert reselect.json()["dataset"] == "default-v1"
    assert [table["row_count"] for table in reselect.json()["catalog"]] == [4, 3]


def test_missing_static_build_has_actionable_error(client):
    response = client.get("/")
    assert response.status_code == 503
    assert response.json()["errors"][0]["code"] == "CONSOLE_NOT_BUILT"
    assert "npm" in response.json()["errors"][0]["message"]


def test_serves_prebuilt_static_console(tmp_path):
    (tmp_path / "index.html").write_text("<!doctype html><title>SQL Compiler</title>")
    with TestClient(create_app(dist=tmp_path)) as client:
        response = client.get("/")
        assert response.status_code == 200
        assert "<title>SQL Compiler</title>" in response.text
        assert response.headers["x-content-type-options"] == "nosniff"
        assert client.get("/api/health").json()["status"] == "ok"
