"""PeopleCore (HRIS) generator.

Consumes the ground truth and renders PeopleCore's nightly export as
of a given date: data/employees.csv, one row per employment record
that exists by that date.

Usage:
    python generate_hris.py              # export as of the real today
    python generate_hris.py 2026-08-15   # export as of a chosen date

The as-of date is the broadcast dial: ground truth is a finished
script running to the horizon (end of 2027), and each export shows
only the events that have happened by the as-of date. Consecutive
daily runs therefore differ in realistic ways: new hires appear,
terminations land, promotions show up.

Distortions applied here:
- P4: rehires become two rows with two unrelated employee IDs
- P7: work emails collide and get suffixed (sarah.lee2@)
- P8: department names drift ("Retail Ops", "retail ops")
- Casing inconsistency in employment_type
- Occasional blank personal_email and salary_band

Two rules keep the distortions honest:
- Destructive mess (blanked fields) never touches special people, so
  their planted matching signals survive exactly as designed.
- Every random choice is seeded PER RECORD, not per run. A record's
  drifted department, casing, and blanks are identical in every
  export, on every date. Real systems are messy but consistently
  messy: the same stored value exports the same way every night.
"""

import csv
import random
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

from ground_truth import (
    DEPARTMENTS,
    HORIZON,
    SEED,
    build_all_people,
    build_special_people,
)

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


def record_rng(*key_parts) -> random.Random:
    """A random generator seeded by a stable key, so the 'random'
    choices for any given record are identical on every run and
    every export date."""
    return random.Random("|".join(str(p) for p in key_parts))


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
    """Assign an employee_id to every stint in the full script, in
    hire date order, the way a real HRIS would: earlier hires got
    lower numbers. IDs cover ALL stints including future ones, so an
    ID never changes between export dates; future records are simply
    not exported yet.

    Each STINT gets its own ID. This is where the rehire fracture
    (P4) happens: Maria's two stints become two employees as far as
    PeopleCore is concerned."""
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


def build_rows(people, ids, work_emails, special_nums, as_of: date) -> list[dict]:
    """One CSV row per employment record that exists by as_of, showing
    each record's state as of that date."""
    rows = []
    for person in people:
        for stint_index, stint in enumerate(person.stints):
            # Not hired yet as of this export: invisible.
            if stint.start_date > as_of:
                continue

            # Only assignments that have taken effect are visible;
            # the latest of them is the current role (P3: the export
            # only knows the present).
            visible = [a for a in stint.assignments if a.effective_date <= as_of]
            current = visible[-1]

            # A scripted termination that has not happened yet means
            # this person is still active in this export.
            terminated = stint.end_date is not None and stint.end_date <= as_of

            rng = record_rng(SEED, "hris", person.person_num, stint_index)

            # The personal email that was current when this stint
            # began; sometimes HR never collected one. Never blanked
            # for specials: their matching signals must survive.
            email_index = min(stint_index, len(person.personal_emails) - 1)
            personal_email = person.personal_emails[email_index]
            if person.person_num not in special_nums and rng.random() < 0.15:
                personal_email = ""

            employment_type = rng.choice([
                stint.employment_type,
                stint.employment_type.lower(),
                stint.employment_type.capitalize(),
            ])

            on_leave_roll = rng.random() < 0.04
            if terminated:
                status = "Terminated"
                termination_date = stint.end_date.isoformat()
            else:
                status = "On Leave" if on_leave_roll else "Active"
                termination_date = ""

            # last_modified: shortly after the latest visible event.
            latest = current.effective_date
            if terminated and stint.end_date > latest:
                latest = stint.end_date
            touched = datetime(latest.year, latest.month, latest.day) + timedelta(
                days=rng.randint(0, 3),
                hours=rng.randint(8, 18),
                minutes=rng.randint(0, 59),
            )

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
                "last_modified": touched.isoformat(),
            })
    return rows


def parse_as_of() -> date:
    """The export date: an optional command line argument, defaulting
    to the real today, never past the horizon."""
    if len(sys.argv) > 1:
        as_of = date.fromisoformat(sys.argv[1])
    else:
        as_of = date.today()
    return min(as_of, HORIZON)


def write_csv(rows: list[dict]) -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    as_of = parse_as_of()
    people = build_all_people()
    ids = assign_employee_ids(people)
    work_emails = assign_work_emails(people, ids)
    special_nums = {p.person_num for p in build_special_people()}
    rows = build_rows(people, ids, work_emails, special_nums, as_of)
    write_csv(rows)

    print(f"Export as of {as_of}: {len(rows)} employment records -> {OUTPUT_PATH}")

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