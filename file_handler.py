import os.path
from logging_setup import logger
from time import time
from watchdog.observers import Observer
from watchdog.events import PatternMatchingEventHandler


class ModifiedFileHandler(PatternMatchingEventHandler):
    last_modified = 0

    def on_modified(self, event):
        super(ModifiedFileHandler, self).on_modified(event)
        current_time = time()
        if (current_time - self.last_modified) > 0.1:
            logger.info(f"File {event.src_path} was just modified")
            self.last_modified = current_time


class FileHandler:
    def __init__(self, file_path):
        self.file_path = file_path
        self.event_handler = ModifiedFileHandler(patterns=[self.file_path])
        self.watched_dir = os.path.split(self.file_path)[0]
        self.observer = Observer()

    async def run(self):
        self.observer.schedule(self.event_handler, self.watched_dir, recursive=False)
        self.observer.start()
