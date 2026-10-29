# Vigil — Support Runbook

This is the artifact the JD's "Support" section is actually asking
for: not a promise that the system never breaks, but a record of the
specific ways it can, and what to do about each one, written before
they happen rather than improvised during an incident.

## 1. The model's explanation layer fails or disagrees with the score

**Symptom:** `GET /alerts/{id}` returns a `500`, or an analyst reports
the top explanation feature doesn't match what actually looks
suspicious about the alert.

**Likely cause:** `scoring.py`'s `_explainer()` is built once per
process (`lru_cache`) against whatever model `_model()` loaded at
first use. If `model.joblib` is swapped on disk for a retrained model
*without restarting the service*, the cached explainer can end up
paired with a stale model object, or vice versa if only one of the two
caches was cleared.

**Response:**
1. Check `GET /health` responds — if the process is up but scoring is
   wrong, this is a stale-cache issue, not a crash.
2. Restart the service process. Both `lru_cache`s are process-local
   and rebuild clean on the next request.
3. Confirm `VIGIL_MODEL_PATH` actually points at the model you think
   it does — `ls -la` the target, don't assume the deploy step ran.
4. If the explanation *disagrees with the score itself* (contributions
   don't plausibly sum toward the reported probability), that is a
   genuine model/explainer mismatch, not an ops issue — page whoever
   owns `model/train.py`, don't try to patch it in the service.

## 2. A malformed or out-of-range alert payload

**Symptom:** `POST /alerts` returns `422` from a real upstream
monitoring rule, not a test script.

**Likely cause:** `AlertFeatures`' Pydantic validation (`ge=0`,
`le=1`, etc.) is deliberately strict — it rejects a negative
transaction count or a jurisdiction-risk-score above `1.0` rather than
silently clamping it, because a model trained on `[0, 1]`-bounded
features fed a `1.4` is not a model failure, it's a feature-pipeline
bug that should surface immediately rather than quietly degrade
scoring.

**Response:**
1. Read the `422` response body — Pydantic names the exact field and
   constraint that failed.
2. This is almost always a bug in the *upstream* system that computed
   the feature (e.g., a percentage sent as `80` instead of `0.80`),
   not in Vigil. Fix the sender; do not loosen the validation to make
   the symptom go away.
3. If the upstream system cannot be fixed quickly, the stopgap is a
   dedicated adapter in front of `/alerts` that normalizes known bad
   shapes — never relaxing `AlertFeatures` itself, which is the
   contract the trained model actually agrees with.

## 3. The queue appears stuck (alerts pile up, nothing gets decided)

**Symptom:** `GET /alerts?status=OPEN` keeps growing; disposition
submissions are failing or not happening.

**Likely cause, in order of likelihood:**
- **Analyst-side:** the dashboard's `API base` field points at the
  wrong host (check it against what's actually running — the
  dashboard has no server-side config, it's whatever the browser was
  told).
- **Double-decision contention:** if a popular alert is being decided
  by multiple people simultaneously, nine will see `409` and one will
  see `201` — expected and correct (see `test_concurrent_dispositions_
  on_the_same_alert_exactly_one_wins`), not a bug. Confirm *someone*
  got `201`, not that everyone got `409`.
- **Postgres/Mongo actually down:** `POST /alerts/{id}` ingestion
  writes to both stores; if either is unreachable the request fails
  outright rather than silently losing the evidence side. `GET
  /health` checks both dependencies directly (`{"status": "ok",
  "checks": {"postgres": "ok", "mongo": "ok"}}`) — a `degraded` status
  there, with one of the two checks showing an error, tells you which
  store to look at before you start guessing.

## 4. Model drift (declining precision/recall in production, not visible from logs alone)

**Symptom:** analysts report the model is "wrong more than it used to
be" — there's no exception, no 500, nothing a log line would surface.

**Response:**
1. This is the one failure mode that genuinely cannot be caught from
   inside the service — it requires comparing model predictions
   against *eventual* disposition outcomes over time, which only
   exists once enough `dispositions` rows have accumulated.
2. Query `dispositions` joined to `alerts.score` and recompute
   precision/recall/the volume-reduction KPI from `model/train.py`
   against the real outcomes, not the synthetic test set.
3. If real-world precision/recall has meaningfully diverged from
   `model/artifacts/metrics.json`'s reported numbers, that's the
   retrain trigger — re-run `generate_data.py`/`train.py` (or, in a
   real deployment, retrain against the accumulated real disposition
   history) and redeploy, following the restart step in failure mode
   #1 above so the explainer cache doesn't go stale.
