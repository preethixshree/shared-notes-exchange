import argparse
import json
import os
import shutil
import sqlite3
import webbrowser
import tkinter as tk
from tkinter import filedialog, messagebox

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATABASE_PATH = os.path.join(BASE_DIR, "database", "notes.db")
NOTES_FOLDER = os.path.join(os.path.dirname(__file__), "notes")
USERS_FILE = os.path.join(BASE_DIR, "cgi_urllib", "data", "users.json")
ADMIN_ID = "admin"
ADMIN_PASSWORD = "admin123"
PORTAL_URL = "http://localhost:8000/form.html"
ALLOWED_EXTENSIONS = {".pdf", ".doc", ".docx", ".ppt", ".pptx", ".txt"}

def connect_db():
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    return sqlite3.connect(DATABASE_PATH)


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


def load_users():
    if not os.path.exists(USERS_FILE):
        return []

    try:
        with open(USERS_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    except (OSError, json.JSONDecodeError):
        return []


def resolve_note_path(file_path):
    if not file_path:
        return ""

    if os.path.isabs(file_path):
        return file_path

    candidates = [
        os.path.join(os.path.dirname(__file__), file_path),
        os.path.join(BASE_DIR, file_path),
        os.path.join(NOTES_FOLDER, os.path.basename(file_path)),
    ]

    for candidate in candidates:
        if os.path.exists(candidate):
            return candidate

    return candidates[0]


def parse_record_id(listbox_text):
    return int(listbox_text.split("|")[0].replace("ID:", "").strip())


class App(tk.Tk):
    def __init__(self, initial_user=None):
        super().__init__()
        self.title("Shared Notes Exchange")
        self.geometry("900x680")
        self.resizable(False, False)

        self.primary_color = "#eef3f8"
        self.accent_color = "#102b57"
        self.secondary_color = "#1d5fa7"
        self.gold_color = "#f2b233"
        self.text_color = "#172033"
        self.muted_color = "#657085"
        self.configure(bg=self.primary_color)

        self.current_user = None
        self.selected_note_id = None
        self.entries = {}
        self.search_entries = {}

        setup_db()
        if initial_user:
            self.current_user = initial_user
            if initial_user.get("role") == "faculty":
                self.create_faculty_dashboard()
            else:
                self.create_student_dashboard()
        else:
            self.create_login_view()
        self.protocol("WM_DELETE_WINDOW", self.exit_app)

    def clear_window(self):
        for widget in self.winfo_children():
            widget.destroy()

    def create_login_view(self):
        self.clear_window()
        self.config(menu=tk.Menu(self))
        self.current_user = None
        self.selected_note_id = None
        self.configure(bg=self.primary_color)

        header = tk.Frame(self, bg=self.accent_color, height=110)
        header.pack(fill="x")
        header.pack_propagate(False)

        tk.Label(
            header,
            text="Shared Notes Exchange",
            bg=self.accent_color,
            fg="white",
            font=("Segoe UI", 22, "bold"),
        ).pack(anchor="w", padx=32, pady=(24, 0))

        tk.Label(
            header,
            text="Tkinter student and faculty dashboards",
            bg=self.accent_color,
            fg="#dce8f6",
            font=("Segoe UI", 11),
        ).pack(anchor="w", padx=32, pady=(5, 0))

        login_panel = tk.Frame(self, bg="white", highlightbackground="#d8e0eb", highlightthickness=1)
        login_panel.pack(pady=54, ipadx=26, ipady=22)

        tk.Label(
            login_panel,
            text="Login",
            bg="white",
            fg=self.accent_color,
            font=("Segoe UI", 18, "bold"),
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 18))

        self.login_email = self.create_labeled_entry(login_panel, "Email / Admin ID", 1)
        self.login_password = self.create_labeled_entry(login_panel, "Password", 2, show="*")

        tk.Label(
            login_panel,
            text="Role:",
            bg="white",
            fg=self.accent_color,
            font=("Segoe UI", 10, "bold"),
        ).grid(row=3, column=0, sticky="e", padx=8, pady=8)

        self.login_role = tk.StringVar(value="student")
        role_frame = tk.Frame(login_panel, bg="white")
        role_frame.grid(row=3, column=1, sticky="w", padx=8, pady=8)
        for role in ("student", "faculty", "admin"):
            tk.Radiobutton(
                role_frame,
                text=role.title(),
                value=role,
                variable=self.login_role,
                bg="white",
                fg=self.text_color,
                activebackground="white",
                font=("Segoe UI", 10),
            ).pack(side="left", padx=(0, 14))

        tk.Button(
            login_panel,
            text="Login",
            command=self.login,
            bg=self.accent_color,
            fg="white",
            font=("Segoe UI", 10, "bold"),
            relief="flat",
            padx=18,
            pady=8,
        ).grid(row=4, column=1, sticky="e", padx=8, pady=(16, 0))

        tk.Label(
            self,
            text="Student and faculty accounts come from Part B registration. Admin opens in browser.",
            bg=self.primary_color,
            fg=self.muted_color,
            font=("Segoe UI", 9),
        ).pack()

    def create_labeled_entry(self, parent, label, row, show=None):
        tk.Label(
            parent,
            text=label + ":",
            bg="white",
            fg=self.accent_color,
            font=("Segoe UI", 10, "bold"),
        ).grid(row=row, column=0, sticky="e", padx=8, pady=8)

        entry = tk.Entry(
            parent,
            width=36,
            show=show,
            bg="#fbfcfe",
            fg=self.text_color,
            font=("Segoe UI", 10),
        )
        entry.grid(row=row, column=1, sticky="w", padx=8, pady=8)
        return entry

    def login(self):
        email = self.login_email.get().strip()
        password = self.login_password.get().strip()
        role = self.login_role.get()

        if not email or not password:
            messagebox.showwarning("Login Error", "Email/Admin ID and password are required.")
            return

        if role == "admin":
            if email.lower() == ADMIN_ID and password == ADMIN_PASSWORD:
                webbrowser.open(PORTAL_URL)
                messagebox.showinfo(
                    "Admin Portal",
                    "Admin dashboard opens in the browser. Start Part B server if the page does not load.",
                )
                return
            messagebox.showerror("Login Error", "Invalid admin credentials.")
            return

        for user in load_users():
            if (
                user.get("email", "").lower() == email.lower()
                and user.get("password") == password
                and user.get("role") == role
            ):
                self.current_user = user
                if role == "faculty":
                    self.create_faculty_dashboard()
                else:
                    self.create_student_dashboard()
                return

        messagebox.showerror("Login Error", "Invalid email, password, or role.")

    def create_menu(self):
        menubar = tk.Menu(self)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Open", command=self.browse_file)
        file_menu.add_command(label="Save", command=self.save_selected_note)
        file_menu.add_separator()
        file_menu.add_command(label="Logout", command=self.logout_to_browser)
        file_menu.add_command(label="Exit", command=self.exit_app)
        menubar.add_cascade(label="File", menu=file_menu)
        self.config(menu=menubar)

    def create_dashboard_header(self, title, subtitle):
        header = tk.Frame(self, bg=self.accent_color, height=92)
        header.pack(fill="x")
        header.pack_propagate(False)

        tk.Label(
            header,
            text=title,
            bg=self.accent_color,
            fg="white",
            font=("Segoe UI", 20, "bold"),
        ).pack(anchor="w", padx=24, pady=(18, 0))

        tk.Label(
            header,
            text=subtitle,
            bg=self.accent_color,
            fg="#dce8f6",
            font=("Segoe UI", 10),
        ).pack(anchor="w", padx=24, pady=(4, 0))

    def create_faculty_dashboard(self):
        self.clear_window()
        self.create_menu()
        user_name = self.current_user.get("name", "Faculty")
        self.create_dashboard_header("Faculty Dashboard", f"Welcome {user_name}. Insert, update, delete, and search notes.")

        body = tk.Frame(self, bg=self.primary_color)
        body.pack(fill="both", expand=True, padx=20, pady=16)

        form_frame = tk.LabelFrame(
            body,
            text="Note Details",
            bg=self.primary_color,
            fg=self.accent_color,
            padx=10,
            pady=10,
            font=("Segoe UI", 10, "bold"),
        )
        form_frame.pack(fill="x")

        self.entries = {}
        fields = [
            ("Subject", "subject"),
            ("Title", "title"),
            ("Semester", "semester"),
            ("File Link", "file_link"),
            ("Download Count", "download_count"),
        ]
        for index, (label, key) in enumerate(fields):
            tk.Label(
                form_frame,
                text=label + ":",
                bg=self.primary_color,
                fg=self.accent_color,
                font=("Segoe UI", 10, "bold"),
            ).grid(row=index // 2, column=(index % 2) * 3, sticky="e", padx=8, pady=6)

            entry = tk.Entry(form_frame, width=32, bg="white", fg=self.text_color, font=("Segoe UI", 10))
            entry.grid(row=index // 2, column=(index % 2) * 3 + 1, sticky="w", padx=8, pady=6)
            self.entries[key] = entry

            if key == "file_link":
                tk.Button(form_frame, text="Browse", command=self.browse_file).grid(
                    row=index // 2,
                    column=(index % 2) * 3 + 2,
                    padx=4,
                )

        actions = tk.Frame(body, bg=self.primary_color)
        actions.pack(fill="x", pady=10)
        self.create_action_button(actions, "Insert", self.insert_record, 0)
        self.create_action_button(actions, "Update", self.update_record, 1)
        self.create_action_button(actions, "Delete", self.delete_record, 2)
        self.create_action_button(actions, "Clear", self.clear_form, 3)
        self.create_action_button(actions, "Logout", self.logout_to_browser, 4)

        self.create_search_panel(body, faculty_mode=True)
        self.create_notes_list(body)
        self.load_data()

    def create_student_dashboard(self):
        self.clear_window()
        self.config(menu=tk.Menu(self))
        user_name = self.current_user.get("name", "Student")
        self.create_dashboard_header("Student Dashboard", f"Welcome {user_name}. Search by semester, title, or subject and download notes.")

        body = tk.Frame(self, bg=self.primary_color)
        body.pack(fill="both", expand=True, padx=20, pady=16)

        self.create_search_panel(body, faculty_mode=False)

        actions = tk.Frame(body, bg=self.primary_color)
        actions.pack(fill="x", pady=(0, 10))
        self.create_action_button(actions, "Download Selected", self.download_note, 0)
        self.create_action_button(actions, "Clear Search", self.clear_search, 1)
        self.create_action_button(actions, "Logout", self.logout_to_browser, 2)

        self.create_notes_list(body)
        self.load_data()

    def create_action_button(self, parent, text, command, column):
        tk.Button(
            parent,
            text=text,
            command=command,
            bg=self.accent_color if column != 1 else self.secondary_color,
            fg="white",
            font=("Segoe UI", 10, "bold"),
            relief="flat",
            padx=12,
            pady=7,
        ).grid(row=0, column=column, padx=4, sticky="w")

    def create_search_panel(self, parent, faculty_mode):
        search_frame = tk.LabelFrame(
            parent,
            text="Search Notes",
            bg=self.primary_color,
            fg=self.accent_color,
            padx=10,
            pady=10,
            font=("Segoe UI", 10, "bold"),
        )
        search_frame.pack(fill="x", pady=10)

        self.search_entries = {}
        for index, (label, key) in enumerate([("Semester", "semester"), ("Title", "title"), ("Subject", "subject")]):
            tk.Label(
                search_frame,
                text=label + ":",
                bg=self.primary_color,
                fg=self.accent_color,
                font=("Segoe UI", 10, "bold"),
            ).grid(row=0, column=index * 2, padx=6, pady=4, sticky="e")
            entry = tk.Entry(search_frame, width=22, bg="white", fg=self.text_color, font=("Segoe UI", 10))
            entry.grid(row=0, column=index * 2 + 1, padx=6, pady=4, sticky="w")
            self.search_entries[key] = entry

        tk.Button(
            search_frame,
            text="Search",
            command=self.load_data,
            bg=self.secondary_color,
            fg="white",
            font=("Segoe UI", 10, "bold"),
            relief="flat",
            padx=10,
            pady=5,
        ).grid(row=0, column=6, padx=8)

        if faculty_mode:
            tk.Button(
                search_frame,
                text="Show Mine",
                command=self.clear_search,
                bg=self.accent_color,
                fg="white",
                font=("Segoe UI", 10, "bold"),
                relief="flat",
                padx=10,
                pady=5,
            ).grid(row=0, column=7, padx=4)

    def create_notes_list(self, parent):
        list_frame = tk.LabelFrame(
            parent,
            text="Stored Notes",
            bg=self.primary_color,
            fg=self.accent_color,
            padx=10,
            pady=10,
            font=("Segoe UI", 10, "bold"),
        )
        list_frame.pack(fill="both", expand=True)

        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side="right", fill="y")

        self.listbox = tk.Listbox(
            list_frame,
            yscrollcommand=scrollbar.set,
            selectmode="extended",
            font=("Consolas", 10),
            height=13,
        )
        self.listbox.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=self.listbox.yview)
        self.listbox.bind("<<ListboxSelect>>", self.on_list_select)

    def browse_file(self):
        if not hasattr(self, "entries") or "file_link" not in self.entries:
            messagebox.showinfo("Open", "File browsing is available in the faculty dashboard.")
            return

        filepath = filedialog.askopenfilename(title="Select note file")
        if filepath:
            self.entries["file_link"].delete(0, tk.END)
            self.entries["file_link"].insert(0, filepath)

    def get_note_inputs(self):
        return {
            "subject": self.entries["subject"].get().strip(),
            "title": self.entries["title"].get().strip(),
            "semester": self.entries["semester"].get().strip(),
            "file_link": self.entries["file_link"].get().strip(),
            "download_count": self.entries["download_count"].get().strip() or "0",
        }

    def get_search_values(self):
        return {
            key: entry.get().strip()
            for key, entry in self.search_entries.items()
        }

    def clear_form(self):
        self.selected_note_id = None
        for entry in self.entries.values():
            entry.delete(0, tk.END)

    def clear_search(self):
        for entry in self.search_entries.values():
            entry.delete(0, tk.END)
        self.load_data()

    def load_data(self):
        self.selected_note_id = None
        self.listbox.delete(0, tk.END)
        search = self.get_search_values()
        role = self.current_user.get("role") if self.current_user else ""

        query = """
            SELECT id, uploader_name, title, subject, semester, download_count
            FROM notes
            WHERE 1=1
        """
        params = []

        if role == "faculty":
            query += " AND email=?"
            params.append(self.current_user.get("email", ""))

        if search["semester"]:
            query += " AND semester LIKE ?"
            params.append(f"%{search['semester']}%")
        if search["title"]:
            query += " AND title LIKE ?"
            params.append(f"%{search['title']}%")
        if search["subject"]:
            query += " AND subject LIKE ?"
            params.append(f"%{search['subject']}%")

        query += " ORDER BY id DESC"

        conn = connect_db()
        try:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
        finally:
            conn.close()

        if not rows:
            self.listbox.insert(tk.END, "No notes found.")
            return

        for row in rows:
            text = f"ID:{row[0]} | {row[1]} | {row[2]} ({row[3]}) | Sem:{row[4]} | DL:{row[5]}"
            self.listbox.insert(tk.END, text)

    def insert_record(self):
        data = self.get_note_inputs()
        if not data["title"] or not data["subject"] or not data["semester"]:
            messagebox.showwarning("Input Error", "Subject, title, and semester are required.")
            return

        try:
            download_count = int(data["download_count"])
        except ValueError:
            messagebox.showwarning("Input Error", "Download count must be a number.")
            return

        file_path = data["file_link"]
        if not file_path or not os.path.isfile(file_path):
            messagebox.showwarning("File Error", "Please select a valid note file.")
            return

        extension = os.path.splitext(file_path)[1].lower()
        if extension not in ALLOWED_EXTENSIONS:
            messagebox.showwarning("File Error", "Only PDF, DOC, DOCX, PPT, PPTX, and TXT files are allowed.")
            return

        os.makedirs(NOTES_FOLDER, exist_ok=True)
        filename = os.path.basename(file_path)
        base, ext = os.path.splitext(filename)
        saved_path = os.path.join(NOTES_FOLDER, filename)
        counter = 1
        while os.path.exists(saved_path):
            filename = f"{base}_{counter}{ext}"
            saved_path = os.path.join(NOTES_FOLDER, filename)
            counter += 1

        try:
            shutil.copy2(file_path, saved_path)
        except OSError as error:
            messagebox.showerror("File Error", f"Could not copy file:\n{error}")
            return

        conn = connect_db()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO notes
                (subject, title, semester, uploader_name, email, file_link, download_count)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                data["subject"],
                data["title"],
                data["semester"],
                self.current_user.get("name", ""),
                self.current_user.get("email", ""),
                os.path.relpath(saved_path, BASE_DIR),
                download_count,
            ))
            conn.commit()
            self.clear_form()
            self.load_data()
            messagebox.showinfo("Success", "Note inserted successfully.")
        except sqlite3.Error as error:
            conn.rollback()
            messagebox.showerror("Error", str(error))
        finally:
            conn.close()

    def update_record(self):
        if not self.selected_note_id:
            messagebox.showwarning("Select", "Select a note to update.")
            return

        data = self.get_note_inputs()
        if not data["title"] or not data["subject"] or not data["semester"]:
            messagebox.showwarning("Input Error", "Subject, title, and semester are required.")
            return

        conn = connect_db()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE notes
                SET subject=?, title=?, semester=?
                WHERE id=? AND email=?
            """, (
                data["subject"],
                data["title"],
                data["semester"],
                self.selected_note_id,
                self.current_user.get("email", ""),
            ))
            if cursor.rowcount == 0:
                conn.rollback()
                messagebox.showerror("Update Error", "Note not found or not owned by this faculty account.")
                return
            conn.commit()
            self.load_data()
            messagebox.showinfo("Success", "Note updated successfully.")
        except sqlite3.Error as error:
            conn.rollback()
            messagebox.showerror("Error", str(error))
        finally:
            conn.close()

    def delete_record(self):
        if not self.selected_note_id:
            messagebox.showwarning("Select", "Select a note to delete.")
            return

        if not messagebox.askyesno("Delete", "Delete the selected note?"):
            return

        conn = connect_db()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT file_link FROM notes WHERE id=? AND email=?",
                (self.selected_note_id, self.current_user.get("email", "")),
            )
            row = cursor.fetchone()
            if not row:
                messagebox.showerror("Delete Error", "Note not found or not owned by this faculty account.")
                return

            file_path = resolve_note_path(row[0])
            cursor.execute(
                "DELETE FROM notes WHERE id=? AND email=?",
                (self.selected_note_id, self.current_user.get("email", "")),
            )
            conn.commit()

            if file_path and os.path.isfile(file_path):
                os.remove(file_path)

            self.clear_form()
            self.load_data()
            messagebox.showinfo("Success", "Note deleted successfully.")
        except (OSError, sqlite3.Error) as error:
            conn.rollback()
            messagebox.showerror("Error", str(error))
        finally:
            conn.close()

    def save_selected_note(self):
        self.download_note()

    def download_note(self):
        selected = self.listbox.curselection()
        if not selected:
            messagebox.showwarning("Select", "Select a note first.")
            return

        item = self.listbox.get(selected[0])
        if item.startswith("No notes"):
            return

        record_id = parse_record_id(item)
        conn = connect_db()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT title, file_link, download_count FROM notes WHERE id=?", (record_id,))
            row = cursor.fetchone()
            if not row:
                messagebox.showerror("Error", "Note not found.")
                return

            title, file_path, count = row
            file_path = resolve_note_path(file_path)
            if not file_path or not os.path.isfile(file_path):
                messagebox.showerror("Download Error", "Stored note file not found.")
                return

            save_path = filedialog.asksaveasfilename(
                title="Save Note As",
                initialfile=os.path.basename(file_path),
            )
            if not save_path:
                return

            shutil.copy2(file_path, save_path)
            new_count = (count or 0) + 1
            cursor.execute("UPDATE notes SET download_count=? WHERE id=?", (new_count, record_id))
            conn.commit()
            self.load_data()
            messagebox.showinfo("Success", f"'{title}' downloaded successfully.\nDownload count: {new_count}")
        except (OSError, sqlite3.Error) as error:
            conn.rollback()
            messagebox.showerror("Error", str(error))
        finally:
            conn.close()

    def on_list_select(self, event):
        if not self.current_user or self.current_user.get("role") != "faculty":
            return

        selection = self.listbox.curselection()
        if not selection:
            return

        item = self.listbox.get(selection[0])
        if item.startswith("No notes"):
            return

        record_id = parse_record_id(item)
        conn = connect_db()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT subject, title, semester, file_link, download_count FROM notes WHERE id=? AND email=?",
                (record_id, self.current_user.get("email", "")),
            )
            row = cursor.fetchone()
        finally:
            conn.close()

        if row:
            self.selected_note_id = record_id
            self.clear_form()
            self.selected_note_id = record_id
            self.entries["subject"].insert(0, row[0] or "")
            self.entries["title"].insert(0, row[1] or "")
            self.entries["semester"].insert(0, row[2] or "")
            self.entries["file_link"].insert(0, resolve_note_path(row[3]) if row[3] else "")
            self.entries["download_count"].insert(0, str(row[4] or "0"))

    def exit_app(self):
        if messagebox.askyesno("Exit", "Are you sure you want to exit?"):
            self.destroy()

    def logout_to_browser(self):
        webbrowser.open(PORTAL_URL)
        self.destroy()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Shared Notes Exchange Tkinter app")
    parser.add_argument("--role", choices=["student", "faculty"])
    parser.add_argument("--email")
    args = parser.parse_args()

    initial_user = None
    if args.role and args.email:
        for saved_user in load_users():
            if (
                saved_user.get("role") == args.role
                and saved_user.get("email", "").lower() == args.email.lower()
            ):
                initial_user = saved_user
                break

    app = App(initial_user)
    app.mainloop()
