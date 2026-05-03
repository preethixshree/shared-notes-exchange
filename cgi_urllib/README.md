# CGI and urllib Assignment

This folder runs the full browser-based Role-Based Shared Notes Exchange System.
It still completes Part B with `urllib`, CGI, GET, POST, and validation, and it now routes each user to a role dashboard in the same browser.

## Files

- `client_get.py` sends a GET request to JSONPlaceholder and prints the first post.
- `client_post.py` sends login/registration data using `urlencode()` and `Request()`.
- `form.html` provides a PTU-inspired login/registration portal with JavaScript validation.
- `cgi-bin/process_user.cgi` reads input with `cgi.FieldStorage()`, validates it on the server, stores registered users, and serves student, faculty, and admin dashboards.
- `server.py` starts a local CGI-enabled server.
- `data/users.json` is created automatically when a student or faculty member registers.

## Run

From this folder:

```bash
python server.py
```

If Windows says `Python was not found`, try:

```bash
py server.py
```

If `py` also fails, install Python from <https://www.python.org/downloads/> and select **Add python.exe to PATH** during installation. After installing, close and reopen Command Prompt, then run:

```bash
python --version
python server.py
```

You can also disable the Microsoft Store shortcut from:

```text
Settings > Apps > Advanced app settings > App execution aliases
```

Then open:

```text
http://localhost:8000/form.html
```

After login:

- Student opens the Student Dashboard and downloads notes.
- Faculty opens the Faculty Dashboard and uploads documents.
- Admin opens the Admin Dashboard and runs the synchronization demo.

Admin does not register. Use:

```text
Role: Admin
ID: admin
Password: admin123
```

In a second terminal, test the urllib clients:

```bash
python client_get.py
python client_post.py
```

Example successful responses:

```text
Registration successful for [name] as Student.
Login successful. Welcome [name].
```
