"""Ground truth for Northline Outfitters synthetic data.

This file defines the "real" people behind both source system exports.
It is the answer key: the person_num here never appears in any export,
but lets us verify that identity resolution reaches the right answer.

The two generator scripts (generate_hris.py, generate_ats.py) consume
this ground truth and each render their system's imperfect view of it.
"""

from dataclasses import dataclass, field
from datetime import date

# Fixing the seed makes every run reproducible: same people, same
# problems, every time. Any constant works. Faker and random both
# get seeded in the builder functions that use them.
SEED = 42


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
    name_variant: str | None = None  # e.g. "Rob" for Robert, used by the ATS


def build_special_people() -> list[Person]:
    """The hand-built people who carry the planted problems.
    Each is constructed deliberately so we know exactly what the
    pipeline should discover about them."""

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
    # P12 (the no show): TalentFlow believes Benjamin Hayes was hired (accepted offer, start date in the past) who never actually started.
    # ------------------------------------------------------------------
    people.append(Person(
        person_num=3,
        first_name="Benjamin",
        last_name="Hayes",
        personal_emails=["benjamin.hayes@gmail.com"],
        phone="647-543-9530",
        stints=[
        ],
    ))

    return people


if __name__ == "__main__":
    # Quick manual check: run `python generators/ground_truth.py` to
    # print a summary of the special people.
    for person in build_special_people():
        stint_count = len(person.stints)
        if stint_count == 0:
            status = "no stints (never employed)"
        else:
            active = person.stints[-1].end_date is None
            status = "active" if active else "former"
        print(
            f"#{person.person_num} {person.first_name} {person.last_name}: "
            f"{stint_count} stint(s), {status}"
        )