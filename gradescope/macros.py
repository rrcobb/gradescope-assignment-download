import collections as _collections
import csv as _csv
import json
import os as _os
import tempfile as _tempfile

import bs4 as _bs4

import gradescope.api
import gradescope.raw_util
import gradescope.util
from gradescope.raw_util import robust_float

ASSIGNMENT_URL_PATTERN = r"/courses/([0-9]*)/assignments/([0-9]*)$"


class GradescopeRole(gradescope.raw_util.DocEnum):
    # <option value="0">Student</option>
    # <option selected="selected" value="1">Instructor</option>
    # <option value="2">TA</option>
    # <option value="3">Reader</option>

    STUDENT = 0, "Student user"
    INSTRUCTOR = 1, "Instructor user"
    TA = 2, "TA user"
    READER = 3, "Reader user"


def get_assignment_grades(course_id, assignment_id, simplified=False, **kwargs):
    # Fetch the grades
    response = gradescope.api.request(
        endpoint="courses/{}/assignments/{}/scores.csv".format(course_id, assignment_id)
    )

    # Parse the CSV format
    grades = gradescope.util.parse_csv(response.content)

    # Summarize it if necessary by removing question-level data
    if simplified:
        shortened_grades = list(map(gradescope.util.shortened_grade_record, grades))
        return shortened_grades

    # Collapse assignment grades into dictionary key
    grades = gradescope.util.collapse_grades(grades)
    gradescope.util.to_numeric(grades, ("Total Score", "Max Points", "View Count"))

    return grades


def get_assignment_evaluations(course_id, assignment_id, **kwargs):
    response = gradescope.api.request(
        endpoint="courses/{}/assignments/{}/export_evaluations".format(
            course_id, assignment_id
        )
    )

    # Fetch assignment grades for scaffolding
    grades = get_assignment_grades(course_id, assignment_id)

    if len(grades) == 0:
        return []

    subid_grades = {person["Submission ID"]: person for person in grades}

    # Open temp directory for extraction
    with _tempfile.TemporaryDirectory() as td:
        file_path = gradescope.util.extract_evaluations(td, response.content)

        # Find question name for each sheet
        sheets = [i for i in _os.listdir(file_path) if ".csv" in i]
        sheet_map = gradescope.util.map_sheets(sheets, grades[0]["questions"].keys())

        # Read questions from each sheet
        for sheet in sheets:
            q_name = sheet_map[sheet]
            with open(_os.path.join(file_path, sheet)) as csvfile:
                reader = _csv.DictReader(
                    csvfile,
                    quotechar='"',
                    delimiter=",",
                    quoting=_csv.QUOTE_ALL,
                    skipinitialspace=True,
                )
                # Match rows to students
                for row in reader:
                    if row["Assignment Submission ID"] not in subid_grades:
                        continue

                    subid = row["Assignment Submission ID"]

                    new_row = gradescope.util.read_eval_row(row)

                    if new_row["score"] != subid_grades[subid]["questions"][q_name]:
                        raise ValueError("Mismatched scores!")

                    subid_grades[subid]["questions"][q_name] = new_row

    return list(subid_grades.values())


def get_course_roster(course_id, **kwargs):
    # Fetch the grades
    response = gradescope.api.request(
        endpoint="courses/{}/memberships.csv".format(course_id)
    )

    # Parse the CSV format
    roster = gradescope.util.parse_csv(response.content)

    return roster


def invite_many(course_id, role, users, **kwargs):
    # type: (int, GradescopeRole, _typing.List[_typing.Tuple[str, str]], dict) -> bool

    # Built payload
    payload = _collections.OrderedDict()
    counter = 0
    for email, name in users:
        payload["students[{}][name]".format(counter)] = name
        payload["students[{}][email]".format(counter)] = email
        counter += 1
    payload["role"] = role

    # Fetch the grades
    response = gradescope.api.request(
        endpoint="courses/{}/memberships/many".format(course_id),
        data=payload,
    )

    return response.status_code == 200


def get_courses():
    response = gradescope.api.request(endpoint="account")
    soup = _bs4.BeautifulSoup(response.content, features="html.parser")
    course_boxes = soup.find_all("a", {"class": "courseBox"})
    courses = []
    for box in course_boxes:
        href = box.get("href")
        course_id = href.split("/")[-1]
        course_code = box.find("h3", {"class": "courseBox--shortname"}).text
        course_name = box.find("div", {"class": "courseBox--name"}).text
        courses.append(
            {
                "name": course_name,
                "id": course_id,
                "code": course_code,
            }
        )
    return courses


# gets all assignments
def get_assignments(course_ids):
    assert len(course_ids) > 0
    course_page_id = course_ids[0]
    endpoint = f"courses/{course_page_id}/assignments"
    result = gradescope.api.request(endpoint=endpoint)
    soup = _bs4.BeautifulSoup(result.content.decode(), features="html.parser")

    all_assignment_table = soup.select_one("ul.treeSelector")
    course_rows = all_assignment_table.findChildren("li", {"class": "js-courseRow"})
    assignments = []
    for course_row in course_rows:
        course_id = course_row.findChild("button").get("id").split("course-")[1]
        if course_id not in course_ids:
            continue
        course_code = course_row.findChild("div", {"class": "type-heading"}).text
        assignment_rows = course_row.findChildren("li", {"class": "js-assignmentRow"})

        for row in assignment_rows:
            buttons = row.find_all("button")

            assignment = None
            for button in buttons:
                assignment_id = button.get("data-assignment-id")
                assignment = {
                    "id": assignment_id,
                    "name": button.text,
                    "course_id": course_id,
                    "course_code": course_code,
                    "href": f"https://gradescope.com/courses/{course_id}/assignments/{assignment_id}",
                }

            if assignment is None:
                continue

            assignments.append(assignment)
    return assignments


def find(iterable, condition):
    return next((item for item in iterable if condition(item)), None)


def get_assignment_submissions(course_id, assignment_id, **kwargs):
    endpoint = f"courses/{course_id}/assignments/{assignment_id}/review_grades"
    result = gradescope.api.request(endpoint=endpoint)
    soup = _bs4.BeautifulSoup(result.content.decode(), features="html.parser")

    submissions_table = soup.find("table", {"class": "js-reviewGradesTable"})
    submissions_rows = submissions_table.findChildren("tr")

    submissions = []
    for row in submissions_rows:
        cells = row.find_all("td")

        # Get the student name and submission ID
        student_name = cells[0].text.strip()
        anchor = cells[0].find("a")
        href = anchor.get("href") if anchor else None
        submission_id = href.split("/")[-1] if href else None

        if not href or not submission_id:
            continue

        # Get the email
        celltexts = [c.text.strip() for c in cells]
        email = find(celltexts, lambda c: "@" in c)

        submissions.append(
            {"id": submission_id, "href": href, "name": student_name, "email": email}
        )

    return submissions


def get_image(path):
    result = gradescope.api.request(endpoint=path)
    return result


def get_data_from_assignment(course_id, assignment_id):
    outline_url = f"https://www.gradescope.com/courses/{course_id}/assignments/{assignment_id}/outline/edit"
    result = gradescope.api.request(endpoint=outline_url)
    soup = _bs4.BeautifulSoup(result.content.decode(), features="html.parser")

    editor = soup.select_one("#main-content div")
    title = soup.select_one("h2.sidebar--title").get("title")
    attr = editor.get("data-react-props")
    react_props = json.loads(attr)
    data = {"title": title}
    return data | react_props


def get_assignment_template_href(course_id, assignment_id):
    # go to https://www.gradescope.com/courses/{course_id}/assignments/{assignment_id}/edit
    # get the 'download pdf' link, pull the pdf from there, save it
    #    (this works for upload-style assignments)
    edit_page_url = f"courses/{course_id}/assignments/{assignment_id}/edit"
    result = gradescope.api.request(endpoint=edit_page_url)
    soup = _bs4.BeautifulSoup(result.content.decode(), features="html.parser")

    download_pdf_button = soup.select_one(".fileUpload a.tiiBtn")
    if download_pdf_button:
        pdf_href = download_pdf_button.get("href")
        return pdf_href

    # Returns None if there is no template to download


def get_course_grades(course_id, only_graded=True, use_email=True):
    # Dictionary mapping student emails to grades
    grades = {}

    gradescope_assignments = get_course_assignments(course_id=course_id)

    for assignment in gradescope_assignments:
        # {'id': '273671', 'name': 'Written Exam 1'}
        assignment_name = assignment["name"]
        assignment_grades = get_assignment_grades(
            course_id=course_id, assignment_id=assignment.get("id"), simplified=True
        )

        for record in assignment_grades:
            # {'name': 'Joe Student',
            #   'sid': 'jl27',
            #   'email': 'jl27@princeton.edu',
            #   'score': '17.75',
            #   'graded': True,
            #   'view_count': '4',
            #   'id': '22534979'}

            if only_graded and not record.get("graded", False):
                continue

            student_id = record["sid"]
            if use_email:
                student_id = record["email"]
            grade = robust_float(record.get("score"))

            # Add grade to student
            grades[student_id] = grades.get(student_id, dict())
            grades[student_id][assignment_name] = grade

    return grades
