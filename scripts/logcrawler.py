import os
import re
from datetime import datetime
from collections import defaultdict
import logging

import aw_core

logging.basicConfig()

log_dir = aw_core.dirs.get_log_dir("")


def get_filepaths():
    filepaths = []
    for folder, dirs, files in os.walk(log_dir):
        print("Crawling folder: " + folder)

        if False:
            print("Files: ")
            for filename in files:
                print(" - " + filename)

        filepaths.extend([os.path.join(folder, filename) for filename in files])
    return filepaths


def collect():
    matched_lines = defaultdict(lambda: [])
    for filepath in sorted(get_filepaths()):
        with open(filepath, "r") as f:
            log = f.read()
            for line in log.split("\n"):
                s = re.search("(ERR|WARN)", line)
                ignored = re.search("(CORS|Deleted bucket)", line)
                if s and not ignored:
                    matched_lines[filepath].append(line)
    return matched_lines


_date_reg_exp = re.compile('\d{4}-\d{2}-\d{2}')


today = datetime.now()


def line_age(line):
    """Returns line age in days"""
    match = _date_reg_exp.search(line)
    if not match:
        logging.warning("Line had no date, avoid multiple line messages in logs. Line will have its age set to zero.")
        return 0
    else:
        dt = datetime.strptime(match.group(), '%Y-%m-%d')
        td = today - dt
        return td.days


def main(exclude_testing: bool = False, limit_days: int = 10, limit_lines: int = 10):
    file_lines = collect()

    if exclude_testing:
        keys = filter(lambda k: "testing" not in k, file_lines.keys())
        file_lines = {key: file_lines[key] for key in keys}

    for filename, lines in sorted(file_lines.items()):
        lines = sorted(file_lines[filename], reverse=True)

        # Filter lines older than x days
        if limit_days:
            lines = [line for line in lines if line_age(line) <= limit_days]

        if lines:
            print("-" * 50)
            print("File: {}".format(filename))

            # Print lines up to the limit
            for line in lines[:limit_lines]:
                print("  " + line)

            if limit_lines < len(lines):
                print("Showing {} out of {} lines".format(limit_lines, len(lines)))


if __name__ == "__main__":
    main()
