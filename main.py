#!/usr/bin/env python
import json
import os
import re
from urllib.parse import urljoin

import requests
from fpdf import FPDF

from gradescope.macros import (
    get_assignment_template_href,
    get_assignments,
    get_courses,
    get_data_from_assignment,
    get_image,
)

TARGET_DIR = "target"


# so that if we remove these we don't lose the imports to the formatter
def _ignored():
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


def download_images(text):
    image_pattern = r"!\[([^\]]*)\]\((/files/[^)]+)\)"
    downloaded_images = {}

    for match in re.finditer(image_pattern, text):
        alt_text, file_path = match.groups()
        local_filename = "tmp/" + os.path.basename(file_path)

        result = get_image(file_path)
        if not result:
            raise Exception("no image?")
        with open(local_filename, "wb") as f:
            f.write(result.content)
            downloaded_images[file_path] = local_filename

    return downloaded_images


def format_text(pdf, text, font, downloaded_images):
    # Simplified patterns without capture groups
    code_block_pattern = r"```[\s\S]*?```"
    inline_code_pattern = r"`[^`\n]+`"
    image_pattern = r"!\[[^\]]*\]\(/files/[^)]+\)"

    # Combine patterns
    combined_pattern = f"{code_block_pattern}|{inline_code_pattern}|{image_pattern}"

    # Split the text into parts
    parts = re.split(f"({combined_pattern})", text)

    for part in parts:
        if part.startswith("```") and part.endswith("```"):
            # Code block
            pdf.set_font("Latin Modern Mono", "", 10)
            code = part.strip("`").strip()
            pdf.multi_cell(0, text=code)
            pdf.set_font(*font)
        elif part.startswith("`") and part.endswith("`"):
            # Inline code
            pdf.set_font("Latin Modern Mono", "", 10)
            code = part.strip("`")
            pdf.write(text=code)
            pdf.set_font(*font)
        elif part.startswith("!") and part.endswith(")"):
            # Image
            img_match = re.match(r"!\[([^\]]*)\]\((/files/[^)]+)\)", part)
            if not img_match:
                raise Exception("wait, no image?")
            alt_text, file_path = img_match.groups()
            image_file = downloaded_images[file_path]
            img_width = pdf.w - 2 * pdf.l_margin  # Full width minus margins
            pdf.image(image_file, x=pdf.l_margin, w=img_width)
        else:
            # Normal text
            pdf.set_font(*font)
            pdf.write(text=part)


class PDFWithCustomFonts(FPDF):
    def __init__(self):
        super().__init__()
        self.add_font("CMU Serif", "", "fonts/cmu-serif/cmunrm.ttf")
        self.add_font("CMU Serif", "B", "fonts/cmu-serif/cmunbx.ttf")
        self.add_font(
            "Latin Modern Roman", "", "fonts/latin-modern-roman/lmroman10-regular.otf"
        )
        self.add_font(
            "Latin Modern Roman", "B", "fonts/latin-modern-roman/lmroman10-bold.otf"
        )
        self.add_font(
            "Latin Modern Mono", "", "fonts/latin-modern-roman/lmmono10-regular.otf"
        )


def write_markup_to_pdf(data, filename):
    # Download any images in advance
    all_text = ""
    for question in data["questions"].values():
        for content in question["content"]:
            if content["type"] == "text":
                all_text += content["value"] + "\n"

    downloaded_images = download_images(all_text)

    pdf = PDFWithCustomFonts()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.set_font("CMU Serif", "B", 16)
    pdf.write(text=data["title"])
    pdf.ln(10)

    # Set font for the questions
    question_font = ("CMU Serif", "B", 14)
    text_font = ("Latin Modern Roman", "", 12)
    choice_font = ("Latin Modern Roman", "", 12)

    for i, (question_id, question_data) in enumerate(
        data["questions"].items(), start=1
    ):
        pdf.set_font(*question_font)
        pdf.cell(0, 10, f"Q{i}. {question_data['title']}", 0, 1)
        pdf.ln(2)

        for content in question_data["content"]:
            if content["type"] == "text":
                format_text(pdf, content["value"], text_font, downloaded_images)
            elif content["type"] == "radio_input":
                pdf.ln(8)
                for j, choice in enumerate(content["choices"]):
                    choice_text = f"    {chr(65 + j)}. {choice['value']}"
                    format_text(pdf, choice_text, choice_font, downloaded_images)
                    pdf.ln(8)

        # Add more space before the next question
        pdf.ln(8)

    pdf.output(filename)

    # Clean up downloaded images
    for image_file in downloaded_images.values():
        os.remove(image_file)


def save_assignment(assignment=None, course_id=None, assignment_id=None):
    if assignment:
        course_id = assignment["course_id"]
        assignment_id = assignment["id"]

    target_loc = TARGET_DIR + f"/{course_id}_{assignment_id}.pdf"

    if not os.path.exists(target_loc):
        href = get_assignment_template_href(course_id, assignment_id)
        if href:
            print(f"saving {target_loc}")
            download_file_to_loc(href, filename=target_loc)
        else:
            # if there is not a download pdf link, fetch the markdown contents of the assignment instead
            data = get_data_from_assignment(
                course_id=course_id, assignment_id=assignment_id
            )
            assignment_type = data.get("assignment").get("type")

            if assignment_type == "ProgrammingAssignment":
                print("programming assignment, skipping", course_id, assignment_id)
                return
            if data.get("questions"):
                # question data exists
                # turn them into a pdf
                write_markup_to_pdf(data, filename=target_loc)
            else:
                print("not sure how to handle assignment type", data)
                exit()
    else:
        print(f"already downloaded {target_loc}, skipping")


def save_assignments():
    # courses = get_courses()
    filename = TARGET_DIR + "/courses.json"
    # write_json(content=courses, filename=filename)
    # courses = read_json(filename=filename)
    # assignments = get_assignments([course["id"] for course in courses])
    filename = TARGET_DIR + "/assignments.json"
    # write_json(content=assignments, filename=filename)
    assignments = read_json(filename=filename)
    for assignment in assignments:
        save_assignment(assignment)


def main():
    # https://www.gradescope.com/courses/561134/assignments/4315589/outline/edit
    # save_assignment(course_id=561134, assignment_id=4315589)
    save_assignments()


if __name__ == "__main__":
    main()
