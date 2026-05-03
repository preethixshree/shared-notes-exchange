"""Reader-writer synchronization logic for the notes exchange system."""

import random
import threading
import time


class ReaderWriterLock:
    """Allows many readers or one writer to access the shared notes area."""

    def __init__(self):
        self._condition = threading.Condition()
        self._active_readers = 0
        self._writer_active = False
        self._waiting_writers = 0

    def acquire_read(self):
        with self._condition:
            while self._writer_active or self._waiting_writers > 0:
                self._condition.wait()
            self._active_readers += 1
            return self._active_readers

    def release_read(self):
        with self._condition:
            self._active_readers -= 1
            remaining = self._active_readers
            if self._active_readers == 0:
                self._condition.notify_all()
            return remaining

    def acquire_write(self):
        with self._condition:
            self._waiting_writers += 1
            while self._writer_active or self._active_readers > 0:
                self._condition.wait()
            self._waiting_writers -= 1
            self._writer_active = True

    def release_write(self):
        with self._condition:
            self._writer_active = False
            self._condition.notify_all()


class SynchronizationDemo:
    """Runs a reader-writer demo and reports each step through a callback."""

    def __init__(self, logger, on_finish=None, students=None, faculty=None):
        self.lock = ReaderWriterLock()
        self.logger = logger
        self.on_finish = on_finish
        self.threads = []
        self.students = students or ["Sample Student"]
        self.faculty = faculty or ["Sample Faculty"]

    def run(self):
        self.logger("Admin started synchronization demo using registered users.")
        operations = []

        for student in self.students:
            operations.append(("reader", student, "downloads available notes"))

        for faculty in self.faculty:
            operations.append(("writer", faculty, "uploads or updates notes"))

        if len(self.students) == 1:
            operations.append(("reader", self.students[0], "views another note"))

        for index, operation in enumerate(operations):
            kind, actor, action = operation
            target = self.reader if kind == "reader" else self.writer
            thread = threading.Thread(
                target=target,
                args=(actor, action, index * 0.25),
                daemon=True,
            )
            self.threads.append(thread)
            thread.start()

        monitor = threading.Thread(target=self.wait_for_completion, daemon=True)
        monitor.start()

    def reader(self, actor, action, delay):
        time.sleep(delay)
        self.logger(f"{actor} is waiting to read: {action}.")
        active = self.lock.acquire_read()
        self.logger(f"{actor} started reading. Active readers: {active}.")
        time.sleep(random.uniform(0.7, 1.2))
        remaining = self.lock.release_read()
        self.logger(f"{actor} finished reading. Remaining readers: {remaining}.")

    def writer(self, actor, action, delay):
        time.sleep(delay)
        self.logger(f"{actor} is waiting to write: {action}.")
        self.lock.acquire_write()
        self.logger(f"{actor} started writing. Readers are blocked now.")
        time.sleep(random.uniform(0.9, 1.4))
        self.lock.release_write()
        self.logger(f"{actor} finished writing. Waiting users may continue.")

    def wait_for_completion(self):
        for thread in self.threads:
            thread.join()
        self.logger("Synchronization demo completed safely.")
        if self.on_finish:
            self.on_finish()
