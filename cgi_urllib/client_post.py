"""Client-side HTTP POST example using urllib.

Start the CGI server first:
    py server.py

Then run:
    py client_post.py
"""

import json
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


CGI_URL = "http://localhost:8000/cgi-bin/process_user.cgi"
EMAIL_PATTERN = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")


def validate(mode, name, email, password, role, department, semester):
    errors = []

    if mode not in {"login", "register"}:
        errors.append("Mode must be login or register.")

    if role not in {"student", "faculty", "admin"}:
        errors.append("Role must be student, faculty, or admin.")

    if mode == "register" and not name.strip():
        errors.append("Name is required.")

    if not email.strip():
        errors.append("Email or admin ID is required.")
    elif role != "admin" and not EMAIL_PATTERN.match(email):
        errors.append("Invalid email format.")

    if not password.strip():
        errors.append("Password is required.")
    elif mode == "register" and len(password.strip()) < 4:
        errors.append("Password must contain at least 4 characters.")

    if mode == "register" and role == "admin":
        errors.append("Admin registration is not allowed.")

    if mode == "register" and not department.strip():
        errors.append("Department is required.")

    if mode == "register" and role == "student" and not semester.strip():
        errors.append("Semester is required for students.")

    return errors


def main():
    mode = input("Enter mode (login/register): ").strip().lower()
    role = input("Enter role (student/faculty/admin): ").strip().lower()
    name = ""
    department = ""
    semester = ""

    if mode == "register":
        name = input("Enter your name: ").strip()
        department = input("Enter department: ").strip()
        if role == "student":
            semester = input("Enter semester: ").strip()

    email = input("Enter email or admin ID: ").strip()
    password = input("Enter password: ").strip()

    errors = validate(mode, name, email, password, role, department, semester)
    if errors:
        print("Validation failed:")
        for error in errors:
            print(f"- {error}")
        return

    data = urlencode({
        "mode": mode,
        "name": name,
        "email": email,
        "password": password,
        "role": role,
        "department": department,
        "semester": semester,
    }).encode("utf-8")
    request = Request(
        CGI_URL,
        data=data,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=10) as response:
            body = response.read().decode("utf-8")
    except HTTPError as error:
        print(f"HTTP error: {error.code} {error.reason}")
        return
    except URLError as error:
        print(f"Connection error: {error.reason}")
        print("Tip: start the local CGI server with: python server.py")
        return

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        print("Server response:")
        print(body)
        return

    if payload.get("success"):
        print(payload["message"])
    else:
        print("Server validation failed:")
        for error in payload.get("errors", []):
            print(f"- {error}")


if __name__ == "__main__":
    main()
