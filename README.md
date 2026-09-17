# tag-firing-qa-suite

An automated QA suite that checks whether analytics/marketing tags fire
correctly on a page — and with the right parameters — using
[Playwright](https://playwright.dev/python/) network interception.

## What's here

```
site/                    Local demo page with a few fake tracking snippets
qa/
  tag_definitions.py      Declarative list of tags to check + their required params
  network_capture.py      Matches captured requests against tag definitions, builds the report
tests/
  conftest.py              Serves site/, runs one headless Chromium pass, captures tag requests
  test_tag_firing.py       Per-tag pass/fail assertions
.github/workflows/qa.yml  Runs the suite on every PR into main
```

### The demo page (`site/index.html`)

On load it fires three tracking pixels via `new Image().src = ...`:

1. **GA4-style** request to `google-analytics.com/g/collect` with `tid`,
   `en`, `cid` params — correctly configured.
2. **Meta Pixel-style** request to `facebook.com/tr` with `id`, `ev` params
   — correctly configured.
3. **A deliberately broken "Custom Conversion Tag"** to
   `tracking.example.com/collect` — missing its required `value` param, to
   give the suite a known failing case to catch.

These all point at **fake hostnames**, not the real Google/Meta endpoints.
That's intentional — see "Why fake domains?" below.

## Running it locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install --with-deps chromium

pytest -v
```

This starts a plain `http.server` on a free local port serving `site/`,
opens it once in headless Chromium, and prints a report like:

```
Tag Firing QA Report
========================================
[PASS] GA4
    - All required params present: tid, en, cid, dl
[PASS] Meta Pixel
    - All required params present: id, ev, dl
[FAIL] Custom Conversion Tag
    - Missing required param(s): value
```

The same report is written to `qa-report.txt` and uploaded as a CI artifact
on every run.

## How the network interception works

Playwright can register a route handler on a page:

```python
page.route("**://google-analytics.com/**", handler)
```

Every matching request the page makes — from `<img>`, `fetch`,
`sendBeacon`, XHR, anything — gets routed through `handler` **before it
ever leaves the browser process**. From there you can inspect
`route.request.url`, headers, and POST body, and then decide what actually
happens to the request: let it continue (`route.continue_()`), fake a
response (`route.fulfill(...)`), or block it (`route.abort()`).

This suite does two things in that handler:

1. Records the URL so it can be evaluated afterwards against
   `qa/tag_definitions.py` (does it fire, does it have the required query
   params).
2. Calls `route.fulfill(status=204, body="")` instead of `route.continue_()`.

### Why fake domains + `fulfill()` instead of just letting requests through?

- **No real network dependency.** The suite never actually needs
  `google-analytics.com` or `facebook.com` to be reachable, so it works
  identically offline, in CI, behind a firewall, or if those services
  change their real endpoints tomorrow.
- **Determinism.** A locked-down CI runner may have no outbound internet
  access at all (many do, for isolation/security). Faking the response
  avoids any dependency on that.
- **Speed/flakiness.** No real round-trip, no chance of a real ad-tech
  endpoint rate-limiting or timing out a CI run.

The tradeoff: this is a synthetic demo, not a test against your production
GTM/GA/Pixel setup. To point this at a real site, you'd swap
`site/index.html` for `page.goto("https://your-real-site.com")`, keep the
same `page.route()` interception, and either `route.continue_()` the
request through to the real network (if you want to test it actually works
end-to-end) or `route.abort()` it (if you just want to observe/validate
tags without letting third-party trackers actually fire, e.g. in a
staging environment).

## What "pass" means here

The three tests in `tests/test_tag_firing.py` assert:

- `test_ga4_tag_fires_with_required_params` — GA4 fires and has all
  required params. **Should pass.**
- `test_meta_pixel_tag_fires_with_required_params` — same, for Meta Pixel.
  **Should pass.**
- `test_broken_tag_is_flagged_invalid` — the broken tag *does* fire, but is
  *correctly identified* as missing its `value` param. **This test passes
  precisely because the suite catches the problem** — it's testing the
  detection logic, not asserting the broken tag is healthy. If this test
  ever fails, either someone "fixed" the demo page (and the fixture no
  longer matches) or the detection logic has a real regression.

A green CI run therefore means: two tags are firing correctly, and the
suite correctly caught the one that isn't.

## Gotchas with headless browsers in CI

- **Install OS-level dependencies, not just the browser binary.**
  `playwright install chromium` alone downloads the browser but not the
  shared libraries (fonts, GTK/NSS/etc.) it needs to actually launch on a
  bare Linux runner. Use `playwright install --with-deps chromium` (as the
  workflow here does) or you'll see launch errors like "missing shared
  libraries" that don't reproduce on a dev machine with a full desktop
  environment already installed.
- **No display server.** `playwright.chromium.launch()` defaults to
  headless, which is why this works on CI without a virtual framebuffer
  (Xvfb) — don't pass `headless=False` unless you've also set one up.
- **Sandboxing in containers.** Some containerized CI environments (and
  some `act`/Docker-based local runners) don't allow Chromium's sandbox to
  initialize. If you hit a sandbox-related launch failure in such an
  environment, the usual fix is launching with
  `chromium.launch(args=["--no-sandbox"])` — but only do this in CI/sandboxed
  containers you trust, not for browsing untrusted content.
- **Fire-and-forget requests need a moment.** Tracking pixels (`new
  Image().src = ...`, `navigator.sendBeacon`) don't block page load, so a
  request can still be in flight right after `page.goto()` returns. This
  suite uses a fixed `page.wait_for_timeout(500)` to give them a moment to
  fire. That's simple but technically a fixed sleep — for a larger suite,
  prefer waiting on a specific signal (e.g.
  `page.wait_for_request(url_pattern)` per tag) so it's not relying on a
  timing guess. It scales less well if you're checking many tags, since
  a slow CI runner could in theory still race ahead of a very sluggish tag script.
- **CI runners are slower than your laptop.** If you see intermittent
  timeouts in CI that don't reproduce locally, increase Playwright's
  default timeouts rather than assuming the test logic is wrong.
