"""Fictional post-eligibility selection demo; not production SisterTwin code."""
from collections import defaultdict
from dataclasses import asdict, dataclass, replace
import json
from pathlib import Path


@dataclass(frozen=True)
class Candidate:
    target: str
    year: int
    description: str
    reference: str
    part: str | None
    engine: str | None = None
    region: str | None = "North"
    position: str = "Front"
    decision: str = ""


INCLUDE = "Include - selected reference vehicle"
OTHER = "Exclude - another reference vehicle selected"
NO_REGION = "Exclude - Missing Region is NULL"
INCOMPLETE = "Needs review - no reference contains all eligible parts"
NO_PART = "Needs review - missing part number"


def select(rows):
    """Return all rows with decisions; input rows have already passed gap discovery.

    reference/target are fictional combined make-model labels. Production uses
    separate columns and database collation. This sample uses exact strings.
    """
    groups = defaultdict(list)
    for index, row in enumerate(rows):
        groups[row.target, row.year, row.description].append((index, row))
    result = list(rows)
    for group in groups.values():
        eligible = [row for _, row in group if row.region is not None]
        by_reference = defaultdict(list)
        for row in eligible:
            by_reference[row.reference].append(row)
        missing_part = any(not (row.part or "").strip() for row in eligible)
        union = {row.part for row in eligible}
        complete = [name for name, apps in by_reference.items()
                    if {row.part for row in apps} == union]

        def rank(name):
            apps = by_reference[name]
            blank = [not (row.engine or "").strip() for row in apps]
            category = 0 if all(blank) else 1 if not any(blank) else 2
            return category, -len(apps), name

        winner = min(complete, key=rank) if complete and not missing_part else None
        for index, row in group:
            if row.region is None:
                decision = NO_REGION
            elif missing_part:
                decision = NO_PART
            elif winner is None:
                decision = INCOMPLETE
            else:
                decision = INCLUDE if row.reference == winner else OTHER
            result[index] = replace(row, decision=decision)
    return result


def examples():
    rows = []
    for target, lists in {
        "Boreal Brook": {"Aster Atlas": ["DEMO-001", "DEMO-002"],
                         "Cedar Crest": ["DEMO-001", "DEMO-002", "DEMO-003"]},
        "Boreal Bay": {"Aster Atlas": ["DEMO-001", "DEMO-002"],
                       "Cedar Crest": ["DEMO-001", "DEMO-003"]},
    }.items():
        for reference, parts in lists.items():
            rows.extend(Candidate(target, 2022, "Relay", reference, part,
                                  engine="2.0L") for part in parts)
    rows.append(Candidate("Boreal Brook", 2022, "Relay", "Cedar Crest",
                          "DEMO-001", engine="2.0L", position="Rear"))
    rows.append(Candidate("Boreal Brook", 2022, "Relay", "Aster Atlas",
                          "DEMO-004", engine="3.0L", region=None))
    return rows


if __name__ == "__main__":
    report = [asdict(row) for row in select(examples())]
    destination = Path(__file__).with_name("output.json")
    destination.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("FICTIONAL CANDIDATES — no approvals or imports")
    for decision in (INCLUDE, OTHER, NO_REGION, INCOMPLETE, NO_PART):
        print(f"{sum(row['decision'] == decision for row in report):2}  {decision}")
    print(f"Report: {destination.name}")
