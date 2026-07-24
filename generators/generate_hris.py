"""PeopleCore (HRIS) generator.

Consumes the ground truth and renders PeopleCore's imperfect view of
it as data/employees.csv: one row per employment record (stint), with
the planted distortions applied on the way out.

Distortions applied here:
- P4: rehires become two rows with two unrelated employee IDs
- P7: work emails collide and get suffixed (sarah.lee2@)
- P8: department names drift ("Retail Ops", "retail ops")
- Casing inconsistency in employment_type
- Occasional blank personal_email and salary_band
"""

import csv
import random
from datetime import datetime, timedelta
from pathlib import Path

from ground_truth import (
    DEPARTMENTS,
    SEED,
    SIM_TODAY,
    build_all_people,
    build_special_people,
)

# Output lands in the project's data/ folder regardless of where the
# script is run from. Path(__file__) is this file's own location.
OUTPUT_PATH = Path(__file__).resolve().parent.parent / "data" / "employees.csv"

# P8: how PeopleCore renders each department name. Weighted so the
# clean spelling dominates but drift shows up regularly. Departments
# not listed here always export cleanly.
DEPARTMENT_DRIFT = {
    "Retail Operations": [
        ("Retail Operations", 70),
        ("Retail Ops", 20),
        ("retail ops", 10),
    ],
    "People & Culture": [
        ("People & Culture", 75),
        ("People and Culture", 25),
    ],
}

CSV_COLUMNS = [
    "employee_id",
    "first_name",
    "last_name",
    "work_email",
    "personal_email",
    "department",
    "job_title",
    "employment_type",
    "salary_band",
    "hire_date",
    "termination_date",
    "status",
    "last_modified",
]


def drifted_department(canonical: str, rng: random.Random) -> str:
    """Return the department name as PeopleCore would render it,
    sometimes drifted (P8)."""
    variants = DEPARTMENT_DRIFT.get(canonical)
    if variants is None:
        return canonical
    names = [v[0] for v in variants]
    weights = [v[1] for v in variants]
    return rng.choices(names, weights=weights, k=1)[0]


def assign_employee_ids(people) -> dict[tuple[int, int], str]:
    """Assign an employee_id to every stint, in hire date order, the
    way a real HRIS would: earlier hires got lower numbers. Returns a
    mapping of (person_num, stint_index) -> employee_id.

    Crucially, each STINT gets its own ID. This is where the rehire
    fracture (P4) happens: Maria's two stints become two employees as
    far as PeopleCore is concerned."""
    rng = random.Random(SEED + 1)
    stint_keys = []
    for person in people:
        for i, stint in enumerate(person.stints):
            stint_keys.append((stint.start_date, person.person_num, i))
    stint_keys.sort()

    ids = {}
    next_num = 1000
    for start_date, person_num, stint_index in stint_keys:
        # Real ID sequences have gaps (deleted records, test entries),
        # so we skip ahead by a small random amount each time.
        next_num += rng.randint(1, 4)
        ids[(person_num, stint_index)] = f"E-{next_num:05d}"
    return ids


def assign_work_emails(people, ids) -> dict[tuple[int, int], str]:
    """Assign work emails in the same hire order the IDs used. The
    pattern is first.last@northline.ca; when that address is already
    taken, a counter is appended (P7: sarah.lee2@). Uniqueness is
    enforced against every address ever issued, so a rehire gets a
    fresh suffixed address rather than their old one back."""
    ordered = sorted(ids.keys(), key=lambda k: ids[k])
    person_by_num = {p.person_num: p for p in people}

    taken = set()
    emails = {}
    for person_num, stint_index in ordered:
        person = person_by_num[person_num]
        base = f"{person.first_name.lower()}.{person.last_name.lower()}"
        candidate = f"{base}@northline.ca"
        counter = 2
        while candidate in taken:
            candidate = f"{base}{counter}@northline.ca"
            counter += 1
        taken.add(candidate)
        emails[(person_num, stint_index)] = candidate
    return emails


def salary_band_for(department: str, job_title: str, rng: random.Random) -> str:
    """Derive a salary band from the title's rung on its ladder:
    bottom rung is B1, next is B2, and so on. About 8% of records
    have a blank band (realistic HR data entry gaps)."""
    if rng.random() < 0.08:
        return ""
    ladder = DEPARTMENTS.get(department, [])
    if job_title in ladder:
        return f"B{ladder.index(job_title) + 1}"
    return "B1"


def last_modified_for(stint, rng: random.Random) -> str:
    """A plausible timestamp for when HR last touched this record:
    shortly after the most recent event on it (latest assignment or
    the termination)."""
    latest = stint.assignments[-1].effective_date
    if stint.end_date is not None and stint.end_date > latest:
        latest = stint.end_date
    touched = datetime(latest.year, latest.month, latest.day) + timedelta(
        days=rng.randint(0, 3), hours=rng.randint(8, 18), minutes=rng.randint(0, 59)
    )
    return touched.isoformat()


def build_rows(people, ids, work_emails, special_nums, rng: random.Random) -> list[dict]:
    """Build one CSV row per stint. This is the core of the generator."""
    
    rows = []
    for person in people:
        for stint_index, stint in enumerate(person.stints):
            # The current department and title: the stint's last
            # assignment. PeopleCore only shows the present (P3).
            current = stint.assignments[-1]

            # The personal email that was current when this stint
            # began; sometimes HR never collected one at all.
            email_index = min(stint_index, len(person.personal_emails) - 1)
            personal_email = person.personal_emails[email_index]
            if person.person_num not in special_nums and rng.random() < 0.15:
                personal_email = ""

            # Messy casing on employment type.
            employment_type = rng.choice([
                stint.employment_type,
                stint.employment_type.lower(),
                stint.employment_type.capitalize(),
            ])

            if stint.end_date is not None:
                status = "Terminated"
                termination_date = stint.end_date.isoformat()
            else:
                status = "On Leave" if rng.random() < 0.04 else "Active"
                termination_date = ""

            rows.append({
                "employee_id": ids[(person.person_num, stint_index)],
                "first_name": person.first_name,
                "last_name": person.last_name,
                "work_email": work_emails[(person.person_num, stint_index)],
                "personal_email": personal_email,
                "department": drifted_department(current.department, rng),
                "job_title": current.job_title,
                "employment_type": employment_type,
                "salary_band": salary_band_for(current.department, current.job_title, rng),
                "hire_date": stint.start_date.isoformat(),
                "termination_date": termination_date,
                "status": status,
                "last_modified": last_modified_for(stint, rng),
            })
    return rows


def write_csv(rows: list[dict]) -> None:
    """Write the rows to data/employees.csv."""
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    rng = random.Random(SEED + 2)
    people = build_all_people()
    ids = assign_employee_ids(people)
    work_emails = assign_work_emails(people, ids)
    special_nums = {p.person_num for p in build_special_people()}
    rows = build_rows(people, ids, work_emails, special_nums, rng)
    write_csv(rows)

    print(f"Wrote {len(rows)} employment records to {OUTPUT_PATH}")

    # Spot checks on the planted problems.
    by_name = {}
    for row in rows:
        key = (row["first_name"], row["last_name"])
        by_name.setdefault(key, []).append(row["employee_id"])

    print("\nP4 check, rehires should each show TWO unrelated IDs:")
    for name in [("Maria", "Santos"), ("Devon", "Clarke")]:
        print(f"  {name[0]} {name[1]}: {by_name.get(name, 'MISSING')}")

    print("\nP7 check, the two Sarah Lees' work emails should differ:")
    sarah_emails = [r["work_email"] for r in rows if r["last_name"] == "Lee" and r["first_name"] == "Sarah"]
    print(f"  {sarah_emails}")

    print("\nP10 check, Benjamin Hayes should NOT appear:")
    benjamin = [r for r in rows if r["last_name"] == "Hayes" and r["first_name"] == "Benjamin"]
    print(f"  rows found: {len(benjamin)} (should be 0)")

    print("\nP8 check, department drift variants present:")
    dept_values = sorted({r["department"] for r in rows})
    print(f"  {dept_values}")