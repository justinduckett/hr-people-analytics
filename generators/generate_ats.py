"""TalentFlow (ATS) generator.

Consumes the ground truth and renders TalentFlow's imperfect view of
it as data/candidates.json: one object per candidate with nested
applications, covering only what a system adopted in 2022 could know.

Distortions applied here:
- P5: Priya Sharma appears as TWO candidate records (dedup failure)
- P6: Rob Chen's record uses his nickname; Emily's uses her maiden name
- P9: phone numbers and email casing exported in inconsistent formats
- P10: Benjamin Hayes has a hired application but never started
- Plus realistic noise: rejected, withdrawn, and in-progress candidates
  who never became employees

A principle worth noting: recoverable mess (formatting, casing) is
applied to everyone including special people, because cleaning undoes
it deterministically. Destructive mess (dropped fields, wrong values)
never touches the specials, so their planted matching signals survive.
"""

import json
import random
import string
from datetime import date, datetime, timedelta
from pathlib import Path

from faker import Faker

from ground_truth import (
    DEPARTMENTS,
    SEED,
    SIM_TODAY,
    build_all_people,
)

OUTPUT_PATH = Path(__file__).resolve().parent.parent / "data" / "candidates.json"

# TalentFlow was adopted at the start of 2022. It knows nothing about
# anyone hired before this date (part of the P2/P3 asymmetry).
TALENTFLOW_ADOPTED = date(2022, 1, 1)

# Person numbers of specials this generator treats specially.
PRIYA = 3      # P5: split into two candidate records
BENJAMIN = 8   # P10: hired application, but he never started


def make_id(prefix: str, rng: random.Random) -> str:
    """IDs like cand_8f3k2 / app_x92m1: prefix plus 5 random
    lowercase alphanumerics, the style many SaaS tools use."""
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


def application_for_hire(stint, rng: random.Random) -> dict:
    """A hired application leading to the given stint: applied about
    six weeks before the start date, offer accepted about two weeks
    before."""
    start = stint.start_date
    applied = start - timedelta(days=rng.randint(30, 55))
    accepted = start - timedelta(days=rng.randint(10, 18))
    first = stint.assignments[0]
    return {
        "application_id": None,  # filled by caller
        "job_title": first.job_title,
        "department": first.department,
        "applied_at": applied.isoformat(),
        "status": "hired",
        "offer": {
            "accepted_at": accepted.isoformat(),
            "start_date": start.isoformat(),
        },
    }


def noise_application(applied: date, rng: random.Random) -> dict:
    """A non-hired application: rejected, withdrawn, or (if recent)
    still in progress."""
    department = rng.choice(list(DEPARTMENTS.keys()))
    job_title = rng.choice(DEPARTMENTS[department][:2])
    if (SIM_TODAY - applied).days < 60 and rng.random() < 0.5:
        status = "in_progress"
    else:
        status = rng.choices(["rejected", "withdrawn"], weights=[75, 25], k=1)[0]
    return {
        "application_id": None,
        "job_title": job_title,
        "department": department,
        "applied_at": applied.isoformat(),
        "status": status,
        "offer": None,
    }


def candidate_shell(first, last, email, phone, first_applied: date, rng) -> dict:
    """The outer candidate object, with the P9 formatting mess
    applied to the contact fields."""
    created = datetime(
        first_applied.year, first_applied.month, first_applied.day,
        rng.randint(8, 20), rng.randint(0, 59), rng.randint(0, 59),
    )
    return {
        "candidate_id": make_id("cand", rng),
        "first_name": first,
        "last_name": last,
        "personal_email": messy_email(email, rng),
        "phone": messy_phone(phone, rng),
        "created_at": created.isoformat() + "Z",
        "applications": [],
    }


def build_candidates_from_people(people, rng: random.Random) -> list[dict]:
    """Candidates for real people: anyone whose employment stint
    began after TalentFlow was adopted applied through it."""
    candidates = []

    for person in people:
        # The name TalentFlow holds: the one the candidate typed.
        # Nicknames and maiden names live here (P6).
        first = person.name_variant or person.first_name
        last = person.former_last_name or person.last_name

        # --- Special case: Priya, the dedup failure (P5) -----------
        # Her 2022 rejected application and her 2024 hired application
        # were filed under different emails, so TalentFlow created two
        # separate candidate records. Same phone: the clue that they
        # are one person.
        if person.person_num == PRIYA:
            old_applied = date(2022, 5, 16)
            rec1 = candidate_shell(
                first, last, person.personal_emails[0], person.phone,
                old_applied, rng,
            )
            app1 = noise_application(old_applied, rng)
            app1["status"] = "rejected"
            app1["department"] = "Marketing"
            app1["job_title"] = "Marketing Coordinator"
            app1["application_id"] = make_id("app", rng)
            rec1["applications"].append(app1)
            candidates.append(rec1)

            stint = person.stints[0]
            rec2 = candidate_shell(
                first, last, person.personal_emails[-1], person.phone,
                stint.start_date - timedelta(days=40), rng,
            )
            app2 = application_for_hire(stint, rng)
            app2["application_id"] = make_id("app", rng)
            rec2["applications"].append(app2)
            candidates.append(rec2)
            continue

        # --- Special case: Benjamin, the no show (P10) -------------
        # TalentFlow believes he was hired in early 2025. He has no
        # stints in ground truth: he never actually started.
        if person.person_num == BENJAMIN:
            fake_start = date(2025, 3, 3)
            rec = candidate_shell(
                first, last, person.personal_emails[0], person.phone,
                fake_start - timedelta(days=45), rng,
            )
            app = {
                "application_id": make_id("app", rng),
                "job_title": "Customer Care Representative",
                "department": "Customer Experience",
                "applied_at": (fake_start - timedelta(days=45)).isoformat(),
                "status": "hired",
                "offer": {
                    "accepted_at": (fake_start - timedelta(days=14)).isoformat(),
                    "start_date": fake_start.isoformat(),
                },
            }
            rec["applications"].append(app)
            candidates.append(rec)
            continue

        # --- The general case -------------------------------------
        # One candidate record per person, holding a hired application
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

        rec = candidate_shell(
            first, last, email, person.phone,
            first_stint.start_date - timedelta(days=40), rng,
        )
        for stint_index, stint in ats_stints:
            app = application_for_hire(stint, rng)
            app["application_id"] = make_id("app", rng)
            rec["applications"].append(app)

        # Realism: some hired people also applied unsuccessfully
        # earlier (a rejected application in their history).
        if rng.random() < 0.15:
            earlier = first_stint.start_date - timedelta(days=rng.randint(200, 700))
            if earlier >= TALENTFLOW_ADOPTED:
                app = noise_application(earlier, rng)
                app["application_id"] = make_id("app", rng)
                rec["applications"].insert(0, app)

        candidates.append(rec)

    return candidates


def build_noise_candidates(count: int, rng: random.Random, reserved_names) -> list[dict]:
    """Candidates who never became employees: the rejected, the
    withdrawn, and the still-in-progress. Most of any real ATS."""
    Faker.seed(SEED + 3)
    fake = Faker("en_CA")
    candidates = []
    used = set(reserved_names)

    for _ in range(count):
        while True:
            first = fake.first_name()
            last = fake.last_name()
            if (first, last) not in used:
                used.add((first, last))
                break

        days_back = rng.randint(14, (SIM_TODAY - TALENTFLOW_ADOPTED).days)
        applied = SIM_TODAY - timedelta(days=days_back)
        email = f"{first.lower()}.{last.lower()}{rng.randint(1, 999)}@{rng.choice(['gmail.com', 'hotmail.com', 'outlook.com', 'yahoo.ca'])}"
        phone = f"{rng.choice(['416', '647', '905', '289'])}-555-{rng.randint(0, 9999):04d}"

        rec = candidate_shell(first, last, email, phone, applied, rng)
        app = noise_application(applied, rng)
        app["application_id"] = make_id("app", rng)
        rec["applications"].append(app)

        # Some persistent candidates applied twice.
        if rng.random() < 0.2:
            applied2 = applied + timedelta(days=rng.randint(60, 400))
            if applied2 < SIM_TODAY:
                app2 = noise_application(applied2, rng)
                app2["application_id"] = make_id("app", rng)
                rec["applications"].append(app2)

        candidates.append(rec)

    return candidates


if __name__ == "__main__":
    rng = random.Random(SEED + 4)
    people = build_all_people()

    from_people = build_candidates_from_people(people, rng)
    reserved = {(p.first_name, p.last_name) for p in people}
    noise = build_noise_candidates(140, rng, reserved)

    candidates = from_people + noise
    # Shuffle so real hires and noise are interleaved like a real
    # export, not two neat blocks.
    rng.shuffle(candidates)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(candidates, f, indent=2)

    print(f"Wrote {len(candidates)} candidates to {OUTPUT_PATH}")
    hired = sum(
        1 for c in candidates
        for a in c["applications"] if a["status"] == "hired"
    )
    print(f"Hired applications: {hired}")

    # Spot checks on the planted problems.
    def find(last_name, first_name=None):
        return [
            c for c in candidates
            if c["last_name"] == last_name
            and (first_name is None or c["first_name"] == first_name)
        ]

    priya = find("Sharma")
    print(f"\nP5 check, Priya should be TWO records, different emails, same phone:")
    for c in priya:
        print(f"  {c['candidate_id']}: {c['personal_email']} / {c['phone']}")

    rob = find("Chen")
    print(f"\nP6 check, Chen's first name should be the nickname:")
    for c in rob:
        print(f"  {c['first_name']} {c['last_name']}")

    emily = find("Tran")
    print(f"\nP6 check, Emily should appear under maiden name Tran:")
    for c in emily:
        print(f"  {c['first_name']} {c['last_name']} ({c['personal_email']})")

    ben = find("Hayes", "Benjamin")
    print(f"\nP10 check, Benjamin should have a hired application:")
    for c in ben:
        for a in c["applications"]:
            print(f"  status={a['status']}, start={a['offer']['start_date'] if a['offer'] else None}")

    print(f"\nP9 check, phone format variety (first 6):")
    for c in candidates[:6]:
        print(f"  {c['phone']}")