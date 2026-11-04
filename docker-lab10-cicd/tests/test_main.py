def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_list_is_empty_at_start(client):
    response = client.get("/todos")
    assert response.status_code == 200
    assert response.get_json() == []


def test_add_todo(client):
    response = client.post("/todos", json={"title": "Learn GitHub Actions"})
    assert response.status_code == 201
    assert response.get_json()["title"] == "Learn GitHub Actions"
    assert len(client.get("/todos").get_json()) == 1


def test_add_todo_without_title(client):
    assert client.post("/todos", json={}).status_code == 400
