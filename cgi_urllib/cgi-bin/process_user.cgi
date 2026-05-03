#!python
"""Server-side CGI script for the browser-based notes exchange portal."""

import html
import json
import mimetypes
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import threading
import time
import warnings
from types import SimpleNamespace
from urllib.parse import parse_qs

try:
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=DeprecationWarning)
        import cgi
except ModuleNotFoundError:
    class FieldItem:
        def __init__(self, value="", filename="", content=b""):
            self.value = value
            self.filename = filename
            self.content = content

    class FieldStorage:
        """Small FieldStorage replacement for Python 3.13+ demos."""

        def __init__(self):
            self.fields = {}
            method = os.environ.get("REQUEST_METHOD", "").upper()
            content_type = os.environ.get("CONTENT_TYPE", "")

            if method == "GET":
                self.parse_urlencoded(os.environ.get("QUERY_STRING", ""))
                return

            length = int(os.environ.get("CONTENT_LENGTH") or 0)
            body = sys.stdin.buffer.read(length)

            if "multipart/form-data" in content_type:
                self.parse_multipart(body, content_type)
            else:
                self.parse_urlencoded(body.decode("utf-8", errors="replace"))

        def parse_urlencoded(self, raw_data):
            parsed = parse_qs(raw_data, keep_blank_values=True)
            for key, values in parsed.items():
                self.fields[key] = FieldItem(value=values[0] if values else "")

        def parse_multipart(self, body, content_type):
            match = re.search(r"boundary=([^;]+)", content_type)
            if not match:
                return

            boundary = ("--" + match.group(1).strip('"')).encode("utf-8")
            for part in body.split(boundary):
                part = part.strip()
                if not part or part == b"--":
                    continue

                if part.endswith(b"--"):
                    part = part[:-2].strip()

                header_blob, _, content = part.partition(b"\r\n\r\n")
                headers = header_blob.decode("utf-8", errors="replace")
                content = content.rstrip(b"\r\n")
                name_match = re.search(r'name="([^"]+)"', headers)
                if not name_match:
                    continue

                filename_match = re.search(r'filename="([^"]*)"', headers)
                name = name_match.group(1)
                filename = filename_match.group(1) if filename_match else ""
                value = "" if filename else content.decode("utf-8", errors="replace")
                self.fields[name] = FieldItem(value=value, filename=filename, content=content)

        def getfirst(self, field_name, default=""):
            item = self.fields.get(field_name)
            return item.value if item else default

        def __getitem__(self, field_name):
            return self.fields[field_name]

    cgi = SimpleNamespace(FieldStorage=FieldStorage)


EMAIL_PATTERN = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
ADMIN_ID = "admin"
ADMIN_PASSWORD = "admin123"
PROJECT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))
USERS_FILE = os.path.join(DATA_DIR, "users.json")
DATABASE_PATH = os.path.join(PROJECT_DIR, "database", "notes.db")
NOTES_DIR = os.path.join(PROJECT_DIR, "gui", "notes")
TKINTER_APP = os.path.join(PROJECT_DIR, "gui", "app.py")
ALLOWED_EXTENSIONS = {".pdf", ".doc", ".docx", ".ppt", ".pptx", ".txt"}


def get_value(form, field_name):
    value = form.getfirst(field_name, "")
    return value.strip() if isinstance(value, str) else ""


def get_file_item(form, field_name):
    try:
        return form[field_name]
    except Exception:
        return None


def load_users():
    if not os.path.exists(USERS_FILE):
        return []

    try:
        with open(USERS_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    except (OSError, json.JSONDecodeError):
        return []


def save_users(users):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(USERS_FILE, "w", encoding="utf-8") as file:
        json.dump(users, file, indent=2)


def connect_db():
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    return sqlite3.connect(DATABASE_PATH)


def resolve_note_path(file_path):
    if not file_path:
        return ""

    if os.path.isabs(file_path):
        return file_path

    candidates = [
        os.path.join(PROJECT_DIR, "gui", file_path),
        os.path.join(PROJECT_DIR, file_path),
        os.path.join(NOTES_DIR, os.path.basename(file_path)),
    ]

    for candidate in candidates:
        if os.path.exists(candidate):
            return candidate

    return candidates[0]


def setup_db():
    conn = connect_db()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject TEXT,
                title TEXT,
                semester TEXT,
                uploader_name TEXT,
                email TEXT,
                file_link TEXT,
                download_count INTEGER DEFAULT 0
            )
        """)
        conn.commit()
    finally:
        conn.close()


def fetch_notes(email=None):
    setup_db()
    conn = connect_db()
    try:
        cursor = conn.cursor()
        if email:
            cursor.execute("""
                SELECT id, subject, title, semester, uploader_name, email, file_link, download_count
                FROM notes
                WHERE email=?
                ORDER BY id DESC
            """, (email,))
        else:
            cursor.execute("""
                SELECT id, subject, title, semester, uploader_name, email, file_link, download_count
                FROM notes
                ORDER BY id DESC
            """)

        return [
            {
                "id": row[0],
                "subject": row[1] or "",
                "title": row[2] or "",
                "semester": row[3] or "",
                "uploader_name": row[4] or "",
                "email": row[5] or "",
                "file_link": row[6] or "",
                "download_count": row[7] or 0,
            }
            for row in cursor.fetchall()
        ]
    finally:
        conn.close()


def validate_auth(mode, name, email, password, role, department, semester):
    errors = []

    if mode not in {"login", "register"}:
        errors.append("Invalid request mode.")

    if role not in {"student", "faculty", "admin"}:
        errors.append("Role is required.")

    if mode == "register" and not name:
        errors.append("Name is required.")

    if not email:
        errors.append("Email or admin ID is required.")
    elif role != "admin" and not EMAIL_PATTERN.match(email):
        errors.append("Invalid email format.")

    if not password:
        errors.append("Password is required.")
    elif mode == "register" and len(password) < 4:
        errors.append("Password must contain at least 4 characters.")

    if mode == "register" and role == "admin":
        errors.append("Admin registration is not allowed.")

    if mode == "register" and not department:
        errors.append("Department is required.")

    if mode == "register" and role == "student" and not semester:
        errors.append("Semester is required for students.")

    return errors


def wants_json():
    accept_header = os.environ.get("HTTP_ACCEPT", "")
    return "application/json" in accept_header.lower()


def print_json(success, message="", errors=None, role=""):
    print("Content-Type: application/json")
    print()
    print(json.dumps({
        "success": success,
        "message": message,
        "errors": errors or [],
        "role": role,
    }))


def register_user(name, email, password, role, department, semester):
    users = load_users()
    email_key = email.lower()

    if any(user["email"].lower() == email_key for user in users):
        return False, ["This email is already registered."]

    users.append({
        "name": name,
        "email": email,
        "password": password,
        "role": role,
        "department": department,
        "semester": semester if role == "student" else "",
    })
    save_users(users)
    return True, []


def login_user(email, password, role):
    if role == "admin":
        if email.lower() == ADMIN_ID and password == ADMIN_PASSWORD:
            return True, {
                "name": "Admin",
                "email": ADMIN_ID,
                "role": "admin",
                "department": "Administration",
                "semester": "",
            }
        return False, ["Invalid admin credentials."]

    users = load_users()
    email_key = email.lower()
    for user in users:
        if (
            user["email"].lower() == email_key
            and user["password"] == password
            and user["role"] == role
        ):
            return True, user

    return False, ["Invalid email, password, or role."]


def page_start(title):
    print("Content-Type: text/html")
    print()
    print("<!doctype html>")
    print("<html lang='en'><head><meta charset='utf-8'>")
    print("<meta name='viewport' content='width=device-width, initial-scale=1'>")
    print(f"<title>{html.escape(title)}</title>")
    print("<style>")
    print("""
        :root{--navy:#102b57;--blue:#1d5fa7;--gold:#f2b233;--bg:#eef3f8;--line:#d8e0eb;--ink:#172033;--muted:#657085}
        *{box-sizing:border-box}
        body{margin:0;font-family:Segoe UI,Arial,sans-serif;background:var(--bg);color:var(--ink)}
        .top{background:var(--navy);color:white;border-bottom:5px solid var(--gold)}
        .mast{width:min(1120px,calc(100% - 32px));margin:0 auto;padding:20px 0}
        .mast h1{margin:0;font-size:25px}.mast p{margin:6px 0 0;color:#dce8f6}
        .nav{background:#153866}.nav div{width:min(1120px,calc(100% - 32px));margin:0 auto;padding:10px 0;color:#eef5ff;font-weight:700}
        main{width:min(1120px,calc(100% - 32px));margin:24px auto 36px}
        .panel{background:white;border:1px solid var(--line);border-radius:8px;box-shadow:0 18px 44px rgba(23,32,51,.10);margin-bottom:18px}
        .panel h2,.panel h3{margin:0;color:var(--navy)}.panel-head{padding:18px 20px;border-bottom:1px solid var(--line)}
        .panel-body{padding:20px}.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}
        .card{padding:16px;background:#f7f9fc;border:1px solid var(--line);border-radius:6px}.card strong{display:block;color:var(--muted);font-size:13px}.card span{display:block;margin-top:6px;color:var(--navy);font-size:24px;font-weight:800}
        label{display:block;margin:0 0 6px;font-weight:700}input,select{width:100%;height:42px;padding:8px 10px;border:1px solid var(--line);border-radius:5px;font:inherit}
        .form-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:14px}.full{grid-column:1/-1}
        button,.btn{display:inline-block;border:0;border-radius:5px;background:var(--navy);color:white;font:inherit;font-weight:800;padding:10px 14px;text-decoration:none;cursor:pointer}
        .btn-blue{background:var(--blue)}.btn-light{background:#f7f9fc;color:var(--navy);border:1px solid var(--line)}.btn-danger{background:#b42318}
        table{width:100%;border-collapse:collapse}th,td{padding:10px;border-bottom:1px solid var(--line);text-align:left;font-size:14px}th{color:var(--navy);background:#f7f9fc}
        td input,td select{height:36px}.actions{display:flex;gap:8px;align-items:center}.inline-form{display:inline}
        .notice{padding:12px 14px;border-left:4px solid var(--gold);background:#fff7e5;color:#5b4211;margin-bottom:14px}
        .error{padding:12px 14px;border-left:4px solid #b42318;background:#fff1f0;color:#b42318;margin-bottom:14px}
        pre{white-space:pre-wrap;background:#0f172a;color:#e5edf7;padding:16px;border-radius:6px;line-height:1.45}
        .bar{display:flex;justify-content:space-between;gap:12px;align-items:center}.muted{color:var(--muted)}
        @media(max-width:760px){.grid,.form-grid{grid-template-columns:1fr}.bar{display:block}.bar a{margin-top:10px}}
    """)
    print("</style></head><body>")
    print("<header class='top'><div class='mast'>")
    print("<h1>Puducherry Technological University</h1>")
    print("<p>Role-Based Shared Notes Exchange System</p>")
    print("</div><div class='nav'><div>CGI + urllib | Tkinter + SQLite | Synchronization</div></div></header>")
    print("<main>")


def page_end():
    print("</main></body></html>")


def hidden_user_inputs(user):
    return (
        f"<input type='hidden' name='name' value='{html.escape(user.get('name', ''))}'>"
        f"<input type='hidden' name='email' value='{html.escape(user.get('email', ''))}'>"
        f"<input type='hidden' name='role' value='{html.escape(user.get('role', ''))}'>"
    )


def render_table(notes, show_uploader=True):
    print("<table><thead><tr>")
    headers = ["Title", "Subject", "Semester"]
    if show_uploader:
        headers.append("Faculty")
    headers.extend(["Downloads", "Action"])
    for header in headers:
        print(f"<th>{header}</th>")
    print("</tr></thead><tbody>")

    if not notes:
        colspan = len(headers)
        print(f"<tr><td colspan='{colspan}' class='muted'>No notes available yet.</td></tr>")

    for note in notes:
        print("<tr>")
        print(f"<td>{html.escape(note['title'])}</td>")
        print(f"<td>{html.escape(note['subject'])}</td>")
        print(f"<td>{html.escape(note['semester'])}</td>")
        if show_uploader:
            print(f"<td>{html.escape(note['uploader_name'])}</td>")
        print(f"<td>{note['download_count']}</td>")
        print(f"<td><a class='btn btn-light' href='/cgi-bin/process_user.cgi?action=download&note_id={note['id']}'>Download</a></td>")
        print("</tr>")
    print("</tbody></table>")


def render_faculty_notes_table(notes, user):
    print("<table><thead><tr>")
    for header in ["Title", "Subject", "Semester", "Downloads", "Update", "Delete"]:
        print(f"<th>{header}</th>")
    print("</tr></thead><tbody>")

    if not notes:
        print("<tr><td colspan='6' class='muted'>You have not uploaded notes yet.</td></tr>")

    for note in notes:
        update_form_id = f"update-note-{note['id']}"
        delete_form_id = f"delete-note-{note['id']}"
        print("<tr>")
        print(f"<td><input form='{update_form_id}' name='title' value='{html.escape(note['title'])}' required></td>")
        print(f"<td><input form='{update_form_id}' name='subject' value='{html.escape(note['subject'])}' required></td>")
        print(f"<td><select form='{update_form_id}' name='semester' required>")
        for semester in range(1, 9):
            selected = " selected" if str(note["semester"]) == str(semester) else ""
            print(f"<option value='{semester}'{selected}>Semester {semester}</option>")
        print("</select></td>")
        print(f"<td>{note['download_count']}</td>")
        print("<td>")
        print(f"<form id='{update_form_id}' action='/cgi-bin/process_user.cgi?action=update_note' method='post'>")
        print(hidden_user_inputs(user))
        print(f"<input type='hidden' name='note_id' value='{note['id']}'>")
        print("<button class='btn-blue' type='submit'>Update</button>")
        print("</form>")
        print("</td>")
        print("<td>")
        print(f"<form id='{delete_form_id}' class='inline-form' action='/cgi-bin/process_user.cgi?action=delete_note' method='post'>")
        print(hidden_user_inputs(user))
        print(f"<input type='hidden' name='note_id' value='{note['id']}'>")
        print("<button class='btn-danger' type='submit'>Delete</button>")
        print("</form>")
        print("</td>")
        print("</tr>")

    print("</tbody></table>")


def render_student_dashboard(user, message=""):
    notes = fetch_notes()
    page_start("Student Dashboard")
    print("<section class='panel'><div class='panel-head bar'>")
    print(f"<div><h2>Student Dashboard</h2><p class='muted'>Welcome {html.escape(user['name'])}</p></div>")
    print("<a class='btn btn-light' href='/form.html'>Logout</a>")
    print("</div><div class='panel-body'>")
    if message:
        print(f"<div class='notice'>{html.escape(message)}</div>")
    print("<h3>Available Faculty Notes</h3>")
    render_table(notes, show_uploader=True)
    print("</div></section>")
    page_end()


def render_faculty_dashboard(user, message="", errors=None):
    notes = fetch_notes(user.get("email"))
    page_start("Faculty Dashboard")
    print("<section class='panel'><div class='panel-head bar'>")
    print(f"<div><h2>Faculty Dashboard</h2><p class='muted'>Welcome {html.escape(user['name'])}</p></div>")
    print("<a class='btn btn-light' href='/form.html'>Logout</a>")
    print("</div><div class='panel-body'>")
    if message:
        print(f"<div class='notice'>{html.escape(message)}</div>")
    if errors:
        print("<div class='error'>" + "<br>".join(html.escape(error) for error in errors) + "</div>")
    print("<form action='/cgi-bin/process_user.cgi?action=upload' method='post' enctype='multipart/form-data'>")
    print(hidden_user_inputs(user))
    print("<div class='form-grid'>")
    print("<div><label>Subject</label><input name='subject' required></div>")
    print("<div><label>Title</label><input name='title' required></div>")
    print("<div><label>Semester</label><select name='semester' required>")
    for semester in range(1, 9):
        print(f"<option value='{semester}'>Semester {semester}</option>")
    print("</select></div>")
    print("<div><label>Document</label><input name='note_file' type='file' required></div>")
    print("<div class='full'><button type='submit'>Upload Notes</button></div>")
    print("</div></form></div></section>")

    print("<section class='panel'><div class='panel-head'><h3>Your Uploaded Notes</h3></div><div class='panel-body'>")
    render_faculty_notes_table(notes, user)
    print("</div></section>")
    page_end()


def synchronization_log():
    users = load_users()
    student_names = [
        user.get("name") or user.get("email") or "Student"
        for user in users
        if user.get("role") == "student"
    ]
    faculty_names = [
        user.get("name") or user.get("email") or "Faculty"
        for user in users
        if user.get("role") == "faculty"
    ]

    if not student_names:
        student_names = ["Sample Student"]
    if not faculty_names:
        faculty_names = ["Sample Faculty"]

    lock = threading.Condition()
    state = {"readers": 0, "writer": False, "waiting_writers": 0}
    logs = []

    def log(message):
        logs.append(message)

    def reader(name, delay):
        time.sleep(delay)
        log(f"{name} waiting to download notes.")
        with lock:
            while state["writer"] or state["waiting_writers"] > 0:
                lock.wait()
            state["readers"] += 1
            log(f"{name} started reading. Active readers: {state['readers']}.")
        time.sleep(0.25)
        with lock:
            state["readers"] -= 1
            log(f"{name} finished reading. Remaining readers: {state['readers']}.")
            if state["readers"] == 0:
                lock.notify_all()

    def writer(name, delay):
        time.sleep(delay)
        log(f"{name} waiting to upload/update notes.")
        with lock:
            state["waiting_writers"] += 1
            while state["writer"] or state["readers"] > 0:
                lock.wait()
            state["waiting_writers"] -= 1
            state["writer"] = True
            log(f"{name} started writing. Readers are blocked.")
        time.sleep(0.3)
        with lock:
            state["writer"] = False
            log(f"{name} finished writing. Access released.")
            lock.notify_all()

    threads = []
    delay = 0.0

    for student_name in student_names:
        threads.append(threading.Thread(target=reader, args=(student_name, delay)))
        delay += 0.05

    for faculty_name in faculty_names:
        threads.append(threading.Thread(target=writer, args=(faculty_name, delay)))
        delay += 0.05

    if len(student_names) == 1:
        threads.append(threading.Thread(target=reader, args=(student_names[0], delay + 0.05)))

    log("Admin started reader-writer synchronization demo using registered users.")
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    log("Synchronization completed safely.")
    return "\n".join(logs)


def render_admin_dashboard(message="", sync_text=""):
    users = load_users()
    notes = fetch_notes()
    students = [user for user in users if user.get("role") == "student"]
    faculty = [user for user in users if user.get("role") == "faculty"]
    downloads = sum(note["download_count"] for note in notes)

    page_start("Admin Dashboard")
    print("<section class='panel'><div class='panel-head bar'>")
    print("<div><h2>Admin Dashboard</h2><p class='muted'>System overview and synchronization monitor</p></div>")
    print("<a class='btn btn-light' href='/form.html'>Logout</a>")
    print("</div><div class='panel-body'>")
    if message:
        print(f"<div class='notice'>{html.escape(message)}</div>")
    print("<div class='grid'>")
    for label, value in [
        ("Students", len(students)),
        ("Faculty", len(faculty)),
        ("Notes", len(notes)),
        ("Downloads", downloads),
    ]:
        print(f"<div class='card'><strong>{label}</strong><span>{value}</span></div>")
    print("</div></div></section>")

    print("<section class='panel'><div class='panel-head'><h3>Registered Users</h3></div><div class='panel-body'>")
    print("<table><thead><tr><th>Name</th><th>Email</th><th>Role</th><th>Department</th><th>Semester</th><th>Action</th></tr></thead><tbody>")
    if not users:
        print("<tr><td colspan='6' class='muted'>No registered users yet.</td></tr>")
    for user in users:
        user_email = user.get("email", "")
        user_role = user.get("role", "")
        print("<tr>")
        print(f"<td>{html.escape(user.get('name', ''))}</td>")
        print(f"<td>{html.escape(user_email)}</td>")
        print(f"<td>{html.escape(user_role.title())}</td>")
        print(f"<td>{html.escape(user.get('department', ''))}</td>")
        print(f"<td>{html.escape(user.get('semester', ''))}</td>")
        print("<td>")
        print("<form class='inline-form' action='/cgi-bin/process_user.cgi?action=delete_user' method='post'>")
        print(f"<input type='hidden' name='email' value='{html.escape(user_email)}'>")
        print(f"<input type='hidden' name='role' value='{html.escape(user_role)}'>")
        print("<button class='btn-danger' type='submit'>Delete</button>")
        print("</form>")
        print("</td>")
        print("</tr>")
    print("</tbody></table></div></section>")

    print("<section class='panel'><div class='panel-head'><h3>Uploaded Notes</h3></div><div class='panel-body'>")
    render_table(notes, show_uploader=True)
    print("</div></section>")

    print("<section class='panel'><div class='panel-head bar'>")
    print("<h3>Reader-Writer Synchronization</h3>")
    print("<a class='btn btn-blue' href='/cgi-bin/process_user.cgi?action=sync'>Run Synchronization Demo</a>")
    print("</div><div class='panel-body'>")
    print("<p class='muted'>Students are readers, faculty are writers, and admin monitors controlled access.</p>")
    if sync_text:
        print(f"<pre>{html.escape(sync_text)}</pre>")
    print("</div></section>")
    page_end()


def delete_user(form):
    email = get_value(form, "email")
    role = get_value(form, "role").lower()

    if not email or role not in {"student", "faculty"}:
        render_admin_dashboard("Invalid user selected for deletion.")
        return

    users = load_users()
    remaining_users = [
        user
        for user in users
        if not (
            user.get("email", "").lower() == email.lower()
            and user.get("role", "").lower() == role
        )
    ]

    if len(remaining_users) == len(users):
        render_admin_dashboard("User not found.")
        return

    save_users(remaining_users)
    render_admin_dashboard(f"{role.title()} user {email} deleted successfully.")


def launch_tkinter_dashboard(user):
    subprocess.Popen(
        [
            sys.executable,
            TKINTER_APP,
            "--role",
            user.get("role", ""),
            "--email",
            user.get("email", ""),
        ],
        cwd=os.path.dirname(TKINTER_APP),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def render_tkinter_handoff(user, message):
    role = user.get("role", "").title()
    page_start(f"{role} Tkinter Dashboard")
    print("<section class='panel'><div class='panel-head'>")
    print(f"<h2>{html.escape(role)} Dashboard</h2>")
    print("</div><div class='panel-body'>")
    print(f"<div class='notice'>{html.escape(message)}</div>")
    print("<p class='muted'>Your Tkinter dashboard has been opened for Part C.</p>")
    print("<a class='btn btn-light' href='/form.html'>Back to login</a>")
    print("</div></section>")
    page_end()


def save_uploaded_note(form):
    user = {
        "name": get_value(form, "name"),
        "email": get_value(form, "email"),
        "role": get_value(form, "role"),
    }
    subject = get_value(form, "subject")
    title = get_value(form, "title")
    semester = get_value(form, "semester")
    file_item = get_file_item(form, "note_file")
    errors = []

    if user["role"] != "faculty":
        errors.append("Only faculty can upload notes.")
    if not subject:
        errors.append("Subject is required.")
    if not title:
        errors.append("Title is required.")
    if not semester:
        errors.append("Semester is required.")
    if file_item is None or not getattr(file_item, "filename", ""):
        errors.append("Document file is required.")

    if errors:
        render_faculty_dashboard(user, errors=errors)
        return

    original_name = os.path.basename(file_item.filename)
    extension = os.path.splitext(original_name)[1].lower()
    if extension not in ALLOWED_EXTENSIONS:
        render_faculty_dashboard(
            user,
            errors=["Only PDF, DOC, DOCX, PPT, PPTX, and TXT files are allowed."],
        )
        return

    os.makedirs(NOTES_DIR, exist_ok=True)
    filename = original_name
    base, ext = os.path.splitext(filename)
    saved_path = os.path.join(NOTES_DIR, filename)
    counter = 1
    while os.path.exists(saved_path):
        filename = f"{base}_{counter}{ext}"
        saved_path = os.path.join(NOTES_DIR, filename)
        counter += 1

    content = getattr(file_item, "content", b"")
    if not content and hasattr(file_item, "file"):
        content = file_item.file.read()

    with open(saved_path, "wb") as file:
        file.write(content)

    setup_db()
    conn = connect_db()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO notes
            (subject, title, semester, uploader_name, email, file_link, download_count)
            VALUES (?, ?, ?, ?, ?, ?, 0)
        """, (subject, title, semester, user["name"], user["email"], saved_path))
        conn.commit()
    except sqlite3.Error as error:
        conn.rollback()
        render_faculty_dashboard(user, errors=[str(error)])
        return
    finally:
        conn.close()

    render_faculty_dashboard(user, message="Notes uploaded successfully.")


def update_note(form):
    user = {
        "name": get_value(form, "name"),
        "email": get_value(form, "email"),
        "role": get_value(form, "role"),
    }
    note_id = get_value(form, "note_id")
    title = get_value(form, "title")
    subject = get_value(form, "subject")
    semester = get_value(form, "semester")
    errors = []

    if user["role"] != "faculty":
        errors.append("Only faculty can update notes.")
    if not note_id:
        errors.append("Note ID is missing.")
    if not title:
        errors.append("Title is required.")
    if not subject:
        errors.append("Subject is required.")
    if not semester:
        errors.append("Semester is required.")

    if errors:
        render_faculty_dashboard(user, errors=errors)
        return

    conn = connect_db()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE notes
            SET title=?, subject=?, semester=?
            WHERE id=? AND email=?
        """, (title, subject, semester, note_id, user["email"]))
        if cursor.rowcount == 0:
            conn.rollback()
            render_faculty_dashboard(user, errors=["Note not found or not owned by this faculty account."])
            return
        conn.commit()
        render_faculty_dashboard(user, message="Note details updated successfully.")
    except sqlite3.Error as error:
        conn.rollback()
        render_faculty_dashboard(user, errors=[str(error)])
    finally:
        conn.close()


def delete_note(form):
    user = {
        "name": get_value(form, "name"),
        "email": get_value(form, "email"),
        "role": get_value(form, "role"),
    }
    note_id = get_value(form, "note_id")

    if user["role"] != "faculty":
        render_faculty_dashboard(user, errors=["Only faculty can delete notes."])
        return

    conn = connect_db()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT file_link FROM notes WHERE id=? AND email=?", (note_id, user["email"]))
        row = cursor.fetchone()
        if not row:
            render_faculty_dashboard(user, errors=["Note not found or not owned by this faculty account."])
            return

        file_path = resolve_note_path(row[0])
        cursor.execute("DELETE FROM notes WHERE id=? AND email=?", (note_id, user["email"]))
        conn.commit()

        if file_path and os.path.exists(file_path):
            os.remove(file_path)

        render_faculty_dashboard(user, message="Note deleted successfully.")
    except (OSError, sqlite3.Error) as error:
        conn.rollback()
        render_faculty_dashboard(user, errors=[str(error)])
    finally:
        conn.close()


def download_note(note_id):
    setup_db()
    conn = connect_db()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT title, file_link, download_count FROM notes WHERE id=?", (note_id,))
        row = cursor.fetchone()
        if not row:
            render_student_dashboard({"name": "Student", "email": "", "role": "student"}, "Note not found.")
            return

        title, file_path, count = row
        file_path = resolve_note_path(file_path)
        if not file_path or not os.path.exists(file_path):
            render_student_dashboard({"name": "Student", "email": "", "role": "student"}, "Stored file is missing.")
            return

        cursor.execute("UPDATE notes SET download_count=? WHERE id=?", ((count or 0) + 1, note_id))
        conn.commit()
    finally:
        conn.close()

    filename = os.path.basename(file_path)
    content_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"
    print(f"Content-Type: {content_type}")
    print(f"Content-Disposition: attachment; filename=\"{filename}\"")
    print(f"Content-Length: {os.path.getsize(file_path)}")
    print()
    sys.stdout.flush()
    with open(file_path, "rb") as file:
        shutil.copyfileobj(file, sys.stdout.buffer)


def handle_auth(form):
    mode = get_value(form, "mode").lower() or "login"
    name = get_value(form, "name")
    email = get_value(form, "email")
    password = get_value(form, "password")
    role = get_value(form, "role").lower()
    department = get_value(form, "department")
    semester = get_value(form, "semester")
    errors = validate_auth(mode, name, email, password, role, department, semester)

    if errors:
        if wants_json():
            print_json(False, errors=errors, role=role)
        else:
            page_start("Request Failed")
            print("<section class='panel'><div class='panel-body'>")
            print("<div class='error'>" + "<br>".join(html.escape(error) for error in errors) + "</div>")
            print("<a class='btn btn-light' href='/form.html'>Back to portal</a>")
            print("</div></section>")
            page_end()
        return

    if mode == "register":
        success, register_errors = register_user(name, email, password, role, department, semester)
        if not success:
            if wants_json():
                print_json(False, errors=register_errors, role=role)
            else:
                page_start("Registration Failed")
                print("<section class='panel'><div class='panel-body'>")
                print("<div class='error'>" + "<br>".join(html.escape(error) for error in register_errors) + "</div>")
                print("<a class='btn btn-light' href='/form.html'>Back to portal</a>")
                print("</div></section>")
                page_end()
            return
        user = {
            "name": name,
            "email": email,
            "role": role,
            "department": department,
            "semester": semester if role == "student" else "",
        }
        message = f"Registration successful. Welcome {name}."
    else:
        success, result = login_user(email, password, role)
        if not success:
            if wants_json():
                print_json(False, errors=result, role=role)
            else:
                page_start("Login Failed")
                print("<section class='panel'><div class='panel-body'>")
                print("<div class='error'>" + "<br>".join(html.escape(error) for error in result) + "</div>")
                print("<a class='btn btn-light' href='/form.html'>Back to portal</a>")
                print("</div></section>")
                page_end()
            return
        user = result
        message = f"Login successful. Welcome {user['name']}."

    if wants_json():
        print_json(True, message=message, role=role)
    elif role == "student":
        try:
            launch_tkinter_dashboard(user)
            render_tkinter_handoff(user, message)
        except OSError as error:
            page_start("Tkinter Launch Failed")
            print("<section class='panel'><div class='panel-body'>")
            print(f"<div class='error'>{html.escape(str(error))}</div>")
            print("<a class='btn btn-light' href='/form.html'>Back to portal</a>")
            print("</div></section>")
            page_end()
    elif role == "faculty":
        try:
            launch_tkinter_dashboard(user)
            render_tkinter_handoff(user, message)
        except OSError as error:
            page_start("Tkinter Launch Failed")
            print("<section class='panel'><div class='panel-body'>")
            print(f"<div class='error'>{html.escape(str(error))}</div>")
            print("<a class='btn btn-light' href='/form.html'>Back to portal</a>")
            print("</div></section>")
            page_end()
    else:
        render_admin_dashboard(message)


def main():
    form = cgi.FieldStorage()
    action = get_value(form, "action") or get_value(form, "mode")

    if not action:
        query = parse_qs(os.environ.get("QUERY_STRING", ""), keep_blank_values=True)
        action = query.get("action", [""])[0]

    if action == "upload":
        save_uploaded_note(form)
    elif action == "update_note":
        update_note(form)
    elif action == "delete_note":
        delete_note(form)
    elif action == "delete_user":
        delete_user(form)
    elif action == "download":
        note_id = get_value(form, "note_id")
        if not note_id:
            query = parse_qs(os.environ.get("QUERY_STRING", ""), keep_blank_values=True)
            note_id = query.get("note_id", [""])[0]
        download_note(note_id)
    elif action == "sync":
        render_admin_dashboard("Synchronization demo executed.", synchronization_log())
    else:
        handle_auth(form)


if __name__ == "__main__":
    main()
