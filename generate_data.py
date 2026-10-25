"""Build anonymous dashboard data from the local grade database."""

from __future__ import annotations

import json
import math
import sqlite3
import statistics
from collections import defaultdict
from datetime import date
from functools import lru_cache
from pathlib import Path
from experiment_data import build_experiment


HERE = Path(__file__).resolve().parent
DB = HERE.parent / "Оценки_Арабули_2012-2026.sqlite"
OUT = HERE / "dist" / "data.js"

COHORTS = {
    ("2023-2024", "7Б"): 7,
    ("2023-2024", "7Д"): 7,
    ("2024-2025", "8Б"): 8,
    ("2024-2025", "8Д"): 8,
    ("2025-2026", "9Б"): 9,
    ("2025-2026", "9Д"): 9,
}

METRICS = {
    "kr": "КР",
    "sr": "Летучки",
    "credit": "Зачёты",
}


def mean(values):
    values = list(values)
    return sum(values) / len(values) if values else None


def pearson(points):
    if len(points) < 3:
        return None
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    mx, my = mean(xs), mean(ys)
    denx = sum((x - mx) ** 2 for x in xs)
    deny = sum((y - my) ** 2 for y in ys)
    if denx == 0 or deny == 0:
        return None
    return sum((x - mx) * (y - my) for x, y in points) / math.sqrt(denx * deny)


con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row

# Mean block KPI (КПД) of checked homework. This is the same measure used in
# the reviewed 7–9 report and can exceed 100% when bonus work is present.
homework = {}
for row in con.execute(
    """SELECT student_id,school_year,group_label,
              AVG(numeric_value) AS rate,COUNT(*) AS n
       FROM v_homework
       WHERE event_kind='homework_ratio'
         AND numeric_value IS NOT NULL
         AND check_status='recorded_check'
       GROUP BY student_id,school_year,group_label"""
):
    key = (row["school_year"], row["group_label"])
    if key in COHORTS and row["n"] >= 2:
        homework[(row["student_id"], *key)] = (row["rate"], row["n"])

# Structured independent grades. In grade 9, the block summary columns
# "Лет" and "Зач" are retained as mark_unspecified in the source database;
# the explicit headers let us classify those two summaries here.
outcomes = defaultdict(list)
rows = con.execute(
    """SELECT st.student_id,g.school_year,g.label AS group_label,
              e.event_kind,e.header_primary,o.grade_value
       FROM observations o
       JOIN assessment_events e USING(event_id)
       JOIN enrollments en USING(enrollment_id)
       JOIN students st USING(student_id)
       JOIN teaching_groups g USING(group_id)
       JOIN source_sheets ss USING(sheet_id)
       WHERE o.grade_value IS NOT NULL AND ss.status='included'
         AND g.school_year>='2023-2024'"""
)
for row in rows:
    cohort = (row["school_year"], row["group_label"])
    if cohort not in COHORTS:
        continue
    grade = COHORTS[cohort]
    kind = row["event_kind"]
    header = (row["header_primary"] or "").strip().upper()
    metric = None
    if kind == "test_grade_inferred":
        metric = "kr"
    elif kind == "quiz_grade":
        metric = "sr"
    elif kind == "credit_grade":
        metric = "credit"
    elif grade == 9 and kind == "mark_unspecified" and header.startswith("ЛЕТ"):
        metric = "sr"
    elif grade == 9 and kind == "mark_unspecified" and header.startswith("ЗАЧ"):
        metric = "credit"
    if metric:
        outcomes[(row["student_id"], *cohort, metric)].append(row["grade_value"])


def grade_bucket(value):
    """Map numeric marks to the familiar 2/3/4/5 scale."""
    return str(max(2, min(5, int(round(value)))))


def homework_grade_from_rate(rate):
    """Convert homework completion share to the standard 2–5 scale."""
    if rate >= 0.85:
        return "5"
    if rate >= 0.70:
        return "4"
    if rate >= 0.50:
        return "3"
    return "2"


# Distribution of every independent mark by school grade and work type.
distribution_by_grade = []
for grade in (7, 8, 9):
    for metric, metric_label in METRICS.items():
        counts = {str(mark): 0 for mark in range(2, 6)}
        for (student_id, year, group, item_metric), values in outcomes.items():
            if item_metric != metric or COHORTS.get((year, group)) != grade:
                continue
            for value in values:
                counts[grade_bucket(value)] += 1
        distribution_by_grade.append(
            {
                "grade": grade,
                "metric": metric,
                "metricLabel": metric_label,
                "counts": counts,
                "total": sum(counts.values()),
            }
        )

# Timeline of full-class grade 9 tests. Events with fewer than 20 marks are
# retakes or corrections and would distort the class distribution.
timeline_events = defaultdict(lambda: {"counts": {str(mark): 0 for mark in range(2, 6)}, "values": []})
timeline_rows = con.execute(
    """SELECT e.event_id,e.event_date,g.label AS group_label,o.grade_value
       FROM observations o
       JOIN assessment_events e USING(event_id)
       JOIN enrollments en USING(enrollment_id)
       JOIN teaching_groups g USING(group_id)
       JOIN source_sheets ss USING(sheet_id)
       WHERE g.school_year='2025-2026'
         AND g.label IN ('9Б','9Д')
         AND e.event_kind='test_grade_inferred'
         AND e.event_date IS NOT NULL
         AND o.grade_value IS NOT NULL
         AND ss.status='included'"""
)
for row in timeline_rows:
    key = (row["event_id"], row["event_date"], row["group_label"])
    timeline_events[key]["counts"][grade_bucket(row["grade_value"])] += 1
    timeline_events[key]["values"].append(row["grade_value"])

timeline_kr9 = []
for (event_id, event_date, group), event in timeline_events.items():
    if len(event["values"]) < 20:
        continue
    timeline_kr9.append(
        {
            "date": event_date,
            "group": group,
            "counts": event["counts"],
            "total": len(event["values"]),
            "mean": round(mean(event["values"]), 2),
        }
    )
timeline_kr9.sort(key=lambda item: (item["group"], item["date"]))

series = []
student_year = {}
for grade in (7, 8, 9):
    for metric, metric_label in METRICS.items():
        points = []
        for (student_id, year, group), (hw_rate, hw_n) in homework.items():
            if COHORTS.get((year, group)) != grade:
                continue
            values = outcomes.get((student_id, year, group, metric), [])
            if not values:
                continue
            grade_mean = mean(values)
            points.append(
                {
                    "x": round(hw_rate * 100, 1),
                    "y": round(grade_mean, 2),
                    "group": group,
                    "homeworkCount": hw_n,
                    "gradeCount": len(values),
                }
            )
            student_year[(student_id, grade, metric)] = grade_mean
            student_year[(student_id, grade, "hw")] = hw_rate
        r = pearson([(p["x"], p["y"]) for p in points])
        series.append(
            {
                "grade": grade,
                "metric": metric,
                "metricLabel": metric_label,
                "r": round(r, 3) if r is not None else None,
                "n": len(points),
                "points": points,
            }
        )

# Same students from grade 8 to grade 9.
paired = []
student_ids = {key[0] for key in student_year}
for student_id in student_ids:
    required = [
        (student_id, 8, "hw"),
        (student_id, 9, "hw"),
        (student_id, 8, "kr"),
        (student_id, 9, "kr"),
    ]
    if all(key in student_year for key in required):
        paired.append(
            {
                "hw": (student_year[(student_id, 9, "hw")] - student_year[(student_id, 8, "hw")]) * 100,
                "kr": student_year[(student_id, 9, "kr")] - student_year[(student_id, 8, "kr")],
            }
        )

years = con.execute("SELECT COUNT(DISTINCT school_year) FROM teaching_groups").fetchone()[0]
students = con.execute("SELECT COUNT(*) FROM students").fetchone()[0]
observations = con.execute("SELECT COUNT(*) FROM observations").fetchone()[0]
linked = con.execute(
    """SELECT COUNT(*) FROM (
         SELECT student_id FROM enrollments en JOIN teaching_groups g USING(group_id)
         GROUP BY student_id HAVING COUNT(DISTINCT g.school_year)>1)"""
).fetchone()[0]

# Dashboard-wide counts. "Grades" excludes homework marks.
independent_grade_count = con.execute(
    """SELECT COUNT(*)
       FROM observations o
       JOIN assessment_events e USING(event_id)
       JOIN source_sheets ss USING(sheet_id)
       WHERE ss.status='included' AND o.grade_value IN (2,3,4,5)
         AND e.event_kind NOT LIKE 'homework%'"""
).fetchone()[0]

# Count a class cohort once as it advances through the grades. Adjacent years
# are linked by shared students using a one-to-one maximum-overlap matching.
# The special-physics group duplicates a regular class roster, so it is a
# course group rather than another class cohort.
cohort_groups = []
for row in con.execute(
    """SELECT group_id,school_year,grade_level,label
       FROM teaching_groups ORDER BY school_year,grade_level,label"""
):
    if "спецфиз" in row["label"].lower():
        continue
    cohort_groups.append(dict(row))

rosters = defaultdict(set)
for row in con.execute("SELECT group_id,student_id FROM enrollments"):
    rosters[row["group_id"]].add(row["student_id"])

groups_by_year = defaultdict(list)
for group in cohort_groups:
    groups_by_year[group["school_year"]].append(group)


def best_year_matching(left, right):
    """Return maximum-cardinality, then maximum-overlap adjacent links."""
    candidates = {}
    for i, before in enumerate(left):
        for j, after in enumerate(right):
            if after["grade_level"] != before["grade_level"] + 1:
                continue
            overlap = len(rosters[before["group_id"]] & rosters[after["group_id"]])
            if overlap >= 5:
                candidates[(i, j)] = overlap

    @lru_cache(maxsize=None)
    def solve(i, used_mask):
        if i == len(left):
            return (0, 0)
        best = solve(i + 1, used_mask)
        for j in range(len(right)):
            if used_mask & (1 << j) or (i, j) not in candidates:
                continue
            tail = solve(i + 1, used_mask | (1 << j))
            option = (tail[0] + 1, tail[1] + candidates[(i, j)])
            if option > best:
                best = option
        return best

    return solve(0, 0)[0]


year_names = sorted(groups_by_year)
cohort_links = 0
for year, next_year in zip(year_names, year_names[1:]):
    if int(next_year[:4]) != int(year[:4]) + 1:
        continue
    cohort_links += best_year_matching(groups_by_year[year], groups_by_year[next_year])
unique_cohort_count = len(cohort_groups) - cohort_links

# Comparable distribution for the full archive. Newer journals label tests
# and quizzes; older journals usually only identify the work by a valid date,
# so those dated marks are pooled into the same written-work category.
archive_distribution = defaultdict(lambda: {"counts": {str(mark): 0 for mark in range(2, 6)}, "groups": set()})
for row in con.execute(
    """SELECT g.school_year,g.grade_level,g.label AS group_label,
              e.event_kind,e.event_date,e.date_valid_for_year,o.grade_value
       FROM observations o
       JOIN assessment_events e USING(event_id)
       JOIN teaching_groups g USING(group_id)
       JOIN source_sheets ss USING(sheet_id)
       WHERE ss.status='included' AND o.grade_value IN (2,3,4,5)"""
):
    kind = row["event_kind"]
    comparable = kind in {"test_grade_inferred", "quiz_grade"}
    comparable = comparable or (
        kind == "mark_unspecified" and row["event_date"] and row["date_valid_for_year"]
    )
    if not comparable or row["grade_level"] is None:
        continue
    key = (row["school_year"], row["group_label"], row["grade_level"])
    archive_distribution[key]["counts"][grade_bucket(row["grade_value"])] += 1
    archive_distribution[key]["groups"].add(row["group_label"])

archive_distribution_rows = []
for year, grade_level, group_label in con.execute(
    """SELECT school_year,grade_level,label FROM teaching_groups
       WHERE grade_level IS NOT NULL ORDER BY school_year,grade_level,label"""
):
    if "спецфиз" in group_label.lower():
        continue
    key = (year, group_label, grade_level)
    archive_distribution[key]["groups"].add(group_label)

for (year, group_label, grade_level), entry in sorted(archive_distribution.items()):
    if "спецфиз" in group_label.lower():
        continue
    counts = entry["counts"]
    archive_distribution_rows.append({
        "year": year,
        "grade": grade_level,
        "group": group_label,
        "groups": sorted(entry["groups"]),
        "counts": counts,
        "total": sum(counts.values()),
    })

# The requested archive-wide distribution gives every class-year equal
# weight, so a large journal does not dominate a small one.
distribution_rows_with_data = [row for row in archive_distribution_rows if row["total"]]
archive_average_shares = {
    mark: round(mean(row["counts"][mark] / row["total"] * 100 for row in distribution_rows_with_data), 3)
    for mark in ("2", "3", "4", "5")
}
archive_average_distribution = {
    "grade": 0,
    "shares": archive_average_shares,
    "classYears": len(distribution_rows_with_data),
    "totalGrades": sum(row["total"] for row in distribution_rows_with_data),
}

archive_parallel_distributions = [archive_average_distribution]
for grade_level in range(7, 12):
    grade_rows = [
        row for row in distribution_rows_with_data if row["grade"] == grade_level
    ]
    archive_parallel_distributions.append({
        "grade": grade_level,
        "shares": {
            mark: round(mean(row["counts"][mark] / row["total"] * 100 for row in grade_rows), 3)
            for mark in ("2", "3", "4", "5")
        },
        "classYears": len(grade_rows),
        "totalGrades": sum(row["total"] for row in grade_rows),
    })

# Comparable grade distributions for class-years where homework was not
# checked. The two 2025–2026 exceptions are shorter blocks; their assessment
# columns are the corresponding block sections in the 9Б/9Д journals.
archive_distribution_lookup = {
    (row["year"], row["group"], row["grade"]): row
    for row in archive_distribution_rows
}
unchecked_period_rows = []
for row in con.execute(
    """SELECT DISTINCT g.school_year,g.grade_level,g.label
       FROM homework_coverage h JOIN teaching_groups g USING(group_id)
       WHERE h.status='no_recorded_check'
       ORDER BY g.school_year,g.grade_level,g.label"""
):
    if "спецфиз" in row["label"].lower():
        continue
    distribution_row = archive_distribution_lookup.get(
        (row["school_year"], row["label"], row["grade_level"])
    )
    if distribution_row and distribution_row["total"]:
        unchecked_period_rows.append({
            **distribution_row,
            "period": f'{row["school_year"]} {row["label"]}',
            "periodType": "year",
        })

block_sections = [
    {"group": "9Д", "block": "4", "start": 48, "end": 59},
    {"group": "9Б", "block": "5", "start": 61, "end": 73},
]
unchecked_block_counts = {}
for section in block_sections:
    coverage_exists = con.execute(
        """SELECT 1 FROM homework_coverage h JOIN teaching_groups g USING(group_id)
           WHERE g.school_year='2025-2026' AND g.label=?
             AND h.block_label=? AND h.status='assigned_answers_given_not_checked'""",
        (section["group"], section["block"]),
    ).fetchone()
    if not coverage_exists:
        continue
    counts = {str(mark): 0 for mark in range(2, 6)}
    for row in con.execute(
        """SELECT e.event_kind,e.event_date,e.date_valid_for_year,o.grade_value
           FROM observations o JOIN assessment_events e USING(event_id)
           JOIN teaching_groups g ON g.group_id=e.group_id
           JOIN source_sheets ss USING(sheet_id)
           WHERE g.school_year='2025-2026' AND g.label=?
             AND e.source_column BETWEEN ? AND ?
             AND ss.status='included' AND o.grade_value IN (2,3,4,5)""",
        (section["group"], section["start"], section["end"]),
    ):
        comparable = row["event_kind"] in {"test_grade_inferred", "quiz_grade"}
        comparable = comparable or (
            row["event_kind"] == "mark_unspecified"
            and row["event_date"] and row["date_valid_for_year"]
        )
        if comparable:
            counts[grade_bucket(row["grade_value"])] += 1
    total = sum(counts.values())
    if total:
        unchecked_block_counts[("2025-2026", section["group"])] = counts.copy()
        unchecked_period_rows.append({
            "year": "2025-2026",
            "grade": 9,
            "group": section["group"],
            "counts": counts,
            "total": total,
            "period": f'2025-2026 {section["group"]}, блок {section["block"]}',
            "periodType": "block",
        })


def average_period_distribution(period_rows, grade_level):
    selected = [
        row for row in period_rows
        if grade_level == 0 or row["grade"] == grade_level
    ]
    return {
        "grade": grade_level,
        "shares": {
            mark: round(mean(row["counts"][mark] / row["total"] * 100 for row in selected), 3)
            if selected else 0
            for mark in ("2", "3", "4", "5")
        },
        "periods": len(selected),
        "years": sum(row["periodType"] == "year" for row in selected),
        "blocks": sum(row["periodType"] == "block" for row in selected),
        "inferredPeriods": sum(bool(row.get("inferred")) for row in selected),
        "totalGrades": sum(row["total"] for row in selected),
    }


unchecked_parallel_distributions = [
    average_period_distribution(unchecked_period_rows, grade_level)
    for grade_level in range(0, 12)
    if grade_level == 0 or 7 <= grade_level <= 11
]

# Class-years with recorded homework checks. For 9Б and 9Д in 2025–2026,
# remove the assessment grades from the one block where homework was not
# checked, so the checked and unchecked bars describe disjoint periods.
checked_period_rows = []
for row in con.execute(
    """SELECT DISTINCT g.school_year,g.grade_level,g.label
       FROM homework_coverage h JOIN teaching_groups g USING(group_id)
       WHERE h.status='recorded_check'
       ORDER BY g.school_year,g.grade_level,g.label"""
):
    if "спецфиз" in row["label"].lower():
        continue
    distribution_row = archive_distribution_lookup.get(
        (row["school_year"], row["label"], row["grade_level"])
    )
    if not distribution_row or not distribution_row["total"]:
        continue
    counts = distribution_row["counts"].copy()
    excluded_block = unchecked_block_counts.get((row["school_year"], row["label"]))
    if excluded_block:
        counts = {
            mark: max(0, counts[mark] - excluded_block[mark])
            for mark in ("2", "3", "4", "5")
        }
    total = sum(counts.values())
    if total:
        checked_period_rows.append({
            "year": row["school_year"],
            "grade": row["grade_level"],
            "group": row["label"],
            "counts": counts,
            "total": total,
            "period": f'{row["school_year"]} {row["label"]}',
            "periodType": "year",
        })

checked_parallel_distributions = [
    average_period_distribution(checked_period_rows, grade_level)
    for grade_level in range(0, 12)
    if grade_level == 0 or 7 <= grade_level <= 11
]

# Homework and independent-grade distributions before and after the selected
# beginning of the AI era. Homework uses the block-summary homework grade only;
# inline homework marks are excluded to avoid counting the same block twice.
ai_cutoff_year = "2025-2026"
group_info_lookup = {
    (group["school_year"], group["label"]): group
    for group in cohort_groups
}
ai_homework_counts = defaultdict(lambda: {str(mark): 0 for mark in range(2, 6)})
for row in con.execute(
    """SELECT school_year,group_label,grade_value
       FROM v_homework
       WHERE event_kind='homework_grade'
         AND check_status='recorded_check'
         AND grade_value IN (2,3,4,5)"""
):
    ai_homework_counts[(row["school_year"], row["group_label"])][
        grade_bucket(row["grade_value"])
    ] += 1

# Old checked journals sometimes contain item-level completion marks but no
# final homework grade. Reconstruct one annual grade per student only when the
# student has at least one recorded homework item. Missing item cells count as
# incomplete; students absent from the homework sheet are not assigned a grade.
checked_group_keys = {
    (row["school_year"], row["label"])
    for row in con.execute(
        """SELECT DISTINCT g.school_year,g.label
           FROM homework_coverage h JOIN teaching_groups g USING(group_id)
           WHERE h.status='recorded_check'"""
    )
}
homework_item_event_counts = {
    (row["school_year"], row["label"]): row["n"]
    for row in con.execute(
        """SELECT g.school_year,g.label,COUNT(*) AS n
           FROM assessment_events e
           JOIN teaching_groups g USING(group_id)
           JOIN source_sheets ss USING(sheet_id)
           WHERE e.event_kind='homework_item' AND ss.status='included'
           GROUP BY g.group_id"""
    )
}
homework_item_students = defaultdict(set)
homework_item_completed = defaultdict(int)
for row in con.execute(
    """SELECT student_id,school_year,group_label,homework_completed
       FROM v_homework
       WHERE event_kind='homework_item' AND check_status='recorded_check'"""
):
    group_key = (row["school_year"], row["group_label"])
    homework_item_students[group_key].add(row["student_id"])
    if row["homework_completed"] == 1:
        homework_item_completed[(group_key, row["student_id"])] += 1

inferred_homework_group_keys = set()
for group_key in sorted(checked_group_keys):
    if group_key in ai_homework_counts:
        continue
    event_count = homework_item_event_counts.get(group_key, 0)
    students_with_items = homework_item_students.get(group_key, set())
    if not event_count or not students_with_items:
        continue
    for student_id in students_with_items:
        completion_rate = homework_item_completed[(group_key, student_id)] / event_count
        ai_homework_counts[group_key][homework_grade_from_rate(completion_rate)] += 1
    inferred_homework_group_keys.add(group_key)

homework_grade_period_rows = []
for (school_year, group_label), counts in ai_homework_counts.items():
    group_info = group_info_lookup.get((school_year, group_label))
    if not group_info or not 7 <= group_info["grade_level"] <= 11:
        continue
    total = sum(counts.values())
    if total:
        homework_grade_period_rows.append({
            "year": school_year,
            "grade": group_info["grade_level"],
            "group": group_label,
            "counts": dict(counts),
            "total": total,
            "period": f"{school_year} {group_label}",
            "periodType": "year",
            "inferred": (school_year, group_label) in inferred_homework_group_keys,
        })

# The checked-objective and homework-grade bars must use the same class-years.
# Three old journals contain only one side of the comparison, so retain the
# intersection rather than showing visually comparable bars with different
# source periods.
checked_period_lookup = {
    (row["year"], row["group"], row["grade"]): row
    for row in checked_period_rows
}
homework_grade_period_lookup = {
    (row["year"], row["group"], row["grade"]): row
    for row in homework_grade_period_rows
}
paired_checked_keys = checked_period_lookup.keys() & homework_grade_period_lookup.keys()
checked_period_rows = [
    checked_period_lookup[key] for key in sorted(paired_checked_keys)
]
homework_grade_period_rows = [
    homework_grade_period_lookup[key] for key in sorted(paired_checked_keys)
]
checked_parallel_distributions = [
    average_period_distribution(checked_period_rows, grade_level)
    for grade_level in range(0, 12)
    if grade_level == 0 or 7 <= grade_level <= 11
]
homework_grade_parallel_distributions = [
    average_period_distribution(homework_grade_period_rows, grade_level)
    for grade_level in range(0, 12)
    if grade_level == 0 or 7 <= grade_level <= 11
]

ai_class_year_rows = []
for (school_year, group_label), homework_counts in ai_homework_counts.items():
    group_info = group_info_lookup.get((school_year, group_label))
    if not group_info or not 7 <= group_info["grade_level"] <= 11:
        continue
    objective_row = archive_distribution_lookup.get(
        (school_year, group_label, group_info["grade_level"])
    )
    homework_total = sum(homework_counts.values())
    if not objective_row or not objective_row["total"] or not homework_total:
        continue
    ai_class_year_rows.append({
        "year": school_year,
        "grade": group_info["grade_level"],
        "group": group_label,
        "homeworkCounts": dict(homework_counts),
        "homeworkTotal": homework_total,
        "objectiveCounts": objective_row["counts"].copy(),
        "objectiveTotal": objective_row["total"],
    })


def ai_distribution(rows, counts_key, total_key):
    return {
        "shares": {
            mark: round(mean(row[counts_key][mark] / row[total_key] * 100 for row in rows), 3)
            if rows else 0
            for mark in ("2", "3", "4", "5")
        },
        "totalGrades": sum(row[total_key] for row in rows),
    }


def ai_era(key, label, rows):
    return {
        "key": key,
        "label": label,
        "classYears": len(rows),
        "years": len({row["year"] for row in rows}),
        "homework": ai_distribution(rows, "homeworkCounts", "homeworkTotal"),
        "objective": ai_distribution(rows, "objectiveCounts", "objectiveTotal"),
    }


ai_before_rows = [
    row for row in ai_class_year_rows
    if row["year"] < ai_cutoff_year and row["grade"] in {8, 9}
]
ai_after_rows = [
    row for row in ai_class_year_rows
    if row["year"] >= ai_cutoff_year and row["grade"] in {8, 9}
]
ai_eras = [
    ai_era("before", "До ИИ · 2012–2025", ai_before_rows),
    ai_era("after", "Эпоха ИИ · 2025–2026", ai_after_rows),
]
ai_eras_by_grade = [{
    "grade": 0,
    "label": "8–9 классы",
    "eras": ai_eras,
}]
for grade in (8, 9):
    ai_eras_by_grade.append({
        "grade": grade,
        "label": f"{grade} класс",
        "eras": [
            ai_era(
                "before", "До ИИ · 2012–2025",
                [row for row in ai_before_rows if row["grade"] == grade],
            ),
            ai_era(
                "after", "Эпоха ИИ · 2025–2026",
                [row for row in ai_after_rows if row["grade"] == grade],
            ),
        ],
    })

# Follow the four cohorts that were in grades 8 and 9 in 2025–2026 back to
# their earlier journals. Average within each cohort first, then across the
# four cohorts, so older cohorts with two pre-AI years do not receive more
# weight than cohorts with one pre-AI year.
ai_class_year_lookup = {
    (row["year"], row["group"]): row
    for row in ai_class_year_rows
}
ai_target_paths = [
    [("2024-2025", "7В"), ("2025-2026", "8В")],
    [("2024-2025", "7Д"), ("2025-2026", "8Д")],
    [("2023-2024", "7Б"), ("2024-2025", "8Б"), ("2025-2026", "9Б")],
    [("2023-2024", "7Д"), ("2024-2025", "8Д"), ("2025-2026", "9Д")],
]


def ai_equal_cohort_distribution(cohort_rows, counts_key, total_key):
    valid_cohorts = [rows for rows in cohort_rows if rows]
    return {
        "shares": {
            mark: round(mean(
                mean(row[counts_key][mark] / row[total_key] * 100 for row in rows)
                for rows in valid_cohorts
            ), 3) if valid_cohorts else 0
            for mark in ("2", "3", "4", "5")
        },
        "totalGrades": sum(
            row[total_key] for rows in valid_cohorts for row in rows
        ),
    }


def ai_cohort_era(key, label, cohort_rows):
    flat_rows = [row for rows in cohort_rows for row in rows]
    return {
        "key": key,
        "label": label,
        "cohorts": sum(bool(rows) for rows in cohort_rows),
        "years": len({row["year"] for row in flat_rows}),
        "homework": ai_equal_cohort_distribution(
            cohort_rows, "homeworkCounts", "homeworkTotal"
        ),
        "objective": ai_equal_cohort_distribution(
            cohort_rows, "objectiveCounts", "objectiveTotal"
        ),
    }


ai_target_before = [
    [ai_class_year_lookup[item] for item in path if item[0] < ai_cutoff_year]
    for path in ai_target_paths
]
ai_target_after = [
    [ai_class_year_lookup[item] for item in path if item[0] >= ai_cutoff_year]
    for path in ai_target_paths
]
ai_four_cohort_comparison = [
    ai_cohort_era("before", "До ИИ", ai_target_before),
    ai_cohort_era("after", "Эпоха ИИ · 2025–2026", ai_target_after),
]

# The same four cohorts, averaged within their 2025–2026 parallel. Each
# parallel therefore has two equally weighted cohorts rather than separate
# class-letter cards.
ai_parallel_comparisons = []
for grade, start, end in ((8, 0, 2), (9, 2, 4)):
    ai_parallel_comparisons.append({
        "grade": grade,
        "label": f"{grade}-я параллель",
        "comparison": [
            ai_cohort_era("before", "До ИИ", ai_target_before[start:end]),
            ai_cohort_era(
                "after", "Эпоха ИИ · 2025–2026", ai_target_after[start:end]
            ),
        ],
    })

# Archive-wide relationship between homework completion and independent
# results. One point is one student in one class-year. Years without recorded
# homework checking remain absent rather than being treated as zero completion.
archive_homework = defaultdict(list)
for row in con.execute(
    """SELECT student_id,school_year,group_label,numeric_value
       FROM v_homework
       WHERE event_kind='homework_ratio' AND check_status='recorded_check'
         AND numeric_value IS NOT NULL"""
):
    key = (row["student_id"], row["school_year"], row["group_label"])
    value = row["numeric_value"]
    # The oldest workbook stores percentages on a 0–100 scale; later files
    # store proportions on a 0–1 scale. Values slightly above 1 are bonuses.
    if value > 2:
        value /= 100
    archive_homework[key].append(value)

# Annual homework-completion histograms for the popup opened from the
# homework-grade bar. Use the same paired class-years as the two comparable
# bars. When a journal has no ready ratio, derive it from checked item marks.
paired_group_grades = {
    (year, group): grade
    for year, group, grade in paired_checked_keys
}
homework_percentage_by_grade = defaultdict(list)
homework_percentage_periods = defaultdict(set)
homework_percentage_fallbacks = defaultdict(int)
homework_percentage_student_keys = set()
for (student_id, school_year, group_label), values in archive_homework.items():
    grade_level = paired_group_grades.get((school_year, group_label))
    if grade_level is None or not values:
        continue
    completion_rate = max(0, mean(values))
    homework_percentage_by_grade[grade_level].append(completion_rate)
    homework_percentage_periods[grade_level].add((school_year, group_label))
    homework_percentage_student_keys.add((student_id, school_year, group_label))

for (school_year, group_label), grade_level in paired_group_grades.items():
    group_key = (school_year, group_label)
    event_count = homework_item_event_counts.get(group_key, 0)
    if not event_count:
        continue
    for student_id in homework_item_students.get(group_key, set()):
        student_key = (student_id, school_year, group_label)
        if student_key in homework_percentage_student_keys:
            continue
        completion_rate = homework_item_completed[(group_key, student_id)] / event_count
        homework_percentage_by_grade[grade_level].append(completion_rate)
        homework_percentage_periods[grade_level].add(group_key)
        homework_percentage_fallbacks[grade_level] += 1


def homework_percentage_histogram(grade_level, values, periods, fallbacks):
    limits = [0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.85, 0.90, 1.00, math.inf]
    labels = ["0–9", "10–19", "20–29", "30–39", "40–49", "50–59", "60–69", "70–79", "80–84", "85–89", "90–99", "100+"]
    marks = ["2", "2", "2", "2", "2", "3", "3", "4", "4", "5", "5", "5"]
    counts = [0] * len(limits)
    for value in values:
        index = next(i for i, upper in enumerate(limits) if value < upper)
        counts[index] += 1
    total = len(values)
    return {
        "grade": grade_level,
        "studentYears": total,
        "periods": len(periods),
        "fallbackStudentYears": fallbacks,
        "bins": [
            {
                "label": label,
                "mark": mark,
                "count": count,
                "share": round(count / total * 100, 3) if total else 0,
            }
            for label, mark, count in zip(labels, marks, counts)
        ],
    }


all_homework_percentage_values = [
    value for grade_level in range(7, 12)
    for value in homework_percentage_by_grade[grade_level]
]
all_homework_percentage_periods = set().union(*(
    homework_percentage_periods[grade_level] for grade_level in range(7, 12)
))
homework_percentage_distributions = [
    homework_percentage_histogram(
        0,
        all_homework_percentage_values,
        all_homework_percentage_periods,
        sum(homework_percentage_fallbacks[grade_level] for grade_level in range(7, 12)),
    )
]
homework_percentage_distributions.extend(
    homework_percentage_histogram(
        grade_level,
        homework_percentage_by_grade[grade_level],
        homework_percentage_periods[grade_level],
        homework_percentage_fallbacks[grade_level],
    )
    for grade_level in range(7, 12)
)

archive_outcomes = defaultdict(list)
for row in con.execute(
    """SELECT en.student_id,g.school_year,g.grade_level,g.label AS group_label,
              e.event_kind,e.event_date,e.date_valid_for_year,o.grade_value
       FROM observations o
       JOIN assessment_events e USING(event_id)
       JOIN enrollments en USING(enrollment_id)
       JOIN teaching_groups g ON g.group_id=e.group_id
       JOIN source_sheets ss USING(sheet_id)
       WHERE ss.status='included' AND o.grade_value IN (2,3,4,5)
         AND g.grade_level BETWEEN 7 AND 11"""
):
    kind = row["event_kind"]
    comparable = kind in {"test_grade_inferred", "quiz_grade", "credit_grade", "exam_grade"}
    comparable = comparable or (
        kind == "mark_unspecified" and row["event_date"] and row["date_valid_for_year"]
    )
    if comparable:
        key = (row["student_id"], row["school_year"], row["group_label"], row["grade_level"])
        archive_outcomes[key].append(row["grade_value"])

archive_points_by_grade = defaultdict(list)
archive_students_by_grade = defaultdict(set)
for (student_id, year, group), homework_values in archive_homework.items():
    if len(homework_values) < 2:
        continue
    grade_level = next(
        (group_info["grade_level"] for group_info in cohort_groups
         if group_info["school_year"] == year and group_info["label"] == group),
        None,
    )
    if grade_level is None:
        continue
    grade_values = archive_outcomes.get((student_id, year, group, grade_level), [])
    if len(grade_values) < 3:
        continue
    archive_students_by_grade[grade_level].add(student_id)
    archive_points_by_grade[grade_level].append({
        "x": round(mean(homework_values) * 100, 1),
        "y": round(mean(grade_values), 2),
        "year": year,
        "grade": grade_level,
        "group": group,
        "homeworkCount": len(homework_values),
        "gradeCount": len(grade_values),
    })

available_student_years_by_grade = {
    grade_level: len({
        (student_id, group["school_year"])
        for group in cohort_groups
        if group["grade_level"] == grade_level
        for student_id in rosters[group["group_id"]]
    })
    for grade_level in range(7, 12)
}
all_available_student_years = len({
    (student_id, group["school_year"])
    for group in cohort_groups
    if 7 <= group["grade_level"] <= 11
    for student_id in rosters[group["group_id"]]
})

archive_correlation = []
all_archive_points = []
all_archive_students = set()
for grade_level in range(7, 12):
    points = archive_points_by_grade[grade_level]
    all_archive_points.extend(points)
    all_archive_students.update(archive_students_by_grade[grade_level])
    r = pearson([(point["x"], point["y"]) for point in points])
    archive_correlation.append({
        "grade": grade_level,
        "r": round(r, 3) if r is not None else None,
        "n": len(points),
        "students": len(archive_students_by_grade[grade_level]),
        "totalStudentYears": available_student_years_by_grade[grade_level],
        "years": len({point["year"] for point in points}),
        "points": points,
    })
all_r = pearson([(point["x"], point["y"]) for point in all_archive_points])
archive_correlation.insert(0, {
    "grade": 0,
    "r": round(all_r, 3) if all_r is not None else None,
    "n": len(all_archive_points),
    "students": len(all_archive_students),
    "totalStudentYears": all_available_student_years,
    "years": len({point["year"] for point in all_archive_points}),
    "points": all_archive_points,
})

# The earlier pause in checking homework covered every archived group in
# 2015–2016 through 2017–2018. Older journals rarely label individual tests,
# so use only dated, integer marks of unspecified type as the broad outcome.
# A separately labelled exam mark is a narrower sensitivity check.
historical_students = defaultdict(lambda: defaultdict(list))
historical_ninth = defaultdict(list)
for row in con.execute(
    """SELECT en.student_id,g.school_year,g.grade_level,g.label AS group_label,
              h.status,e.event_kind,e.event_date,e.date_valid_for_year,
              o.grade_value
       FROM observations o
       JOIN assessment_events e USING(event_id)
       JOIN enrollments en USING(enrollment_id)
       JOIN teaching_groups g USING(group_id)
       JOIN homework_coverage h USING(group_id)
       JOIN source_sheets ss USING(sheet_id)
       WHERE g.school_year BETWEEN '2013-2014' AND '2017-2018'
         AND ss.status='included' AND o.grade_value IN (2,3,4,5)"""
):
    kind = row["event_kind"]
    if kind == "mark_unspecified" and row["event_date"] and row["date_valid_for_year"]:
        kind = "dated_marks"
    elif kind != "exam_grade":
        continue
    key = (row["student_id"], row["school_year"], row["grade_level"], row["status"])
    historical_students[key][kind].append(row["grade_value"])
    if kind == "dated_marks" and row["grade_level"] == 9 and row["school_year"] >= "2014-2015":
        historical_ninth[(row["school_year"], row["status"])].append(row["grade_value"])

historical_transitions = []
historical_exam_switch = None
for start_year in range(2013, 2017):
    from_year = f"{start_year}-{start_year+1}"
    to_year = f"{start_year+1}-{start_year+2}"
    for kind in ("dated_marks", "exam_grade"):
        pairs = []
        for (student_id, year, grade, status), kinds in historical_students.items():
            if year != from_year or kind not in kinds:
                continue
            next_status = "recorded_check" if start_year == 2013 else "no_recorded_check"
            after = historical_students.get((student_id, to_year, grade+1, next_status), {}).get(kind, [])
            before = kinds[kind]
            required = 5 if kind == "dated_marks" else 1
            if len(before) >= required and len(after) >= required:
                pairs.append((statistics.mean(before), statistics.mean(after)))
        if not pairs:
            continue
        item = {
            "from": from_year, "to": to_year,
            "status": "checked" if start_year == 2013 else ("stopped" if start_year == 2014 else "unchecked"),
            "n": len(pairs),
            "before": round(mean(p[0] for p in pairs), 3),
            "after": round(mean(p[1] for p in pairs), 3),
            "delta": round(mean(p[1]-p[0] for p in pairs), 3),
            "worseHalf": sum(p[1]-p[0] <= -0.5 for p in pairs),
        }
        if kind == "dated_marks":
            historical_transitions.append(item)
        elif start_year == 2014:
            historical_exam_switch = item

historical_ninth_rows = []
for (year, status), values in sorted(historical_ninth.items()):
    counts = {str(mark): values.count(mark) for mark in range(2, 6)}
    historical_ninth_rows.append({
        "year": year, "status": status, "counts": counts,
        "total": len(values), "mean": round(mean(values), 3),
    })

historical_coverage = []
for row in con.execute(
    """SELECT g.school_year,h.status,COUNT(*) AS n
       FROM homework_coverage h JOIN teaching_groups g USING(group_id)
       WHERE g.school_year BETWEEN '2015-2016' AND '2017-2018'
       GROUP BY g.school_year,h.status ORDER BY g.school_year"""
):
    historical_coverage.append(dict(row))

data = {
    "crossoverExperiment": build_experiment(con),
    "generated": date.today().isoformat(),
    "summary": {
        "years": years,
        "groups": unique_cohort_count,
        "students": students,
        "observations": observations,
        "independentGrades": independent_grade_count,
        "linkedStudents": linked,
        "threeYearStudents": 52,
    },
    "series": series,
    "archiveCorrelation": archive_correlation,
    "distributions": {
        "byGrade": distribution_by_grade,
        "krTimeline9": timeline_kr9,
        "archiveByGroup": archive_distribution_rows,
        "archiveAverage": archive_average_distribution,
        "archiveByParallel": archive_parallel_distributions,
        "checkedByParallel": checked_parallel_distributions,
        "homeworkGradesByParallel": homework_grade_parallel_distributions,
        "homeworkPercentByParallel": homework_percentage_distributions,
        "uncheckedByParallel": unchecked_parallel_distributions,
    },
    "aiImpact": {
        "cutoffYear": ai_cutoff_year,
        "eras": ai_eras,
        "erasByGrade": ai_eras_by_grade,
        "fourCohortComparison": ai_four_cohort_comparison,
        "parallelComparisons": ai_parallel_comparisons,
    },
    "historical": {
        "coverage": historical_coverage,
        "transitions": historical_transitions,
        "examSwitch": historical_exam_switch,
        "ninthGradeDistribution": historical_ninth_rows,
    },
    "longitudinal": {
        "n": 54,
        "homeworkDelta": -10.4,
        "krDelta": -0.25,
        "source": "reviewed 7–9 report",
        "generatedCheck": {
            "n": len(paired),
            "homeworkDelta": round(mean(p["hw"] for p in paired), 1),
            "krDelta": round(mean(p["kr"] for p in paired), 2),
        },
    },
    # Values reproduced from the reviewed 7–9 report. They are kept separately
    # from the generated scatter data so the origin is transparent in the UI.
    "reviewedCorrelations": {
        "kr": [0.34, 0.42, 0.53],
        "sr": [0.38, 0.52, 0.61],
        "credit": [0.31, 0.47, 0.42],
    },
    "intervention": {
        "blocks": [3, 4, 5, 6],
        "classB": [4.40, 4.10, 3.77, 3.42],
        "classD": [4.13, 3.34, 3.64, 2.94],
        "unchecked": {"4": "9Д", "5": "9Б"},
        "risk": {
            "unchecked": {"count": 14, "total": 48},
            "checked": {"count": 4, "total": 48},
        },
    },
    "notes": {
        "correlation": "Корреляция описывает совместное изменение и не доказывает причинное влияние ДЗ.",
        "ai": "В журналах нет данных о фактическом использовании ИИ конкретными учениками.",
        "privacy": "В браузер передаются только обезличенные точки и агрегаты.",
    },
}

OUT.write_text(
    "window.DASHBOARD_DATA = " + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";\n",
    encoding="utf-8",
)
print(json.dumps({"output": str(OUT), "series": len(series), "paired": len(paired)}, ensure_ascii=False))
