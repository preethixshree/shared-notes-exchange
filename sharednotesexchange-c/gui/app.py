import tkinter as tk
from tkinter import messagebox, simpledialog, filedialog
import sqlite3
import os
import shutil


def connect_db():
    return sqlite3.connect("notes.db")


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


class App(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("Shared Notes Exchange")
        self.geometry("850x650")
        self.resizable(False, False)

        self.configure(bg="#f4f7f6")
        self.primary_color = "#f4f7f6"
        self.accent_color = "#003366"
        self.text_color = "#333333"

        setup_db()
        self.create_menu()
        self.create_widgets()
        self.load_data()
        self.protocol("WM_DELETE_WINDOW", self.exit_app)

    def create_menu(self):
        menubar = tk.Menu(self)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Open", command=self.browse_file)
        file_menu.add_command(label="Save", command=self.menu_save)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.exit_app)

        menubar.add_cascade(label="File", menu=file_menu)
        self.config(menu=menubar)

    def menu_save(self):
        messagebox.showinfo("Save", "Save option selected.")

    def exit_app(self):
        if messagebox.askyesno("Exit", "Are you sure you want to exit?"):
            self.destroy()

    def create_widgets(self):
        label_kwargs = {
            "bg": self.primary_color,
            "fg": self.accent_color,
            "font": ("Segoe UI", 10, "bold")
        }

        entry_kwargs = {
            "bg": "white",
            "fg": self.text_color,
            "font": ("Segoe UI", 10)
        }

        button_kwargs = {
            "bg": self.accent_color,
            "fg": "white",
            "font": ("Segoe UI", 10, "bold"),
            "padx": 8,
            "pady": 4
        }

        tk.Label(
            self,
            text="Shared Notes Exchange",
            bg=self.primary_color,
            fg=self.accent_color,
            font=("Segoe UI", 18, "bold")
        ).pack(pady=10)

        input_frame = tk.LabelFrame(
            self,
            text="Note Metadata",
            bg=self.primary_color,
            fg=self.accent_color,
            padx=10,
            pady=10
        )
        input_frame.pack(padx=20, pady=10, fill="x")

        fields = [
            ("Subject", "subject"),
            ("Title", "title"),
            ("Semester", "semester"),
            ("Uploader Name", "uploader_name"),
            ("Email", "email"),
            ("File Link", "file_link"),
            ("Download Count", "download_count")
        ]

        self.entries = {}

        for i, (label, key) in enumerate(fields):
            tk.Label(input_frame, text=label + ":", **label_kwargs).grid(
                row=i, column=0, sticky="e", padx=8, pady=5
            )

            ent = tk.Entry(input_frame, width=40, **entry_kwargs)
            ent.grid(row=i, column=1, padx=8, pady=5, sticky="w")
            self.entries[key] = ent

            if key == "file_link":
                tk.Button(
                    input_frame,
                    text="Browse",
                    command=self.browse_file
                ).grid(row=i, column=2, padx=5)

        btn_frame = tk.Frame(self, bg=self.primary_color)
        btn_frame.pack(pady=10)

        tk.Button(btn_frame, text="Insert", command=self.insert_record, **button_kwargs).grid(row=0, column=0, padx=4)
        tk.Button(btn_frame, text="Update", command=self.update_record, **button_kwargs).grid(row=0, column=1, padx=4)
        tk.Button(btn_frame, text="Delete", command=self.delete_record, **button_kwargs).grid(row=0, column=2, padx=4)
        tk.Button(btn_frame, text="Download", command=self.download_note, **button_kwargs).grid(row=0, column=3, padx=4)
        tk.Button(btn_frame, text="Clear", command=self.clear_form, **button_kwargs).grid(row=0, column=4, padx=4)
        tk.Button(btn_frame, text="Greet", command=self.greet_user, **button_kwargs).grid(row=0, column=5, padx=4)

        list_frame = tk.LabelFrame(
            self,
            text="Stored Notes",
            bg=self.primary_color,
            fg=self.accent_color,
            padx=10,
            pady=10
        )
        list_frame.pack(fill="both", expand=True, padx=20, pady=10)

        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side="right", fill="y")

        self.listbox = tk.Listbox(
            list_frame,
            yscrollcommand=scrollbar.set,
            selectmode="extended",
            font=("Consolas", 10)
        )
        self.listbox.pack(side="left", fill="both", expand=True)

        scrollbar.config(command=self.listbox.yview)
        self.listbox.bind("<<ListboxSelect>>", self.on_list_select)

    def browse_file(self):
        filepath = filedialog.askopenfilename(title="Select file")
        if filepath:
            self.entries["file_link"].delete(0, tk.END)
            self.entries["file_link"].insert(0, filepath)

    def get_inputs(self):
        return {
            "subject": self.entries["subject"].get(),
            "title": self.entries["title"].get(),
            "semester": self.entries["semester"].get(),
            "uploader_name": self.entries["uploader_name"].get(),
            "email": self.entries["email"].get(),
            "file_link": self.entries["file_link"].get(),
            "download_count": self.entries["download_count"].get() or "0"
        }

    def clear_form(self):
        for ent in self.entries.values():
            ent.delete(0, tk.END)

    def load_data(self):
        self.listbox.delete(0, tk.END)

        conn = connect_db()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, uploader_name, title, subject, download_count FROM notes"
            )

            for row in cursor.fetchall():
                text = f"ID:{row[0]} | {row[1]} | {row[2]} ({row[3]}) | DL:{row[4]}"
                self.listbox.insert(tk.END, text)
        finally:
            conn.close()

    def insert_record(self):
        data = self.get_inputs()

        if not data["title"] or not data["uploader_name"]:
            messagebox.showwarning("Input Error", "Title and uploader required.")
            return

        file_path = data["file_link"]

        if not file_path or not os.path.isfile(file_path):
            messagebox.showwarning("File Error", "Please select a valid file.")
            return

        # SAFE FILE TYPES
        allowed_extensions = [".pdf", ".doc", ".docx", ".ppt", ".pptx", ".txt"]
        ext = os.path.splitext(file_path)[1].lower()

        if ext not in allowed_extensions:
            messagebox.showwarning(
                "File Error",
                "Only study files are allowed:\nPDF, DOC, DOCX, PPT, PPTX, TXT"
            )
            return

        notes_folder = "notes"
        os.makedirs(notes_folder, exist_ok=True)

        # AVOID OVERWRITING SAME FILENAMES
        filename = os.path.basename(file_path)
        base, ext = os.path.splitext(filename)
        saved_path = os.path.join(notes_folder, filename)

        counter = 1
        while os.path.exists(saved_path):
            filename = f"{base}_{counter}{ext}"
            saved_path = os.path.join(notes_folder, filename)
            counter += 1

        try:
            shutil.copy2(file_path, saved_path)
        except Exception as e:
            messagebox.showerror("File Error", f"Could not copy file:\n{e}")
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
                data["uploader_name"],
                data["email"],
                saved_path,
                data["download_count"]
            ))
            conn.commit()
            self.clear_form()
            self.load_data()
            messagebox.showinfo("Success", "Record inserted.")
        except sqlite3.Error as e:
            conn.rollback()
            messagebox.showerror("Error", str(e))
        finally:
            conn.close()

    def update_record(self):
        search_name = simpledialog.askstring("Update", "Enter uploader name:")
        if not search_name:
            return

        new_email = simpledialog.askstring("Update", "Enter new email:")
        if not new_email:
            return

        conn = connect_db()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE notes SET email=? WHERE uploader_name=?",
                (new_email, search_name)
            )
            conn.commit()
            self.load_data()
        finally:
            conn.close()

    def delete_record(self):
        selected = self.listbox.curselection()

        conn = connect_db()
        try:
            cursor = conn.cursor()

            if selected:
                item = self.listbox.get(selected[0])
                record_id = int(item.split("|")[0].replace("ID:", "").strip())

                cursor.execute("SELECT file_link FROM notes WHERE id=?", (record_id,))
                row = cursor.fetchone()

                if row and row[0] and os.path.isfile(row[0]):
                    os.remove(row[0])

                cursor.execute("DELETE FROM notes WHERE id=?", (record_id,))
            else:
                value = simpledialog.askstring(
                    "Delete",
                    "Enter uploader name or email:"
                )

                if not value:
                    return

                cursor.execute(
                    "SELECT file_link FROM notes WHERE uploader_name=? OR email=?",
                    (value, value)
                )

                rows = cursor.fetchall()

                for row in rows:
                    if row[0] and os.path.isfile(row[0]):
                        os.remove(row[0])

                cursor.execute(
                    "DELETE FROM notes WHERE uploader_name=? OR email=?",
                    (value, value)
                )

            conn.commit()
            self.load_data()
            self.clear_form()
        finally:
            conn.close()

    def download_note(self):
        selected = self.listbox.curselection()
        if not selected:
            messagebox.showwarning("Select", "Select a note first.")
            return

        item = self.listbox.get(selected[0])
        record_id = int(item.split("|")[0].replace("ID:", "").strip())

        conn = connect_db()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT title, file_link, download_count FROM notes WHERE id=?",
                (record_id,)
            )
            row = cursor.fetchone()

            if not row:
                messagebox.showerror("Error", "Note not found.")
                return

            title, file_path, count = row

            if not file_path or not os.path.isfile(file_path):
                messagebox.showerror("Download Error", "Stored note file not found.")
                return

            save_path = filedialog.asksaveasfilename(
                title="Save Note As",
                initialfile=os.path.basename(file_path)
            )

            if not save_path:
                return

            shutil.copy2(file_path, save_path)

            new_count = (count or 0) + 1
            cursor.execute(
                "UPDATE notes SET download_count=? WHERE id=?",
                (new_count, record_id)
            )

            conn.commit()
            self.load_data()

            messagebox.showinfo(
                "Success",
                f"'{title}' downloaded successfully.\nDownload count: {new_count}"
            )

        except Exception as e:
            conn.rollback()
            messagebox.showerror("Error", str(e))
        finally:
            conn.close()

    def on_list_select(self, event):
        selection = self.listbox.curselection()
        if not selection:
            return

        item = self.listbox.get(selection[0])
        record_id = int(item.split("|")[0].replace("ID:", "").strip())

        conn = connect_db()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM notes WHERE id=?", (record_id,))
            row = cursor.fetchone()

            if row:
                self.clear_form()
                self.entries["subject"].insert(0, row[1] or "")
                self.entries["title"].insert(0, row[2] or "")
                self.entries["semester"].insert(0, row[3] or "")
                self.entries["uploader_name"].insert(0, row[4] or "")
                self.entries["email"].insert(0, row[5] or "")
                self.entries["file_link"].insert(0, row[6] or "")
                self.entries["download_count"].insert(0, row[7] or "")
        finally:
            conn.close()

    def greet_user(self):
        name = self.entries["uploader_name"].get()

        if name:
            messagebox.showinfo("Greeting", f"Hello, {name}!")
        else:
            messagebox.showinfo("Greeting", "Enter uploader name first.")


if __name__ == "__main__":
    app = App()
    app.mainloop()