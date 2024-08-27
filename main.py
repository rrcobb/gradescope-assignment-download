#!/usr/bin/env python
import json
import os

import requests

from gradescope.macros import (
    get_assignment_template_href,
    get_assignments,
    get_courses,
)

TARGET_DIR = "target"


# so that if we remove these we don't lose the imports to the formatter
def _ignored():
    download_assignment_files
    get_assignments
    get_courses


def groupby(iterable, keyfn):
    """Group items in iterable by keyfn(item)"""
    groups = {}
    for item in iterable:
        key = keyfn(item)
        groups.setdefault(key, []).append(item)
    return groups


def read_json(filename):
    with open(filename, "r") as f:
        return json.load(f)


def write_json(filename, content):
    with open(filename, "w") as f:
        json.dump(content, f)


def write_file(content, filename):
    with open(filename, "wb") as f:
        f.write(content)


def download_file_to_loc(href, filename):
    response = requests.get(href)
    write_file(response.content, filename)


def save_assignment(assignment):
    course_id = assignment["course_id"]
    assignment_id = assignment["id"]

    target_loc = TARGET_DIR + f"/{course_id}_{assignment_id}.pdf"
    if not os.path.exists(target_loc):
        href = get_assignment_template_href(course_id, assignment_id)
        if href:
            print("saving {target_loc}")
            download_file_to_loc(href, filename=target_loc)
        else:
            # if there is not a download pdf link, go to https://www.gradescope.com/courses/{course_id}/assignments/{assignment_id}/rubric/edit
            # pull the html of the questions from there, then turn them into a pdf? They are rendered html here, but we could alternatively get the markdown instead
    else:
        print(f"already downloaded {target_loc}, skipping")


def main():
    # courses = get_courses()
    filename = TARGET_DIR + "/courses.json"
    # write_json(content=courses, filename=filename)
    # courses = read_json(filename=filename)

    # assignments = get_assignments([course["id"] for course in courses])
    filename = TARGET_DIR + "/assignments.json"
    # write_json(content=assignments, filename=filename)
    assignments = read_json(filename=filename)

    assignment = assignments[1]
    save_assignment(assignment)


if __name__ == "__main__":
    main()
