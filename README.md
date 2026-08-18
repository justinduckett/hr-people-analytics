# Northline Outfitters People Analytics Pipeline

An end to end analytics engineering project that solves a problem every HR team has: two systems that both track people, neither of which knows what a person is. Synthetic HR and recruiting data are generated daily, ingested into a warehouse, resolved into a single record per human being, and served to a dashboard that answers headcount and turnover questions the source systems cannot answer on their own.

[View the live dashboard](https://datastudio.google.com/s/r_Lk8rb8nA8)

## Architecture

![People Analytics architecture diagram](assets/people_analytics_pipeline_architecture.png)

## The problem this solves

Northline Outfitters is a fictional Canadian outdoor retailer with about 190 employees. Its people data lives in two systems that were never designed to talk to each other:

- **PeopleCore (HRIS)** is the system of record for employment. It exports a nightly CSV, one row per employment record.
- **TalentFlow (ATS)** is the recruiting system. It exports JSON, one record per candidate, with applications nested inside.

Neither system counts people. PeopleCore counts employment records, so someone who leaves and is rehired appears twice with two unrelated IDs. TalentFlow counts candidate profiles, most belonging to people who were never hired, and it identifies people by self reported email and phone rather than an employee ID.

The result is that a question as basic as "how many people work here, and how many of them are returning employees" has no answer in either system. This pipeline builds that answer.

## Identity resolution

The core of the project. A canonical `person_key` is built in two stages.

**Within the HR system**, employment records are linked by two rules:

1. Records sharing a personal email address belong to one person.
2. Records with the same full name where employment is strictly sequential (one record terminated before the next began) belong to one person.

The second rule's non overlap condition is the safeguard. Two employees named Sarah Lee working at the same time are different people, and concurrent same name records never merge. Over merging is the more dangerous failure: a missed link creates a duplicate someone might notice, while a false merge silently corrupts headcount.

**Across systems**, candidates are matched to employment records by a three rule cascade:

1. Personal email match. This survives nicknames and name changes, which is why it runs first.
2. Same full name plus a hired application whose offer start date falls within seven days of the employee's hire date. The date alignment is the corroboration that makes name matching safe.
3. Shared standardized phone number and full name, which links duplicate candidate records to each other.

Every match records which rules fired, so the reasoning is auditable rather than a black box. Candidates that match nothing keep a null key, which for the roughly 170 people who applied and were never hired is the correct answer rather than a failure.

## Data quality

Ten problems are deliberately planted in the source data, each one a realistic issue found in real HR systems, and each forcing the pipeline to demonstrate a specific technique.

| ID | Problem | What the pipeline does |
|---|---|---|
| P01 | Sources arrive in different formats (CSV and nested JSON) | Staging models conform both into typed tables and unnest the JSON applications |
| P02 | No source table is one row per person | A canonical person record is built by resolving records across and within systems |
| P03 | Exports show current state only with no history | Snapshots capture changes over time into a slowly changing dimension |
| P04 | Rehired employees get a new ID with nothing linking the two records | Identity resolution links them by shared email or by same name with sequential employment |
| P05 | One person exists as two candidate records in the recruiting system | Deduplication by matching name and standardized phone number |
| P06 | Names differ between systems (nicknames and married names) | Matching leads with email so it survives any name change |
| P07 | Two different employees share a name and get colliding work emails | Concurrent same name records are never merged and a uniqueness test enforces it |
| P08 | Department names drift across spellings and casing | A mapping table standardizes them with a test that fails on unmapped values |
| P09 | Phone numbers and emails arrive in inconsistent formats | Standardized in staging before any matching runs |
| P10 | A candidate marked hired never appears in the HR system | The HR system is treated as the system of record for employment |

Every dbt build runs automated tests: primary key uniqueness, not null constraints, accepted values checks on status fields, and an assertion that no candidate ever matches two different people. The department mapping test is the one that earns its keep most often, because it fails the build the moment the source system produces a spelling nobody has seen before, rather than letting a null department reach the dashboard.

## The dimensional model

![People Analytics entity relationship diagram](assets/people_analytics_erd.png)

Two star schemas share conformed dimensions.

**Employment events** is a transaction fact: one row per hire and one per termination. It joins to `dim_person`, `dim_date`, and `dim_department`. Because events are additive, counting them over any period is always correct.

**Headcount** is a periodic snapshot fact: one row per day per department per employment type. This measure is semi additive, meaning it can be summed across departments but never across dates, because that would count the same person once for every day they worked. Two aggregate tables (`fct_headcount_monthly` and `fct_headcount_current`) are built from the daily fact so the BI layer never has to make that mistake.

Slowly changing dimension type 2 history is captured by a dbt snapshot on the employment records. When someone transfers departments, the old version of their record is closed with an end timestamp and a new version opens, which is what makes point in time questions answerable at all.

## Design decisions and limitations

**Reconstructed history versus observed history.** The headcount facts rebuild the full history from hire and termination dates on every run, so they are gap tolerant: if the pipeline does not run for two weeks, one run brings everything current. The snapshot is different. It records changes as it observes them, so its fidelity depends on run cadence, and days it did not run are days it did not see. The dashboard is built entirely on the reconstructed facts for that reason, and the snapshot stands as a demonstrated capability rather than a chart source.

**Department is denormalized into the facts.** `dim_department` defines department attributes (division, whether the department is frontline), but the fact tables carry the department name directly rather than a surrogate key. This avoids pushing a join into the BI layer for an attribute with eight values and no volatility. If departments later gained cost centres or regions, promoting them to a proper key based join would be the right move.

**Local execution, manual triggering.** Prefect Cloud provides the schedule, run history, logging, and failure visibility, but the flow executes locally through `flow.serve()`. That means runs happen when the machine is awake and serving, not unattended at 6am. Prefect offers managed execution that would close this gap, at the cost of storing warehouse credentials with a third party. The tradeoff was scoped deliberately: the orchestration logic is proven, and the dashboard is backed by durable warehouse tables that stay correct regardless of when the pipeline last ran.

**Synthetic data is designed, not sampled.** Every data quality problem in this project exists because it was planted, which means the pipeline was built knowing exactly what it needed to catch. Real source profiling is the harder version of this work: discovering the problems rather than authoring them. A separate ground truth file records the true identity of every person, which is what makes it possible to verify that identity resolution reached the right answer rather than merely a plausible one.

**Headcount counts employment records, not people.** For a rehired employee, two separate employment periods are two separate contributions to headcount over time, which is the correct treatment. Person level counts come from `dim_person` instead.

## Lessons learned the hard way

**Never sum a snapshot measure across dates.** The first version of the headcount dashboard reported 284,814 employees. The fact table stores headcount per day, so summing across every day counted each person once per day they worked, producing person days rather than people. The fix was purpose built aggregate tables that make the mistake impossible, rather than relying on the BI tool being configured correctly.

**An audit trail that overstates its evidence is worse than none.** The identity resolution originally labelled every record with an email as an email match, including records whose email was shared with nobody. The keys were correct, but the explanation of how they were reached was not. Filtering to genuinely shared emails made the audit column honest.

**Change one thing at a time in test data.** An early version of the nickname test case was also a rehire, which meant a failed match would have had two possible explanations. Each planted problem now sits on its own person so that a test failure has exactly one cause.

**Environment variables do not survive a closed terminal.** The credential path that authenticates the pipeline to the warehouse was set per session and silently vanished between working sessions, producing a confusing wall of retries. Moving it into the shell profile fixed it permanently, and the credential inventory now records every location that references the key.

## How to run

Clone the repo and create a virtual environment:

```
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

Add a GCP service account key as `gcp-key.json` in the project root (never committed; see `.gitignore`) and point the environment at it:

```
export GOOGLE_APPLICATION_CREDENTIALS="$PWD/gcp-key.json"
```

Configure dbt by adding a BigQuery profile named `northline_hr` to `~/.dbt/profiles.yml`, using the service account method and the same region as your BigQuery datasets.

Run the full pipeline once:

```
python ingestion/flow.py
```

This generates both source exports for today's date, loads them to the `hr_raw` dataset, then runs `dbt build`, which executes seeds, models, snapshots, and tests in dependency order.

To register the flow with Prefect Cloud and trigger runs from its UI:

```
python ingestion/flow.py serve
```

## Project structure

```
generators/     synthetic source systems and the ground truth they render
ingestion/      Prefect flow: generate, load, transform
dbt/            dbt Core project (staging, intermediate, marts, snapshots)
docs/           source system design, decisions log, credential inventory
```

## Links

- [Live dashboard](https://datastudio.google.com/s/r_Lk8rb8nA8)
- [Portfolio writeup](https://github.com/justinduckett/portfolio/blob/main/people-analytics.md)