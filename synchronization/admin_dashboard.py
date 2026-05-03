"""Admin dashboard and synchronization monitor for Part D."""

import json
import os
import queue
import sqlite3
import tkinter as tk
from tkinter import messagebox, ttk

from reader_writer import SynchronizationDemo


BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
USERS_FILE = os.path.join(BASE_DIR, "cgi_urllib", "data", "users.json")
DB_CANDIDATES = [
    os.path.join(BASE_DIR, "database", "notes.db"),
    os.path.join(BASE_DIR, "gui", "notes.db"),
    os.path.join(BASE_DIR, "notes.db"),
]


class AdminDashboard(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Admin Dashboard - Shared Notes Exchange")
        self.geometry("980x680")
        self.resizable(False, False)

        self.bg = "#eef3f8"
        self.navy = "#102b57"
        self.blue = "#1d5fa7"
        self.gold = "#f2b233"
        self.line = "#d8e0eb"
        self.configure(bg=self.bg)

        self.log_queue = queue.Queue()
        self.demo_running = False

        self.create_widgets()
        self.refresh_data()
        self.after(100, self.process_log_queue)

    def create_widgets(self):
        header = tk.Frame(self, bg=self.navy, height=86)
        header.pack(fill="x")
        header.pack_propagate(False)

        seal = tk.Label(
            header,
            text="PTU",
            bg=self.navy,
            fg=self.gold,
            font=("Segoe UI", 16, "bold"),
            width=6,
        )
        seal.pack(side="left", padx=(22, 10))

        title_block = tk.Frame(header, bg=self.navy)
        title_block.pack(side="left", fill="y", pady=15)

        tk.Label(
            title_block,
            text="Puducherry Technological University",
            bg=self.navy,
            fg="white",
            font=("Segoe UI", 18, "bold"),
        ).pack(anchor="w")

        tk.Label(
            title_block,
            text="Admin Monitoring and Synchronization Dashboard",
            bg=self.navy,
            fg="#dce8f6",
            font=("Segoe UI", 10),
        ).pack(anchor="w", pady=(4, 0))

        toolbar = tk.Frame(self, bg=self.bg)
        toolbar.pack(fill="x", padx=20, pady=(16, 8))

        tk.Button(
            toolbar,
            text="Refresh Overview",
            command=self.refresh_data,
            bg=self.blue,
            fg="white",
            font=("Segoe UI", 10, "bold"),
            padx=12,
            pady=6,
            relief="flat",
        ).pack(side="left")

        self.demo_button = tk.Button(
            toolbar,
            text="Run Synchronization Demo",
            command=self.run_demo,
            bg=self.navy,
            fg="white",
            font=("Segoe UI", 10, "bold"),
            padx=12,
            pady=6,
            relief="flat",
        )
        self.demo_button.pack(side="left", padx=10)

        content = tk.Frame(self, bg=self.bg)
        content.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        left = tk.Frame(content, bg=self.bg)
        left.pack(side="left", fill="both", expand=True)

        right = tk.Frame(content, bg=self.bg, width=390)
        right.pack(side="right", fill="both", padx=(18, 0))
        right.pack_propagate(False)

        stats = tk.Frame(left, bg=self.bg)
        stats.pack(fill="x", pady=(0, 12))

        self.student_count = self.create_stat_card(stats, "Students", "0", 0)
        self.faculty_count = self.create_stat_card(stats, "Faculty", "0", 1)
        self.notes_count = self.create_stat_card(stats, "Notes", "0", 2)
        self.download_count = self.create_stat_card(stats, "Downloads", "0", 3)

        self.notebook = ttk.Notebook(left)
        self.notebook.pack(fill="both", expand=True)

        self.users_tree = self.create_tree(
            self.notebook,
            "Registered Users",
            ("name", "email", "role", "department", "semester"),
            ("Name", "Email", "Role", "Department", "Semester"),
        )

        self.notes_tree = self.create_tree(
            self.notebook,
            "Uploaded Notes",
            ("id", "title", "subject", "uploader", "downloads"),
            ("ID", "Title", "Subject", "Uploader", "Downloads"),
        )

        log_panel = self.create_panel(right, "Synchronization Log")
        self.log_text = tk.Text(
            log_panel,
            height=26,
            bg="#0f172a",
            fg="#e5edf7",
            insertbackground="white",
            font=("Consolas", 10),
            wrap="word",
            relief="flat",
        )
        self.log_text.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        summary_panel = self.create_panel(right, "Reader-Writer Mapping")
        mapping = (
            "Students downloading notes = Readers\n"
            "Faculty uploading/updating notes = Writers\n"
            "Admin dashboard = Monitor\n\n"
            "Many readers can access notes together.\n"
            "Only one writer can modify notes at a time."
        )
        tk.Label(
            summary_panel,
            text=mapping,
            justify="left",
            bg="white",
            fg="#172033",
            font=("Segoe UI", 10),
            wraplength=340,
        ).pack(fill="x", padx=12, pady=(0, 12))

    def create_stat_card(self, parent, label, value, column):
        card = tk.Frame(parent, bg="white", highlightbackground=self.line, highlightthickness=1)
        card.grid(row=0, column=column, padx=(0 if column == 0 else 8, 0), sticky="ew")
        parent.grid_columnconfigure(column, weight=1)

        tk.Label(
            card,
            text=label,
            bg="white",
            fg="#657085",
            font=("Segoe UI", 9, "bold"),
        ).pack(anchor="w", padx=12, pady=(10, 0))

        value_label = tk.Label(
            card,
            text=value,
            bg="white",
            fg=self.navy,
            font=("Segoe UI", 20, "bold"),
        )
        value_label.pack(anchor="w", padx=12, pady=(2, 10))
        return value_label

    def create_panel(self, parent, title):
        panel = tk.Frame(parent, bg="white", highlightbackground=self.line, highlightthickness=1)
        panel.pack(fill="both", expand=True, pady=(0, 12))
        tk.Label(
            panel,
            text=title,
            bg="white",
            fg=self.navy,
            font=("Segoe UI", 12, "bold"),
        ).pack(anchor="w", padx=12, pady=12)
        return panel

    def create_tree(self, parent, title, columns, headings):
        frame = tk.Frame(parent, bg="white")
        parent.add(frame, text=title)

        tree = ttk.Treeview(frame, columns=columns, show="headings", height=15)
        for column, heading in zip(columns, headings):
            tree.heading(column, text=heading)
            tree.column(column, width=110, anchor="w")

        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        tree.pack(side="left", fill="both", expand=True, padx=(10, 0), pady=10)
        scrollbar.pack(side="right", fill="y", padx=(0, 10), pady=10)
        return tree

    def refresh_data(self):
        users = self.load_users()
        notes = self.load_notes()

        students = [user for user in users if user.get("role") == "student"]
        faculty = [user for user in users if user.get("role") == "faculty"]
        total_downloads = sum(note.get("download_count", 0) for note in notes)

        self.student_count.config(text=str(len(students)))
        self.faculty_count.config(text=str(len(faculty)))
        self.notes_count.config(text=str(len(notes)))
        self.download_count.config(text=str(total_downloads))

        self.populate_users(users)
        self.populate_notes(notes)
        self.log("Admin refreshed users, notes, and download overview.")

    def load_users(self):
        if not os.path.exists(USERS_FILE):
            return []

        try:
            with open(USERS_FILE, "r", encoding="utf-8") as file:
                return json.load(file)
        except (OSError, json.JSONDecodeError):
            messagebox.showwarning("Users", "Could not read registered users.")
            return []

    def find_database(self):
        for path in DB_CANDIDATES:
            if os.path.exists(path):
                return path
        return None

    def load_notes(self):
        db_path = self.find_database()
        if not db_path:
            return []

        conn = sqlite3.connect(db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, title, subject, uploader_name, download_count
                FROM notes
                ORDER BY id DESC
            """)
            return [
                {
                    "id": row[0],
                    "title": row[1] or "",
                    "subject": row[2] or "",
                    "uploader": row[3] or "",
                    "download_count": row[4] or 0,
                }
                for row in cursor.fetchall()
            ]
        except sqlite3.Error:
            messagebox.showwarning("Notes", "Could not read notes database.")
            return []
        finally:
            conn.close()

    def populate_users(self, users):
        self.users_tree.delete(*self.users_tree.get_children())
        for user in users:
            self.users_tree.insert(
                "",
                "end",
                values=(
                    user.get("name", ""),
                    user.get("email", ""),
                    user.get("role", "").title(),
                    user.get("department", ""),
                    user.get("semester", ""),
                ),
            )

    def populate_notes(self, notes):
        self.notes_tree.delete(*self.notes_tree.get_children())
        for note in notes:
            self.notes_tree.insert(
                "",
                "end",
                values=(
                    note.get("id", ""),
                    note.get("title", ""),
                    note.get("subject", ""),
                    note.get("uploader", ""),
                    note.get("download_count", 0),
                ),
            )

    def run_demo(self):
        if self.demo_running:
            messagebox.showinfo("Synchronization", "Demo is already running.")
            return

        self.demo_running = True
        self.demo_button.config(state="disabled")
        self.log_text.delete("1.0", tk.END)
        users = self.load_users()
        students = [
            user.get("name") or user.get("email") or "Student"
            for user in users
            if user.get("role") == "student"
        ]
        faculty = [
            user.get("name") or user.get("email") or "Faculty"
            for user in users
            if user.get("role") == "faculty"
        ]
        demo = SynchronizationDemo(
            self.queue_log,
            self.mark_demo_finished,
            students,
            faculty,
        )
        demo.run()

    def queue_log(self, message):
        self.log_queue.put(message)

    def process_log_queue(self):
        while not self.log_queue.empty():
            message = self.log_queue.get()
            if message == "__DEMO_FINISHED__":
                self.process_demo_finished()
            else:
                self.log(message)
        self.after(100, self.process_log_queue)

    def log(self, message):
        self.log_text.insert(tk.END, f"{message}\n")
        self.log_text.see(tk.END)

    def mark_demo_finished(self):
        self.log_queue.put("__DEMO_FINISHED__")

    def process_demo_finished(self):
        self.demo_running = False
        self.demo_button.config(state="normal")

if __name__ == "__main__":
    app = AdminDashboard()
    app.mainloop()
