# Vigil — Explainable AML Alert Triage

AML transaction-monitoring systems generate far more alerts than any
analyst team can review carefully — the real operational problem is
alert fatigue, not a lack of detection. Vigil scores each alert for
true-positive likelihood with a trained model, and shows exactly why:
the per-feature contribution behind every score, because an AML tool
that can't explain its own reasoning is not one a compliance team
could actually rely on.

Built for Société Générale's Software Engineer – Python Developer JD
(Bangalore; Python, SQL/PostgreSQL, MongoDB, machine learning and data
analysis, HTML/CSS/JS, Git, and an explicit "Support" section on
troubleshooting and mentoring).

## Why this design

| JD requirement | How Vigil answers it |
|---|---|
| Python | FastAPI service, real test suite, real CI |
| SQL / PostgreSQL | `alerts` + an append-only `dispositions` audit trail — integrity enforced by a single conditional `UPDATE ... WHERE status = 'OPEN'`, not a check-then-act race |
| MongoDB | Raw evidence + per-alert SHAP explanation payloads — shape genuinely varies per model version, a real reason to reach for a document store rather than a second SQL table |
| Machine learning and data analysis | A real trained `GradientBoostingClassifier`, honest train/val/test metrics, and an operational KPI (queue-volume reduction at a fixed recall target) rather than bare accuracy |
| HTML/CSS/JS | A plain analyst dashboard, no framework — matching the JD's own stated stack |
| Git | Normal commit discipline |
| "Support": troubleshooting, mentoring | `RUNBOOK.md` (5 real failure modes, found or anticipated while building this) and `CONTRIBUTING.md` (the PR/review checklist this project actually follows) |

## Auth, CORS, and connection pooling

An earlier version of this project ran with no authentication, a
wide-open CORS policy (`allow_origins=["*"]`), and a fresh
connect/close on every Postgres call — all three documented plainly
as weaknesses rather than hidden. They've since been fixed for real,
not just reworded in the docs:

- **Authentication.** Every `/alerts*` endpoint now requires a bearer
  token from `POST /auth/login` (`vigil/auth.py`, `vigil/routers/auth.py`).
  Two demo accounts are seeded idempotently on every startup —
  `analyst1` / `analyst1-pass` (role `analyst`) and `reviewer1` /
  `reviewer1-pass` (role `reviewer`) — named plainly here because this
  is a portfolio demo with no real identity system behind it, not a
  hidden default a real deployment would silently inherit. The
  disposition endpoint's `analyst` field now comes from the
  authenticated token, not a free-text field the caller could set to
  any name.
- **CORS.** Scoped to `VIGIL_CORS_ORIGINS` (comma-separated), defaulting
  to the two ways this project is actually served locally. A disallowed
  origin gets a real `400`, not a silently-permissive wildcard.
- **Connection pooling.** `vigil/db/postgres.py` now holds a
  `psycopg2.pool.ThreadedConnectionPool` (bounds via `VIGIL_PG_POOL_MIN`
  /`VIGIL_PG_POOL_MAX`, default 2/20) instead of opening and closing a
  connection per call — the 10-way concurrent-disposition test exercises
  this pool under genuine concurrent load, not just the happy path.

## Layout

```
model/      Synthetic AML alert generator + training script (writes model.joblib + honest metrics.json)
service/    FastAPI service: scoring/explainability, Postgres + Mongo persistence, API
dashboard/  Plain HTML/CSS/JS analyst UI + a real Playwright browser check against it
.github/    CI: unit+integration tests against real Postgres/Mongo, and a real-browser e2e job
RUNBOOK.md       Support runbook for this project's real failure modes
CONTRIBUTING.md  PR/review checklist — the mentoring artifact a solo project can actually produce
```

## Data, honestly

Real AML alert data is regulated and private — there is no legitimate
way to use it for a portfolio project. `model/generate_data.py`
builds a synthetic dataset across four AML typologies (structuring,
rapid fund movement, high-risk jurisdiction, dormant-account
reactivation), each with a genuine-pattern profile and a
benign-but-rule-tripping profile, plus 7% random label noise standing
in for the fact that real historical AML dispositions are themselves
imperfect judgment calls. This is documented, not hidden — see
`model/artifacts/dataset_meta.json` after running the generator.

## Running it locally

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r service/requirements-dev.txt

python model/generate_data.py
python model/train.py          # writes model.joblib + metrics.json

cd service && pytest -v        # 15 tests, against a real local Postgres (see conftest.py)

uvicorn vigil.main:app --reload --port 8010   # from service/, with VIGIL_* env vars set
python3 -m http.server 8011 --directory ../dashboard   # separately, for the UI
```

Open `http://127.0.0.1:8011` and sign in with `analyst1` / `analyst1-pass`
(see "Auth, CORS, and connection pooling" above for both demo accounts).

See `RUNBOOK.md` for the failure modes this project is built to
withstand, and `model/artifacts/metrics.json` (after training) for
this run's actual precision/recall/queue-reduction numbers.
