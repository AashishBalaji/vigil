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
| "Support": troubleshooting, mentoring | `RUNBOOK.md` (4 real failure modes, found or anticipated while building this) and `CONTRIBUTING.md` (the PR/review checklist this project actually follows) |

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

cd service && pytest -v        # 12 tests, against a real local Postgres (see conftest.py)

uvicorn vigil.main:app --reload --port 8010   # from service/, with VIGIL_* env vars set
python3 -m http.server 8011 --directory ../dashboard   # separately, for the UI
```

See `RUNBOOK.md` for the failure modes this project is built to
withstand, and `model/artifacts/metrics.json` (after training) for
this run's actual precision/recall/queue-reduction numbers.
