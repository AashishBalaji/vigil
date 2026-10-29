# Contributing to Vigil

This is the standard this project actually follows — written down so
it can be handed to a newer engineer instead of explained from
scratch each time. The JD mentions mentoring junior developers
explicitly; this file is what that looks like as code, not a claim
that can't be checked.

## Before opening a PR

- [ ] **The feature contract is respected.** Any change touching
  model inputs goes through `service/vigil/features.py`'s
  `FEATURE_NAMES` / `AlertFeatures` — never add a column to the
  training dataset that the service doesn't also build at inference
  time, or vice versa. This is the single most common way a "the
  model worked in training" bug reaches production; see the comment
  at the top of `features.py` for why it's structured as the one
  source of truth both sides import from.
- [ ] **New DB-touching tests actually ran against a real database**,
  not just code review. `conftest.py` points at a real local Postgres
  (`vigil_test`) by default and `mongomock` for Mongo unless
  `VIGIL_MONGO_BACKEND=real` is set — CI runs the real-Mongo path.
  Run `pytest -v` yourself before asking for review; don't rely on CI
  to be the first execution of your test.
- [ ] **A concurrency-sensitive change gets a concurrency test**, not
  just a happy-path one. `test_concurrent_dispositions_on_the_same_
  alert_exactly_one_wins` is the template: a `ThreadPoolExecutor`
  firing real concurrent requests, asserting exactly one outcome wins,
  not sequential calls dressed up as a race test.
- [ ] **A new failure mode gets a `RUNBOOK.md` entry**, written the
  way the existing four are: symptom, likely cause (in order of
  likelihood if there's more than one), response. If you can't write
  the "response" section yet, that's a sign the change isn't done —
  not a sign to skip the entry.
- [ ] **Honest metrics only.** If you retrain the model, let
  `model/train.py` report whatever `test_roc_auc` /
  `queue_volume_reduction` actually come out — don't tune the
  synthetic generator's separability to make the number look better.
  A suspiciously perfect metric is a bug report, not a result (this
  happened once already — see the label-noise comment in
  `generate_data.py`).

## Code review checklist (for reviewing someone else's PR)

1. Does every new Postgres write that can race with another write use
   a single conditional statement (`UPDATE ... WHERE <invariant>
   RETURNING ...`, checked by row count) rather than a separate
   check-then-act? This is the one invariant this codebase cannot
   afford to regress on.
2. Does every new feature field have a `Field(..., ge=..., le=...)`
   constraint tight enough that a silently-wrong upstream value would
   get rejected rather than scored? See Runbook §2 for why this
   matters more here than in a typical CRUD field.
3. Would a new teammate, reading only this file and `RUNBOOK.md`,
   understand why the code is shaped the way it is? If the answer
   requires tribal knowledge not written down anywhere, that's a
   documentation gap to raise before approving, not after.

## Commit style

Small, real commits over one large one — each commit should leave the
test suite passing. If a bug is found and fixed mid-feature (as
happened with the dashboard's hide-on-success bug and the service's
dependency-blind `/health` check during this project's own build),
that's its own commit with its own explanation, not folded silently
into an unrelated one.
