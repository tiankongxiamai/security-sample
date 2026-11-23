"""
A deliberately vulnerable Flask app, used only to demonstrate security scanners.
Every flaw below is intentional and marked with "VULN". Never deploy this.
"""
import sqlite3
import subprocess

from flask import Flask, request

app = Flask(__name__)

# VULN 1 (SAST): hard-coded secrets in source code
app.config["SECRET_KEY"] = "super-secret-key-123"
DB_PASSWORD = "admin123"


def get_db():
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE users (id INTEGER, name TEXT, role TEXT)")
    conn.execute("INSERT INTO users VALUES (1, 'alice', 'trader'), (2, 'bob', 'admin')")
    return conn


@app.route("/")
def index():
    return (
        "<h1>Demo trading tools</h1><ul>"
        "<li><a href='/user?name=alice'>Look up a user</a></li>"
        "<li><a href='/hello?name=guest'>Say hello</a></li>"
        "<li><a href='/ping?host=127.0.0.1'>Ping a host</a></li></ul>"
    )


@app.route("/user")
def user():
    name = request.args.get("name", "")
    # VULN 2 (SAST): SQL injection - user input concatenated into the query
    query = "SELECT id, name, role FROM users WHERE name = '" + name + "'"
    rows = get_db().execute(query).fetchall()
    return {"query": query, "rows": rows}


@app.route("/hello")
def hello():
    name = request.args.get("name", "guest")
    # VULN 3 (SAST + DAST): reflected cross-site scripting (XSS)
    return "<p>Hello " + name + "</p>"


@app.route("/ping")
def ping():
    host = request.args.get("host", "127.0.0.1")
    # VULN 4 (SAST): command injection via shell=True
    out = subprocess.run("ping -c 1 " + host, shell=True, capture_output=True, text=True)
    return "<pre>" + out.stdout + "</pre>"


if __name__ == "__main__":
    # VULN 5 (SAST): debug mode on and listening on all interfaces
    app.run(host="0.0.0.0", port=5000, debug=True)
