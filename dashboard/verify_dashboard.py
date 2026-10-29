"""
A real browser-driven check of the dashboard against a real running
API, not a unit test with the DOM mocked out. Run manually against a
locally-started service+dashboard, or by CI's `ui-e2e` job against the
services it starts itself (see .github/workflows/ci.yml).

This is the exact script that caught a real bug during development:
an earlier version of app.js hid the detail panel in the same tick it
showed the "Disposition recorded" confirmation, so the message was
never actually visible to anyone -- this script's wait_for_selector on
the confirmation text is what surfaced it.
"""

from __future__ import annotations

import json
import os
import urllib.request

from playwright.sync_api import sync_playwright

API = os.environ.get("VIGIL_VERIFY_API", "http://127.0.0.1:8010")
DASH = os.environ.get("VIGIL_VERIFY_DASH", "http://127.0.0.1:8011")

TP_PROFILE = {
    "txn_count_30d": 18,
    "total_amount_30d": 95000,
    "max_single_txn": 9200,
    "distinct_counterparties_30d": 3,
    "pct_round_amounts": 0.2,
    "pct_just_under_threshold": 0.8,
    "jurisdiction_risk_score": 0.3,
    "days_since_last_activity": 2,
    "velocity_score": 4.5,
    "prior_sars_count": 0,
    "account_age_days": 900,
}


def ingest(customer_id: str) -> dict:
    body = json.dumps(
        {"customer_id": customer_id, "typology_hint": "structuring", "features": TP_PROFILE}
    ).encode()
    req = urllib.request.Request(f"{API}/alerts", data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as resp:
        return json.load(resp)


def main() -> None:
    alert = ingest("CUST-VERIFY-001")
    print("ingested alert:", alert["id"], "score:", alert["score"])

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        console_errors: list[str] = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

        page.goto(DASH)
        page.fill("#api-base", API)
        page.click("#refresh-btn")
        page.wait_for_selector("tr.queue-row")
        rows = page.locator("tr.queue-row")
        assert rows.count() >= 1, "queue table has no rows"
        print("queue rows visible:", rows.count())

        rows.first.click()
        page.wait_for_selector("#detail-content:not([hidden])")
        customer_text = page.locator("#detail-customer").inner_text()
        assert customer_text.startswith("CUST-"), f"unexpected detail customer text: {customer_text}"
        print("detail panel customer:", customer_text)

        bars = page.locator("#explanation-bars .bar-row")
        assert bars.count() == 11, f"expected 11 explanation bars, got {bars.count()}"
        print("explanation bars:", bars.count())

        page.select_option("#decision-select", "TRUE_POSITIVE")
        page.fill("#rationale-input", "verified via playwright e2e check")
        page.fill("#analyst-input", "e2e-check")
        page.click("button[type=submit]")
        page.wait_for_selector("#disposition-status.ok")
        print("disposition status:", page.locator("#disposition-status").inner_text())

        page.wait_for_timeout(300)
        rows_after = page.locator("tr.queue-row")
        print("queue rows after disposition:", rows_after.count())

        print("console errors:", console_errors)
        assert not console_errors, f"browser console errors: {console_errors}"

        browser.close()

    print("DASHBOARD VERIFICATION PASSED")


if __name__ == "__main__":
    main()
