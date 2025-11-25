""" Class to keep a log of the game.
The challenge here was to make it thread-safe: simulator plays several games at a time,
but the game log should be written by "whole game" chunks. This is the reason games
will not be in order, as the order games start is different from the order they finish.
"""

import multiprocessing
from os import PathLike
from typing import Union


class Log:
    """ Class to handle logging of game events
    """
    # Lock is declared on the class level,
    # so it would be shared among processes
    lock = multiprocessing.Lock()

    def __init__(self, log_file_name: Union[str, PathLike] = "log.txt", disabled: bool = False):
        self.log_file_name = log_file_name
        self.content = []
        self.disabled = disabled
        self._flushed_count = 0  # Track how many items have been flushed

    def add(self, data):
        """ Add a line to a Log
        """
        if self.disabled:
            return
        self.content.append(data)

    def save(self):
        """ Write out the log (writes any remaining content not yet flushed)
        """
        if self.disabled:
            return
        remaining = self.content[self._flushed_count:]
        if remaining:
            with self.lock:
                with open(self.log_file_name, "a", encoding="utf-8") as logfile:
                    logfile.write("\n".join(remaining))
                    logfile.write("\n")
                self._flushed_count = len(self.content)
    
    def flush(self):
        """ Flush current content to file immediately (for real-time updates)
        """
        if self.disabled or not self.content:
            return
        with self.lock:
            new_content = self.content[self._flushed_count:]
            if new_content:
                with open(self.log_file_name, "a", encoding="utf-8") as logfile:
                    logfile.write("\n".join(new_content))
                    logfile.write("\n")
                    logfile.flush()
                self._flushed_count = len(self.content)

    def reset(self, first_line=""):
        """ Empty the log file, write first_line if provided
        """
        with self.lock:
            with open(self.log_file_name, "w", encoding="utf-8") as logfile:
                logfile.write(f"{first_line}\n")
