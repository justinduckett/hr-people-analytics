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
    name_variant: str | None = None      # e.g. "Rob" for Robert, used by the ATS
    former_last_name: str | None = None  # pre-marriage name, used by the ATS


def build_special_people() -> list[Person]:
    """The hand-built people who carry the planted problems.
    Each is constructed deliberately so we know exactly what the
    pipeline should discover about them. One planted problem per
    person, so a failed match always has one explanation."""

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
    # P12 (the no show): TalentFlow believes Benjamin Hayes was hired
    # (accepted offer, start date in the past) but he never actually
    # started. No stints: he never worked at Northline. Only the ATS
    # generator will produce records for him.
    # ------------------------------------------------------------------
    people.append(Person(
        person_num=3,
        first_name="Benjamin",
        last_name="Hayes",
        personal_emails=["benjamin.hayes@gmail.com"],
        phone="647-543-9530",
        stints=[],
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
    # P5 (duplicate candidates): Priya Sharma applied in 2022 with her
    # university email and was rejected. She applied again in 2024 with
    # a new email and was hired. TalentFlow's deduplication missed it,
    # so she exists as TWO candidate records. The ATS generator splits
    # her emails across the two records.
    # ------------------------------------------------------------------
    people.append(Person(
        person_num=6,
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
    # P7 (work email collision): two different people, both named
    # Sarah Lee, both currently employed. The HRIS generator gives the
    # second one a suffixed work email (sarah.lee2@). Different personal
    # emails and phones prove they are distinct humans. The pipeline
    # must NOT merge them.
    # ------------------------------------------------------------------
    people.append(Person(
        person_num=7,
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
        person_num=8,
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
    # P13 (start date disagreement): Marcus Osei's offer said he would
    # start July 8, 2024, but his actual first day slipped to July 15.
    # Ground truth records reality (July 15). The ATS generator will
    # export the original offer start_date of July 8. The pipeline
    # needs a tolerance rule to treat these as the same hire event.
    # ------------------------------------------------------------------
    people.append(Person(
        person_num=9,
        first_name="Marcus",
        last_name="Osei",
        personal_emails=["marcus.osei@gmail.com"],
        phone="416-555-0371",
        stints=[
            Stint(
                start_date=date(2024, 7, 15),
                end_date=None,
                assignments=[
                    Assignment(date(2024, 7, 15), "Distribution", "Logistics Analyst"),
                ],
            ),
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