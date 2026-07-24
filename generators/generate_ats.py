"""TalentFlow (ATS) generator.

Consumes the ground truth and renders TalentFlow's export as of a
given date: data/candidates.json, one object per candidate with
nested applications, covering only what a system adopted in 2022
could know by that date.

Usage:
    python generate_ats.py              # export as of the real today
    python generate_ats.py 2026-08-15   # export as of a chosen date

Application statuses evolve over time the way a real ATS's would:
an application is invisible before its applied date, in_progress
until its outcome date, and only then shows its final status
(hired with an offer, or rejected/withdrawn).

Distortions applied here:
- P5: Priya Sharma appears as TWO candidate records (dedup failure)
- P6: Rob Chen's record uses his nickname; Emily's uses her maiden name
- P9: phone numbers and email casing exported in inconsistent formats
- P10: Benjamin Hayes has a hired application but never started
- Plus realistic noise: rejected, withdrawn, and in-progress candidates
  who never became employees. These exist only here, not in ground
  truth, because they have no cross-system identity to verify.

Same honesty rules as the HRIS generator: recoverable mess (formats,
casing) can touch anyone; destructive mess never touches specials;
and every random choice is seeded per record, so IDs, names, and
formatting are identical across runs and export dates.
"""

import json
import random
import string
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

from faker import Faker

from ground_truth import (
    DEPARTMENTS,
    HORIZON,
    SEED,
    build_all_people,
)

OUTPUT_PATH = Path(__file__).resolve().parent.parent / "data" / "candidates.json"

# TalentFlow was adopted at the start of 2022. It knows nothing about
# anyone hired before this date.
TALENTFLOW_ADOPTED = date(2022, 1, 1)

# Person numbers of specials this generator treats specially.
PRIYA = 3      # P5: split into two candidate records
BENJAMIN = 8   # P10: hired application, but he never started

NOISE_COUNT = 200


def record_rng(*key_parts) -> random.Random:
    """A random generator seeded by a stable key: identical output
    for the same record on every run and every export date."""
    return random.Random("|".join(str(p) for p in key_parts))


def make_id(prefix: str, key: str) -> str:
    """Stable IDs like cand_8f3k2 / app_x92m1, derived from the
    record's key so they never change between exports."""
    rng = record_rng(SEED, "id", prefix, key)
    alphabet = string.ascii_lowercase + string.digits
    suffix = "".join(rng.choice(alphabet) for _ in range(5))
    return f"{prefix}_{suffix}"


def messy_phone(phone: str, rng: random.Random) -> str:
    """P9: render a clean 416-555-0181 style phone in one of the
    inconsistent formats candidates actually type."""
    area, mid, last = phone.split("-")
    style = rng.randint(0, 3)
    if style == 0:
        return f"{area}-{mid}-{last}"
    if style == 1:
        return f"{area}{mid}{last}"
    if style == 2:
        return f"({area}) {mid}-{last}"
    return f"+1 {area} {mid} {last}"


def messy_email(email: str, rng: random.Random) -> str:
    """P9: sometimes candidates type their email with odd casing.
    Recoverable mess: lowercasing in staging restores it."""
    if rng.random() < 0.25:
        local, domain = email.split("@")
        return f"{local.title()}@{domain}"
    return email


# ----------------------------------------------------------------------
# Application specs: timeless descriptions of each application's full
# story (dates and final outcome). Rendering filters them by as_of.
# ----------------------------------------------------------------------

def hired_app_spec(key: str, stint) -> dict:
    """The spec for an application that led to the given stint:
    applied about six weeks before the start date, offer accepted
    about two weeks before."""
    rng = record_rng(SEED, "hired-app", key)
    start = stint.start_date
    first = stint.assignments[0]
    return {
        "key": key,
        "applied_at": start - timedelta(days=rng.randint(30, 55)),
        "outcome_at": start - timedelta(days=rng.randint(10, 18)),
        "final_status": "hired",
        "job_title": first.job_title,
        "department": first.department,
        "start_date": start,
    }


def noise_app_spec(key: str, applied: date, department: str, job_title: str) -> dict:
    """The spec for an application that went nowhere: resolved to
    rejected or withdrawn a few weeks after it was filed."""
    rng = record_rng(SEED, "noise-app", key)
    return {
        "key": key,
        "applied_at": applied,
        "outcome_at": applied + timedelta(days=rng.randint(14, 60)),
        "final_status": rng.choices(["rejected", "withdrawn"], weights=[75, 25], k=1)[0],
        "job_title": job_title,
        "department": department,
        "start_date": None,
    }


def render_application(spec: dict, as_of: date) -> dict | None:
    """The application as TalentFlow would show it on as_of: absent
    before it was filed, in_progress until its outcome, then final."""
    if spec["applied_at"] > as_of:
        return None
    if spec["outcome_at"] > as_of:
        status = "in_progress"
        offer = None
    else:
        status = spec["final_status"]
        offer = None
        if status == "hired":
            offer = {
                "accepted_at": spec["outcome_at"].isoformat(),
                "start_date": spec["start_date"].isoformat(),
            }
    return {
        "application_id": make_id("app", spec["key"]),
        "job_title": spec["job_title"],
        "department": spec["department"],
        "applied_at": spec["applied_at"].isoformat(),
        "status": status,
        "offer": offer,
    }


def candidate_shell(key: str, first, last, email, phone, first_applied: date) -> dict:
    """The outer candidate object, with the P9 formatting mess
    applied to the contact fields (stable per candidate)."""
    rng = record_rng(SEED, "shell", key)
    created = datetime(
        first_applied.year, first_applied.month, first_applied.day,
        rng.randint(8, 20), rng.randint(0, 59), rng.randint(0, 59),
    )
    return {
        "candidate_id": make_id("cand", key),
        "first_name": first,
        "last_name": last,
        "personal_email": messy_email(email, rng),
        "phone": messy_phone(phone, rng),
        "created_at": created.isoformat() + "Z",
        "applications": [],
    }


# ----------------------------------------------------------------------
# Candidate specs from ground truth people
# ----------------------------------------------------------------------

def build_candidate_specs(people) -> list[dict]:
    """Timeless candidate specs: shell info plus application specs.
    Rendering per as_of happens later."""
    specs = []

    for person in people:
        # The name TalentFlow holds: the one the candidate typed.
        # Nicknames and maiden names live here (P6).
        first = person.name_variant or person.first_name
        last = person.former_last_name or person.last_name

        # --- Special case: Priya, the dedup failure (P5) -----------
        # Different emails on her two records; same phone, the clue
        # that they are one person.
        if person.person_num == PRIYA:
            old_applied = date(2022, 5, 16)
            specs.append({
                "key": f"p{person.person_num}-a",
                "first": first, "last": last,
                "email": person.personal_emails[0],
                "phone": person.phone,
                "first_applied": old_applied,
                "apps": [noise_app_spec(
                    f"p{person.person_num}-a-1", old_applied,
                    "Marketing", "Marketing Coordinator",
                )],
            })
            stint = person.stints[0]
            hired = hired_app_spec(f"p{person.person_num}-b-1", stint)
            specs.append({
                "key": f"p{person.person_num}-b",
                "first": first, "last": last,
                "email": person.personal_emails[-1],
                "phone": person.phone,
                "first_applied": hired["applied_at"],
                "apps": [hired],
            })
            continue

        # --- Special case: Benjamin, the no show (P10) -------------
        # A fully hired application with a start date in the past,
        # and no stints in ground truth: he never actually started.
        if person.person_num == BENJAMIN:
            fake_start = date(2025, 3, 3)
            key = f"p{person.person_num}"
            rng = record_rng(SEED, "benjamin", key)
            applied = fake_start - timedelta(days=45)
            specs.append({
                "key": key,
                "first": first, "last": last,
                "email": person.personal_emails[0],
                "phone": person.phone,
                "first_applied": applied,
                "apps": [{
                    "key": f"{key}-1",
                    "applied_at": applied,
                    "outcome_at": fake_start - timedelta(days=14),
                    "final_status": "hired",
                    "job_title": "Customer Care Representative",
                    "department": "Customer Experience",
                    "start_date": fake_start,
                }],
            })
            continue

        # --- The general case -------------------------------------
        # One candidate record per person, with a hired application
        # for each stint that began in the TalentFlow era.
        ats_stints = [
            (i, s) for i, s in enumerate(person.stints)
            if s.start_date >= TALENTFLOW_ADOPTED
        ]
        if not ats_stints:
            continue

        first_index, first_stint = ats_stints[0]
        email_index = min(first_index, len(person.personal_emails) - 1)
        email = person.personal_emails[email_index]

        apps = [
            hired_app_spec(f"p{person.person_num}-{i}", s)
            for i, s in ats_stints
        ]

        # Realism: some hired people also applied unsuccessfully
        # earlier (deterministic per person, never specials since
        # extra applications could muddy their planted signals).
        rng = record_rng(SEED, "extra-app", person.person_num)
        if person.person_num > 8 and rng.random() < 0.15:
            earlier = apps[0]["applied_at"] - timedelta(days=rng.randint(200, 700))
            if earlier >= TALENTFLOW_ADOPTED:
                dept = rng.choice(list(DEPARTMENTS.keys()))
                apps.insert(0, noise_app_spec(
                    f"p{person.person_num}-x", earlier,
                    dept, DEPARTMENTS[dept][0],
                ))

        specs.append({
            "key": f"p{person.person_num}",
            "first": first, "last": last,
            "email": email,
            "phone": person.phone,
            "first_applied": apps[0]["applied_at"],
            "apps": apps,
        })

    return specs


def build_noise_specs(reserved_names) -> list[dict]:
    """Candidates who never became employees: the rejected, the
    withdrawn, and the in-progress. Most of any real ATS. Generated
    here rather than in ground truth because they have no
    cross-system identity to verify."""
    Faker.seed(SEED + 3)
    fake = Faker("en_CA")
    rng = random.Random(SEED + 3)
    used = set(reserved_names)
    specs = []

    span_days = (HORIZON - TALENTFLOW_ADOPTED).days

    for i in range(NOISE_COUNT):
        while True:
            first = fake.first_name()
            last = fake.last_name()
            if (first, last) not in used:
                used.add((first, last))
                break

        applied = TALENTFLOW_ADOPTED + timedelta(days=rng.randint(0, span_days - 30))
        email = f"{first.lower()}.{last.lower()}{rng.randint(1, 999)}@{rng.choice(['gmail.com', 'hotmail.com', 'outlook.com', 'yahoo.ca'])}"
        phone = f"{rng.choice(['416', '647', '905', '289'])}-555-{rng.randint(0, 9999):04d}"

        dept = rng.choice(list(DEPARTMENTS.keys()))
        apps = [noise_app_spec(f"n{i}-1", applied, dept, rng.choice(DEPARTMENTS[dept][:2]))]

        # Some persistent candidates applied twice.
        if rng.random() < 0.2:
            applied2 = applied + timedelta(days=rng.randint(60, 400))
            if applied2 < HORIZON:
                dept2 = rng.choice(list(DEPARTMENTS.keys()))
                apps.append(noise_app_spec(f"n{i}-2", applied2, dept2, DEPARTMENTS[dept2][0]))

        specs.append({
            "key": f"n{i}",
            "first": first, "last": last,
            "email": email,
            "phone": phone,
            "first_applied": applied,
            "apps": apps,
        })

    return specs


def render_candidates(specs: list[dict], as_of: date) -> list[dict]:
    """Render every candidate visible by as_of, with each application
    in its as-of state."""
    rendered = []
    for spec in specs:
        apps = [render_application(a, as_of) for a in spec["apps"]]
        apps = [a for a in apps if a is not None]
        if not apps:
            continue  # candidate has not applied yet as of this date
        rec = candidate_shell(
            spec["key"], spec["first"], spec["last"],
            spec["email"], spec["phone"], spec["first_applied"],
        )
        rec["applications"] = apps
        rendered.append(rec)
    return rendered


def parse_as_of() -> date:
    if len(sys.argv) > 1:
        as_of = date.fromisoformat(sys.argv[1])
    else:
        as_of = date.today()
    return min(as_of, HORIZON)


if __name__ == "__main__":
    as_of = parse_as_of()
    people = build_all_people()

    specs = build_candidate_specs(people)
    reserved = {(p.first_name, p.last_name) for p in people}
    specs += build_noise_specs(reserved)

    # Stable shuffle so real hires and noise are interleaved like a
    # real export, identically on every run.
    random.Random(SEED + 4).shuffle(specs)

    candidates = render_candidates(specs, as_of)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(candidates, f, indent=2)

    print(f"Export as of {as_of}: {len(candidates)} candidates -> {OUTPUT_PATH}")
    statuses = {}
    for c in candidates:
        for a in c["applications"]:
            statuses[a["status"]] = statuses.get(a["status"], 0) + 1
    print(f"Application statuses: {statuses}")

    def find(last_name, first_name=None):
        return [
            c for c in candidates
            if c["last_name"] == last_name
            and (first_name is None or c["first_name"] == first_name)
        ]

    print("\nP5 check, Priya should be TWO records, different emails, same phone:")
    for c in find("Sharma"):
        print(f"  {c['candidate_id']}: {c['personal_email']} / {c['phone']}")

    print("\nP6 check, Chen's first name should be the nickname:")
    for c in find("Chen"):
        print(f"  {c['first_name']} {c['last_name']}")

    print("\nP6 check, Emily should appear under maiden name Tran:")
    for c in find("Tran"):
        print(f"  {c['first_name']} {c['last_name']} ({c['personal_email']})")

    print("\nP10 check, Benjamin should have a hired application:")
    for c in find("Hayes", "Benjamin"):
        for a in c["applications"]:
            start = a["offer"]["start_date"] if a["offer"] else None
            print(f"  status={a['status']}, start={start}")