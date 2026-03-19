# demo/vulnerable_app.py
# ⚠️  INTENTIONALLY VULNERABLE — for SDLC Intelligence Agent demo only.
# This file exists to trigger the Security Agent's findings.
# Do NOT use any of this code in production.

import os
import sqlite3
import subprocess

# VULNERABILITY: Hardcoded credentials (CRITICAL)
API_KEY = "sk-prod-xK9mN2pL8qR4tY6wZ1aB3cD5eF7gH0j"
DB_PASSWORD = "admin123!"
AWS_SECRET = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"

def get_user(username: str):
    # VULNERABILITY: SQL injection via string interpolation (CRITICAL)
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    query = "SELECT * FROM users WHERE username = '" + username + "'"
    cursor.execute(query)
    return cursor.fetchone()


def run_report(report_name: str):
    # VULNERABILITY: Command injection via subprocess with user input (CRITICAL)
    result = subprocess.run(
        f"python reports/{report_name}.py",
        shell=True,
        capture_output=True,
    )
    return result.stdout


def evaluate_filter(expr: str):
    # VULNERABILITY: eval() with unsanitised user input (HIGH)
    return eval(expr)


def get_file(path: str):
    # VULNERABILITY: Path traversal — no sanitisation (HIGH)
    with open(path, "r") as f:
        return f.read()


def make_request(url: str):
    import requests
    # VULNERABILITY: SSRF — fetches arbitrary user-supplied URL (HIGH)
    # No allowlist, no block of internal IPs
    return requests.get(url, verify=False).text  # also disables TLS verification


def login(username: str, password: str):
    # VULNERABILITY: No rate limiting, no lockout, plaintext password comparison (MEDIUM)
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    query = f"SELECT * FROM users WHERE username='{username}' AND password='{password}'"
    cursor.execute(query)
    user = cursor.fetchone()
    if user:
        # VULNERABILITY: Predictable session token (MEDIUM)
        import hashlib
        token = hashlib.md5(username.encode()).hexdigest()
        return {"token": token, "user": user}
    return None
