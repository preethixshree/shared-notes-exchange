# Part D: Admin Dashboard and Synchronization

This module gives Part D equal weightage in the Role-Based Shared Notes Exchange System.

## Purpose

Admin monitors:

- Registered students and faculty from the Part B CGI module.
- Uploaded notes and download counts from the Part C SQLite database.
- Concurrent note access through a reader-writer synchronization demo.

## Synchronization Problem

The project uses the Reader-Writer Problem.

Mapping:

- Students viewing/downloading notes are readers.
- Faculty uploading/updating/deleting notes are writers.
- Admin is the monitor/controller.

Rules:

- Multiple students can read notes at the same time.
- Only one faculty writer can modify notes at a time.
- If a writer is active, readers wait.
- If readers are active, writers wait until readers finish.

## Files

- `reader_writer.py` contains the synchronization lock and threaded demo.
- `admin_dashboard.py` contains the Tkinter admin dashboard.

## Run

From this folder:

```bash
py admin_dashboard.py
```

or:

```bash
python admin_dashboard.py
```

Use **Run Synchronization Demo** to show the concurrent access log.
