import os.path
from pathlib import Path
from logging_setup import logger
from time import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


class ModifiedFileHandler(FileSystemEventHandler):
    def __init__(self, file_name):
        self.last_modified = time()
        self.file_name = file_name

    def on_modified(self, event):
        if not event.is_directory and event.src_path.endswith(self.file_name):
            current_time = time()
            if (current_time - self.last_modified) > 0.1:
                FileHandler.is_modified = True
                logger.info(f"FILE HANDLER | File {event.src_path} was just modified")
                self.last_modified = current_time


class FileHandler:
    is_modified = True

    def __init__(self, file_path, file_name):
        self.file_path = file_path
        self.event_handler = ModifiedFileHandler(file_name)
        # self.watched_dir = os.path.split(self.file_path)[0]
        self.watched_dir = Path(file_path).absolute().as_posix()
        self.observer = Observer()

    async def run(self):
        self.observer.schedule(self.event_handler, self.watched_dir, recursive=False)
        self.observer.start()
