"""Anonymous, reproducible crossover contrasts for 9Б/9Д, 2025–2026.

Use first test attempts with an actual numeric points entry. Cached grade
formulas can return 2 for an absent pupil: those are not test results.
Two marks for one test are averaged within pupil, never counted as pupils.
"""
from collections import defaultdict
from statistics import mean

BLOCKS = {
    2: {"points": 21, "kr": [22, 23], "quiz": [14, 16, 18, 19], "date": "21.10.2025"},
    3: {"points": 30, "kr": [31, 32], "quiz": [28], "date": "01.11.2025"},
    4: {"points": 57, "kr": [58, 59], "quiz": [48, 49, 51, 53, 55], "date": "16.12.2025"},
    5: {"points": 68, "kr": [69, 70], "quiz": [64, 66], "date": "20.01.2026"},
    6: {"points": 77, "kr": [78, 79], "quiz": [75], "date": "14.02.2026"},
}
GROUPS = ("9Б", "9Д")


def build_experiment(con):
    observations = defaultdict(dict)
    for row in con.execute("""SELECT en.student_id,g.label,e.source_column,
                 o.numeric_value,o.grade_value
          FROM observations o JOIN assessment_events e USING(event_id)
          JOIN enrollments en USING(enrollment_id)
          JOIN teaching_groups g ON g.group_id=e.group_id
          JOIN source_sheets ss USING(sheet_id)
          WHERE g.school_year='2025-2026' AND g.label IN ('9Б','9Д')
            AND ss.status='included' AND ss.sheet_name='Уроки'"""):
        observations[(row["label"], row["student_id"])][row["source_column"]] = (
            row["numeric_value"], row["grade_value"]
        )

    scores = {metric: defaultdict(dict) for metric in ("kr", "low", "quiz")}
    for (group, student), cols in observations.items():
        for block, spec in BLOCKS.items():
            points = cols.get(spec["points"], (None, None))[0]
            marks = [cols.get(col, (None, None))[1] for col in spec["kr"]]
            if points is not None and points >= 0 and all(v in (2, 3, 4, 5) for v in marks):
                scores["kr"][(group, student)][block] = mean(marks)
                scores["low"][(group, student)][block] = mean(v == 2 for v in marks) * 100
            quizzes = [cols.get(col, (None, None))[1] for col in spec["quiz"]]
            quizzes = [v for v in quizzes if v in (2, 3, 4, 5)]
            if quizzes:
                scores["quiz"][(group, student)][block] = mean(quizzes)

    results = []
    for metric, label, unit in (("kr", "Средняя оценка КР", "балла"),
                                ("low", "Доля двоек на КР", "п.п."),
                                ("quiz", "Летучки", "балла")):
        complete = {key: values for key, values in scores[metric].items()
                    if all(block in values for block in BLOCKS)}
        samples = []
        for sample_id, selected in (("balanced", complete), ("available", scores[metric])):
            by_group = {group: {student: values for (item_group, student), values in selected.items()
                                if item_group == group} for group in GROUPS}
            timeline = []
            for block, spec in BLOCKS.items():
                groups = {}
                for group in GROUPS:
                    values = [v[block] for v in by_group[group].values() if block in v]
                    groups[group] = {"mean": round(mean(values), 6), "n": len(values)}
                timeline.append({"block": block, "date": spec["date"], "groups": groups,
                                 "gap": round(groups["9Б"]["mean"] - groups["9Д"]["mean"], 6),
                                 "unchecked": {4: "9Д", 5: "9Б"}.get(block)})
            lookup = {row["block"]: row for row in timeline}
            baseline = mean(lookup[block]["gap"] for block in (2, 3))
            # Negative effect = lower marks without checks. For "low", positive
            # effect = more failing marks without checks (units are percentage points).
            effects = [
                {"id": "D", "label": "9Д · блок 4", "value": -(lookup[4]["gap"] - baseline)},
                {"id": "B", "label": "9Б · блок 5", "value": lookup[5]["gap"] - baseline},
                {"id": "pooled", "label": "Среднее двух этапов", "value": (lookup[5]["gap"] - lookup[4]["gap"]) / 2},
            ]
            for effect in effects:
                effect["value"] = round(effect["value"], 6)
            samples.append({"id": sample_id, "timeline": timeline,
                            "baselineGap": round(baseline, 6), "effects": effects,
                            "students": {group: len(by_group[group]) for group in GROUPS}})
        results.append({"id": metric, "label": label, "unit": unit, "samples": samples})

    # Individual changes use the same complete-case KR cohort as the main graph.
    # Remove each pupil's own baseline and the other class's contemporaneous
    # mean change. This is a descriptive residual, not an individual causal effect.
    balanced = {key: values for key, values in scores["kr"].items()
                if all(block in values for block in BLOCKS)}
    risk = []
    for group, block, other in (("9Д", 4, "9Б"), ("9Б", 5, "9Д")):
        controls = [v for (g, _), v in balanced.items() if g == other]
        control_change = mean(v[block] - mean(v[b] for b in (2, 3)) for v in controls)
        changes = [v[block] - mean(v[b] for b in (2, 3)) - control_change
                   for (g, _), v in balanced.items() if g == group]
        risk.append({"group": group, "block": block, "n": len(changes),
                     "changes": sorted(round(value, 6) for value in changes),
                     "lower": sum(value <= -0.5 for value in changes),
                     "middle": sum(-0.5 < value < 0.5 for value in changes),
                     "higher": sum(value >= 0.5 for value in changes)})
    return {"year": "2025–2026", "baselineBlocks": [2, 3], "metrics": results, "risk": risk}


if __name__ == "__main__":
    import json
    from pathlib import Path
    from research_scope import connect_study_database
    con = connect_study_database(Path(__file__).resolve().parent.parent / "Оценки_Арабули_2012-2026.sqlite")
    print(json.dumps(build_experiment(con), ensure_ascii=False, indent=2))
