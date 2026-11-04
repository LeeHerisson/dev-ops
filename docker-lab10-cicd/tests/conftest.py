import pytest

from app.main import app, todos


@pytest.fixture
def client():
    todos.clear()
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client
