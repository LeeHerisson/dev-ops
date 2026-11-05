def test_second_todo_has_id_two(client):
    client.post("/todos", json={"title": "First"})
    response = client.post("/todos", json={"title": "Second"})
    assert response.status_code == 201
    assert response.get_json()["id"] == 2


def test_title_is_trimmed(client):
    response = client.post("/todos", json={"title": "  Docker  "})
    assert response.status_code == 201
    assert response.get_json()["title"] == "Docker"


def test_whitespace_title_is_rejected(client):
    assert client.post("/todos", json={"title": "   "}).status_code == 400


def test_json_array_is_rejected(client):
    assert client.post("/todos", json=["invalid"]).status_code == 400


def test_non_string_title_is_rejected(client):
    assert client.post("/todos", json={"title": 42}).status_code == 400


def test_long_title_is_rejected(client):
    assert client.post("/todos", json={"title": "x" * 2001}).status_code == 400


def test_version_reports_commit(client, monkeypatch):
    monkeypatch.setenv("RENDER_GIT_COMMIT", "abc123")
    response = client.get("/version")
    assert response.status_code == 200
    assert response.get_json() == {"commit": "abc123"}
