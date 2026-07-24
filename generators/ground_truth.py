"""Ground truth for Northline Outfitters synthetic data.

This file defines the "real" people behind both source system exports.
It is the answer key: the person_num here never appears in any export,
but lets us verify that identity resolution reaches the right answer.

The two generator scripts (generate_hris.py, generate_ats.py) consume
this ground truth and each render their system's imperfect view of it.
"""

import random
from dataclasses import dataclass
from datetime import date, timedelta

from faker import Faker

# Fixing the seed makes every run reproducible: same people, same
# problems, every time. Any constant works.
SEED = 42

# The simulation's "today". Frozen so the data never drifts as real
# time passes: a run next month produces identical files to a run now.
SIM_TODAY = date(2026, 7, 1)

# Department catalog. Each department has a career ladder, ordered
# junior to senior, so promotions can pick "the next title up".
DEPARTMENTS = {
    "Retail Operations": [
        "Retail Associate",
        "Senior Retail Associate",
        "Shift Supervisor",
        "Assistant Store Manager",
        "Store Manager",
    ],
    "Distribution": [
        "Warehouse Associate",
        "Warehouse Team Lead",
        "Inventory Lead",
        "Distribution Supervisor",
    ],
    "Customer Experience": [
        "Customer Care Representative",
        "Senior Customer Care Representative",
        "Customer Care Team Lead",
    ],
    "Merchandising": [
        "Merchandising Coordinator",
        "Senior Merchandising Coordinator",
        "Merchandising Manager",
    ],
    "Marketing": [
        "Marketing Coordinator",
        "Marketing Specialist",
        "Marketing Manager",
    ],
    "Finance": [
        "Financial Analyst",
        "Senior Financial Analyst",
        "Finance Manager",
    ],
    "People & Culture": [
        "HR Coordinator",
        "HR Generalist",
        "HR Business Partner",
    ],
    "Technology": [
        "IT Support Specialist",
        "Systems Analyst",
        "Software Developer",
    ],
}

# Relative sizes: a retailer is mostly stores and a warehouse.
DEPARTMENT_WEIGHTS = {
    "Retail Operations": 45,
    "Distribution": 18,
    "Customer Experience": 8,
    "Merchandising": 6,
    "Marketing": 6,
    "Finance": 5,
    "People & Culture": 5,
    "Technology": 7,
}

# Chance a given stint has ended by now, by department.
# Retail and warehouse churn harder than head office.
DEPARTMENT_TURNOVER = {
    "Retail Operations": 0.50,
    "Distribution": 0.40,
}
DEFAULT_TURNOVER = 0.25


@dataclass
class Assignment:
    """A role a person held during a stint. A promotion or department
    change creates a new assignment with a new effective date."""
    effective_date: date
    department: str
    job_title: str


@dataclass
class Stint:
    """One continuous period of employment. A rehired person has
    multiple stints. end_date of None means currently employed."""
    start_date: date
    end_date: date | None
    assignments: list[Assignment]
    employment_type: str = "FT"  # FT, PT, or Contract


@dataclass
class Person:
    """One real human. The person_num is our secret answer key and
    never appears in either system's export."""
    person_num: int
    first_name: str
    last_name: str
    personal_emails: list[str]      # ordered oldest to newest
    phone: str
    stints: list[Stint]
    name_variant: str | None = None      # e.g. "Rob" for Robert, used by the ATS
    former_last_name: str | None = None  # pre-marriage name, used by the ATS


def build_special_people() -> list[Person]:
    """The hand-built people who carry the planted identity problems
    (P4 through P7) and the no show (P10). Listed in problem order.
    One planted problem per person, so a failed match always has one
    explanation."""

    people = []

    # ------------------------------------------------------------------
    # P4 (clean case): Maria Santos, rehired with the SAME personal
    # email both times. The easy rehire: email matching alone links her
    # two employment records.
    # ------------------------------------------------------------------
    people.append(Person(
        person_num=1,
        first_name="Maria",
        last_name="Santos",
        personal_emails=["maria.santos88@gmail.com"],
        phone="416-555-0181",
        stints=[
            Stint(
                start_date=date(2020, 3, 9),
                end_date=date(2023, 8, 18),
                assignments=[
                    Assignment(date(2020, 3, 9), "Retail Operations", "Retail Associate"),
                    Assignment(date(2022, 1, 10), "Retail Operations", "Shift Supervisor"),
                ],
            ),
            Stint(
                start_date=date(2025, 2, 3),
                end_date=None,
                assignments=[
                    Assignment(date(2025, 2, 3), "Retail Operations", "Assistant Store Manager"),
                ],
            ),
        ],
    ))

    # ------------------------------------------------------------------
    # P4 (hard case): Devon Clarke, rehired with a DIFFERENT personal
    # email the second time. Email matching fails; the pipeline must
    # fall back to name plus corroborating signals (phone).
    # ------------------------------------------------------------------
    people.append(Person(
        person_num=2,
        first_name="Devon",
        last_name="Clarke",
        personal_emails=["dclarke_2011@hotmail.com", "devon.clarke@gmail.com"],
        phone="905-555-0139",
        stints=[
            Stint(
                start_date=date(2021, 6, 14),
                end_date=date(2024, 4, 26),
                assignments=[
                    Assignment(date(2021, 6, 14), "Distribution", "Warehouse Associate"),
                ],
            ),
            Stint(
                start_date=date(2025, 9, 8),
                end_date=None,
                assignments=[
                    Assignment(date(2025, 9, 8), "Distribution", "Inventory Lead"),
                ],
            ),
        ],
    ))

    # ------------------------------------------------------------------
    # P5 (duplicate candidates): Priya Sharma applied in 2022 with her
    # university email and was rejected. She applied again in 2024 with
    # a new email and was hired. TalentFlow's deduplication missed it,
    # so she exists as TWO candidate records. The ATS generator splits
    # her emails across the two records.
    # ------------------------------------------------------------------
    people.append(Person(
        person_num=3,
        first_name="Priya",
        last_name="Sharma",
        personal_emails=["psharma@alumni.uwaterloo.ca", "priya.sharma.to@gmail.com"],
        phone="647-555-0163",
        stints=[
            Stint(
                start_date=date(2024, 6, 10),
                end_date=None,
                assignments=[
                    Assignment(date(2024, 6, 10), "Marketing", "Marketing Coordinator"),
                ],
            ),
        ],
    ))

    # ------------------------------------------------------------------
    # P6 (nickname drift): Robert Chen goes by "Rob". He applied as
    # "Robert" but HR entered him as "Rob" (or vice versa; the ATS
    # generator uses name_variant). One continuous stint, hired after
    # 2022 so he exists in BOTH systems. His only quirk is the name.
    # ------------------------------------------------------------------
    people.append(Person(
        person_num=4,
        first_name="Robert",
        last_name="Chen",
        personal_emails=["robert.chen@gmail.com"],
        phone="905-423-5920",
        stints=[
            Stint(
                start_date=date(2023, 5, 15),
                end_date=None,
                assignments=[
                    Assignment(date(2023, 5, 15), "Merchandising", "Merchandising Coordinator"),
                    Assignment(date(2025, 4, 1), "Merchandising", "Senior Merchandising Coordinator"),
                ],
            ),
        ],
        name_variant="Rob",
    ))

    # ------------------------------------------------------------------
    # P6 (last name change): Emily Tran married in 2025 and became
    # Emily Foster. PeopleCore was updated to Foster; her TalentFlow
    # application from 2023 still says Tran. Name matching alone fails;
    # her personal email is the link.
    # ------------------------------------------------------------------
    people.append(Person(
        person_num=5,
        first_name="Emily",
        last_name="Foster",
        personal_emails=["emily.tran.93@gmail.com"],
        phone="416-555-0227",
        stints=[
            Stint(
                start_date=date(2023, 9, 5),
                end_date=None,
                assignments=[
                    Assignment(date(2023, 9, 5), "Finance", "Financial Analyst"),
                ],
            ),
        ],
        former_last_name="Tran",
    ))

    # ------------------------------------------------------------------
    # P7 (work email collision): two different people, both named
    # Sarah Lee, both currently employed. The HRIS generator gives the
    # second one a suffixed work email (sarah.lee2@). Different personal
    # emails and phones prove they are distinct humans. The pipeline
    # must NOT merge them.
    # ------------------------------------------------------------------
    people.append(Person(
        person_num=6,
        first_name="Sarah",
        last_name="Lee",
        personal_emails=["sarahlee.416@gmail.com"],
        phone="416-555-0244",
        stints=[
            Stint(
                start_date=date(2019, 11, 4),
                end_date=None,
                assignments=[
                    Assignment(date(2019, 11, 4), "People & Culture", "HR Coordinator"),
                    Assignment(date(2023, 2, 20), "People & Culture", "HR Business Partner"),
                ],
            ),
        ],
    ))

    people.append(Person(
        person_num=7,
        first_name="Sarah",
        last_name="Lee",
        personal_emails=["s.lee.designs@gmail.com"],
        phone="289-555-0308",
        stints=[
            Stint(
                start_date=date(2024, 3, 18),
                end_date=None,
                assignments=[
                    Assignment(date(2024, 3, 18), "Retail Operations", "Visual Merchandiser"),
                ],
            ),
        ],
    ))

    # ------------------------------------------------------------------
    # P10 (the no show): TalentFlow believes Benjamin Hayes was hired
    # (accepted offer, start date in the past) but he never actually
    # started. No stints: he never worked at Northline. Only the ATS
    # generator will produce records for him.
    # ------------------------------------------------------------------
    people.append(Person(
        person_num=8,
        first_name="Benjamin",
        last_name="Hayes",
        personal_emails=["benjamin.hayes@gmail.com"],
        phone="647-543-9530",
        stints=[],
    ))

    return people


def build_random_people(count: int = 242, start_num: int = 9) -> list[Person]:
    """The ordinary population around the special people. Random but
    reproducible: the seed fixes every choice, so every run produces
    the identical company."""

    rng = random.Random(SEED)
    Faker.seed(SEED)
    fake = Faker("en_CA")

    # Names already used by special people. Random generation must not
    # accidentally create a third Sarah Lee, which would contaminate
    # the carefully isolated P7 test case.
    reserved_names = {
        (p.first_name, p.last_name) for p in build_special_people()
    }

    dept_names = list(DEPARTMENT_WEIGHTS.keys())
    dept_weights = list(DEPARTMENT_WEIGHTS.values())

    people = []
    used_names = set(reserved_names)

    for i in range(count):
        # Generate a unique full name, retrying on collisions.
        while True:
            first = fake.first_name()
            last = fake.last_name()
            if (first, last) not in used_names:
                used_names.add((first, last))
                break

        # Department, weighted so the company shape is realistic.
        department = rng.choices(dept_names, weights=dept_weights, k=1)[0]
        ladder = DEPARTMENTS[department]

        # Hire date: any day from 2015 through mid 2026, weighted
        # toward recent years to mimic company growth.
        year = rng.choices(
            list(range(2015, 2027)),
            weights=[2, 2, 3, 3, 4, 5, 6, 7, 8, 9, 10, 4],
            k=1,
        )[0]
        month = rng.randint(1, 12)
        day = rng.randint(1, 28)
        hire_date = date(year, month, day)
        if hire_date > SIM_TODAY - timedelta(days=14):
            hire_date = SIM_TODAY - timedelta(days=14)

        # Employment type: stores and warehouse lean part time.
        if department in ("Retail Operations", "Distribution"):
            employment_type = rng.choices(
                ["FT", "PT", "Contract"], weights=[55, 40, 5], k=1
            )[0]
        else:
            employment_type = rng.choices(
                ["FT", "PT", "Contract"], weights=[85, 8, 7], k=1
            )[0]

        # Start at the bottom of the ladder, mostly.
        start_level = 0 if rng.random() < 0.8 else min(1, len(ladder) - 1)
        assignments = [Assignment(hire_date, department, ladder[start_level])]

        # Maybe a promotion, if they have been around at least 2 years
        # and the ladder has a next rung.
        tenure_days = (SIM_TODAY - hire_date).days
        if (
            tenure_days > 730
            and start_level + 1 < len(ladder)
            and rng.random() < 0.4
        ):
            promo_date = hire_date + timedelta(
                days=rng.randint(365, min(tenure_days, 1460))
            )
            assignments.append(
                Assignment(promo_date, department, ladder[start_level + 1])
            )

        # Has this stint ended? Churn depends on department, and very
        # recent hires have not had time to leave.
        turnover = DEPARTMENT_TURNOVER.get(department, DEFAULT_TURNOVER)
        end_date = None
        if tenure_days > 120 and rng.random() < turnover:
            end_offset = rng.randint(90, tenure_days - 14)
            end_date = hire_date + timedelta(days=end_offset)
            # A termination truncates history: drop any promotion that
            # would have happened after they left.
            assignments = [a for a in assignments if a.effective_date <= end_date]

        # Contact details. Ground truth stores clean, consistent
        # formats; the generators add the formatting mess on export.
        email_local = f"{first.lower()}.{last.lower()}{rng.randint(1, 99)}"
        email_domain = rng.choice(
            ["gmail.com", "hotmail.com", "outlook.com", "yahoo.ca"]
        )
        email = f"{email_local}@{email_domain}"
        phone = f"{rng.choice(['416', '647', '905', '289'])}-555-{rng.randint(0, 9999):04d}"

        people.append(Person(
            person_num=start_num + i,
            first_name=first,
            last_name=last,
            personal_emails=[email],
            phone=phone,
            stints=[
                Stint(
                    start_date=hire_date,
                    end_date=end_date,
                    assignments=assignments,
                    employment_type=employment_type,
                )
            ],
        ))

    return people


def build_all_people() -> list[Person]:
    """The complete Northline population: specials plus the crowd."""
    return build_special_people() + build_random_people()


if __name__ == "__main__":
    # Quick manual check: run `python generators/ground_truth.py`.
    specials = build_special_people()
    everyone = build_all_people()

    print("Special people:")
    for person in specials:
        stint_count = len(person.stints)
        if stint_count == 0:
            status = "no stints (never employed)"
        else:
            active = person.stints[-1].end_date is None
            status = "active" if active else "former"
        print(
            f"  #{person.person_num} {person.first_name} {person.last_name}: "
            f"{stint_count} stint(s), {status}"
        )

    active_count = sum(
        1 for p in everyone if p.stints and p.stints[-1].end_date is None
    )
    former_count = sum(
        1 for p in everyone if p.stints and p.stints[-1].end_date is not None
    )

    print(f"\nTotal people: {len(everyone)}")
    print(f"Currently active: {active_count}")
    print(f"Former employees: {former_count}")

    print("\nActive headcount by department:")
    dept_counts = {}
    for p in everyone:
        if p.stints and p.stints[-1].end_date is None:
            dept = p.stints[-1].assignments[-1].department
            dept_counts[dept] = dept_counts.get(dept, 0) + 1
    for dept, n in sorted(dept_counts.items(), key=lambda kv: -kv[1]):
        print(f"  {dept}: {n}")