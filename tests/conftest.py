import functools
import http.server
import threading
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

from qa.network_capture import CapturedRequest, evaluate_tag, format_report
from qa.tag_definitions import TAGS

SITE_DIR = Path(__file__).resolve().parent.parent / "site"
REPORT_PATH = Path(__file__).resolve().parent.parent / "qa-report.txt"

# Hostnames the demo page's tags fire against. We only intercept these -
# everything else (the page's own HTML/JS) is left to load normally.
TRACKING_HOSTS = ["google-analytics.com", "facebook.com", "tracking.example.com"]


@pytest.fixture(scope="session")
def demo_server():
    """Serve site/ over plain HTTP on a free local port."""
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(SITE_DIR))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    yield f"http://127.0.0.1:{port}"

    server.shutdown()
    thread.join()


@pytest.fixture(scope="session")
def tag_results(demo_server):
    """Load the demo page once in headless Chromium, capture every tracking
    request it fires, and evaluate each one against qa.tag_definitions.TAGS.

    Returns a dict of {tag_name: TagResult}, shared by all tests in the
    session so we only need a single browser pass.
    """
    captured: list[CapturedRequest] = []

    def handle_tracking_request(route):
        # Record the request, then fulfill it with a fake response instead
        # of letting Playwright actually dial out. The tag's own JS never
        # inspects the response, so a bare 204 is enough - the browser
        # thinks the pixel loaded fine, and nothing leaves the machine.
        captured.append(CapturedRequest(url=route.request.url))
        route.fulfill(status=204, body="")

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()

        for host in TRACKING_HOSTS:
            # Plain substring-style glob (not anchored to "://host/") so this
            # also matches subdomains like "www.google-analytics.com".
            page.route(f"**{host}**", handle_tracking_request)

        page.goto(demo_server)
        # The tags fire fire-and-forget pixel requests on page load; give
        # the event loop a moment to dispatch them before we inspect what
        # was captured. See README for why a fixed wait is used here.
        page.wait_for_timeout(500)

        browser.close()

    results = {tag.name: evaluate_tag(tag, captured) for tag in TAGS}

    report = format_report(results.values())
    print("\n" + report)
    REPORT_PATH.write_text(report + "\n")

    return results
