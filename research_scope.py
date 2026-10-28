"""Read-only study scope shared by every analysis of the grade archive.

The archive remains intact. Temporary views hide classes excluded from this
research before any count, correlation, or chart is calculated.
"""

import sqlite3
from pathlib import Path


EXCLUDED_CLASSES = (
    ("2022-2023", "11 база"),
    ("2024-2025", "10Эк"),
)


def connect_study_database(path):
    con = sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    con.execute("CREATE TEMP TABLE research_excluded_groups(group_id INTEGER PRIMARY KEY)")
    excluded_ids = []
    for school_year, label in EXCLUDED_CLASSES:
        rows = con.execute(
            "SELECT group_id FROM main.teaching_groups WHERE school_year=? AND label=?",
            (school_year, label),
        ).fetchall()
        if not rows:
            raise ValueError(f"Excluded class not found: {school_year} {label}")
        excluded_ids.extend(row["group_id"] for row in rows)
    con.executemany(
        "INSERT INTO research_excluded_groups VALUES (?)",
        ((group_id,) for group_id in excluded_ids),
    )

    views = {
        "teaching_groups": """SELECT * FROM main.teaching_groups
            WHERE group_id NOT IN (SELECT group_id FROM research_excluded_groups)""",
        "enrollments": """SELECT en.* FROM main.enrollments en
            JOIN teaching_groups g USING(group_id)""",
        "assessment_events": """SELECT e.* FROM main.assessment_events e
            JOIN teaching_groups g USING(group_id)""",
        "homework_coverage": """SELECT h.* FROM main.homework_coverage h
            JOIN teaching_groups g USING(group_id)""",
        "students": """SELECT st.* FROM main.students st
            WHERE EXISTS (SELECT 1 FROM enrollments en WHERE en.student_id=st.student_id)""",
        "observations": """SELECT o.* FROM main.observations o
            JOIN assessment_events e USING(event_id)
            JOIN enrollments en USING(enrollment_id)""",
        "v_homework": """SELECT h.* FROM main.v_homework h
            WHERE EXISTS (SELECT 1 FROM teaching_groups g
                          WHERE g.school_year=h.school_year AND g.label=h.group_label)""",
    }
    for name, query in views.items():
        con.execute(f"CREATE TEMP VIEW {name} AS {query}")
    return con
