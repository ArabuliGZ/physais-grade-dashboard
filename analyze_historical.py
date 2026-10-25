"""Explore the 2014–2019 homework checking change using anonymous aggregates."""

from collections import Counter, defaultdict
from pathlib import Path
import json
import sqlite3
import statistics

DB = Path(__file__).resolve().parent.parent / "Оценки_Арабули_2012-2026.sqlite"
con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row

rows = con.execute(
    """SELECT en.student_id, g.group_id, g.school_year, g.grade_level,
              g.label AS group_label, h.status, e.event_kind, e.event_date,
              e.date_valid_for_year, e.header_primary, o.grade_value
       FROM observations o
       JOIN assessment_events e USING(event_id)
       JOIN enrollments en USING(enrollment_id)
       JOIN teaching_groups g USING(group_id)
       JOIN homework_coverage h USING(group_id)
       JOIN source_sheets ss USING(sheet_id)
       WHERE ss.status='included' AND o.grade_value IN (2,3,4,5)
         AND g.school_year BETWEEN '2013-2014' AND '2019-2020'"""
).fetchall()

groups = defaultdict(lambda: defaultdict(list))
students = defaultdict(lambda: defaultdict(list))
for row in rows:
    key = (row["school_year"], row["group_label"], row["grade_level"], row["status"])
    kind = row["event_kind"]
    if kind == "mark_unspecified" and row["event_date"] and row["date_valid_for_year"]:
        kind = "dated_marks"
    elif kind == "mark_unspecified":
        continue
    groups[key][kind].append(row["grade_value"])
    students[(row["student_id"], row["school_year"], row["grade_level"], row["status"])][kind].append(row["grade_value"])

summary = []
for (year, group, grade, status), kinds in sorted(groups.items()):
    summary.append({
        "year": year, "group": group, "grade": grade, "status": status,
        "marks": {kind: {"n": len(values), "mean": round(statistics.mean(values), 2)}
                  for kind, values in kinds.items()
                  if kind in ("dated_marks", "exam_grade", "credit_grade", "test_grade_inferred")},
    })

matched = []
for (student_id, year, grade, status), kinds in students.items():
    next_year = f"{int(year[:4])+1}-{int(year[5:])+1}"
    for next_grade in (grade + 1,):
        for next_status in ("recorded_check", "no_recorded_check"):
            other = students.get((student_id, next_year, next_grade, next_status))
            if not other:
                continue
            for kind in ("dated_marks", "exam_grade", "credit_grade"):
                before, after = kinds.get(kind, []), other.get(kind, [])
                if len(before) >= (5 if kind == "dated_marks" else 1) and len(after) >= (5 if kind == "dated_marks" else 1):
                    matched.append({
                        "from": year, "to": next_year,
                        "status": status + "→" + next_status,
                        "grade": grade, "kind": kind,
                        "delta": statistics.mean(after) - statistics.mean(before),
                        "before": statistics.mean(before), "after": statistics.mean(after),
                        "low_before": sum(v <= 3 for v in before)/len(before),
                        "low_after": sum(v <= 3 for v in after)/len(after),
                    })

transitions = []
for key in sorted({(x["from"], x["to"], x["status"], x["grade"], x["kind"]) for x in matched}):
    values = [x for x in matched if (x["from"], x["to"], x["status"], x["grade"], x["kind"]) == key]
    transitions.append({
        "from": key[0], "to": key[1], "status": key[2], "grade": key[3], "kind": key[4],
        "n": len(values),
        "before": round(statistics.mean(x["before"] for x in values), 2),
        "after": round(statistics.mean(x["after"] for x in values), 2),
        "delta": round(statistics.mean(x["delta"] for x in values), 2),
        "share_worse_05": round(sum(x["delta"] <= -0.5 for x in values)/len(values), 2),
        "low_before": round(statistics.mean(x["low_before"] for x in values), 2),
        "low_after": round(statistics.mean(x["low_after"] for x in values), 2),
    })

pooled = []
for key in sorted({(x["from"], x["status"], x["kind"]) for x in matched}):
    values = [x for x in matched if (x["from"], x["status"], x["kind"]) == key]
    pooled.append({"year": key[0], "status": key[1], "kind": key[2], "n": len(values),
                   "before": round(statistics.mean(x["before"] for x in values), 3),
                   "after": round(statistics.mean(x["after"] for x in values), 3),
                   "worse05": sum(x["delta"] <= -0.5 for x in values),
                   "worse_any": sum(x["delta"] < 0 for x in values),
                   "better05": sum(x["delta"] >= 0.5 for x in values)})

cohort = []
for student_id in {key[0] for key in students}:
    pathway = [("2014-2015", 8, "recorded_check"),
               ("2015-2016", 9, "no_recorded_check"),
               ("2016-2017", 10, "no_recorded_check"),
               ("2017-2018", 11, "no_recorded_check")]
    values = [students.get((student_id, *stage), {}).get("dated_marks", []) for stage in pathway]
    if all(len(v) >= 5 for v in values):
        cohort.append([statistics.mean(v) for v in values])
print(json.dumps({"transitions": transitions, "pooled": pooled,
                  "cohort_8_to_11": {"n": len(cohort), "means": [round(statistics.mean(v[i] for v in cohort), 3) for i in range(4)] if cohort else []}}, ensure_ascii=True))
