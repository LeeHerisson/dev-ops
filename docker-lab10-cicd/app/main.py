from threading import Lock

from flask import Flask, jsonify, request

app = Flask(__name__)
todos = []
lock = Lock()


@app.get("/health")
def health():
    return jsonify(status="OK")


@app.get("/todos")
def list_todos():
    with lock:
        return jsonify(list(todos))


@app.post("/todos")
def add_todo():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error="JSON object is required"), 400
    title = data.get("title")
    if not isinstance(title, str) or not title.strip():
        return jsonify(error="title is required"), 400
    title = title.strip()
    if len(title) > 2000:
        return jsonify(error="title is too long"), 400
    with lock:
        todo = {"id": len(todos) + 1, "title": title, "done": False}
        todos.append(todo)
    return jsonify(todo), 201


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
