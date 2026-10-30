-- Postgres is the system of record here deliberately: an AML audit
-- trail is exactly the kind of data where "a row went missing" or
-- "two analysts' decisions overwrote each other" is not an acceptable
-- failure mode, so the integrity guarantees go in the schema, not in
-- application code that could forget to check something.

CREATE TABLE IF NOT EXISTS alerts (
    id              BIGSERIAL PRIMARY KEY,
    customer_id     TEXT NOT NULL,
    typology_hint   TEXT NOT NULL,
    score           DOUBLE PRECISION NOT NULL,
    status          TEXT NOT NULL DEFAULT 'OPEN'
                        CHECK (status IN ('OPEN', 'TRUE_POSITIVE', 'FALSE_POSITIVE', 'ESCALATED')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    decided_at      TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_alerts_status_score ON alerts (status, score DESC);

-- Append-only audit trail. A disposition row is never updated or
-- deleted -- if an analyst's decision needs to be reconsidered, that
-- happens as a new, separately-timestamped event, not an edit to
-- history. This is the same "the audit trail can't lose rows"
-- principle SiteWatch's idempotency invariants were built around,
-- applied to compliance record-keeping instead of telemetry.
CREATE TABLE IF NOT EXISTS dispositions (
    id              BIGSERIAL PRIMARY KEY,
    alert_id        BIGINT NOT NULL REFERENCES alerts(id),
    decision        TEXT NOT NULL CHECK (decision IN ('TRUE_POSITIVE', 'FALSE_POSITIVE', 'ESCALATED')),
    rationale       TEXT NOT NULL,
    analyst         TEXT NOT NULL,
    decided_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_dispositions_alert_id ON dispositions (alert_id);

-- Real authentication, not a free-text "analyst" field anyone could
-- type anything into. A disposition's `analyst` column now comes
-- from the authenticated user's own username (see routers/alerts.py),
-- not from the request body -- this table is what makes that
-- identity real rather than self-reported.
CREATE TABLE IF NOT EXISTS users (
    id              BIGSERIAL PRIMARY KEY,
    username        TEXT NOT NULL UNIQUE,
    password_hash   TEXT NOT NULL,
    role            TEXT NOT NULL CHECK (role IN ('analyst', 'reviewer')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
