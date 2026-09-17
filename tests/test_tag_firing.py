"""Per-tag pass/fail checks.

tag_results (see conftest.py) does the actual browsing + capture once per
session; each test below just asserts on the resulting TagResult, so pytest
reports a clear individual PASS/FAIL line per tag.
"""


def test_ga4_tag_fires_with_required_params(tag_results):
    result = tag_results["GA4"]
    assert result.fired, "GA4 tag never fired a request"
    assert not result.missing_params, f"GA4 tag is missing required param(s): {result.missing_params}"


def test_meta_pixel_tag_fires_with_required_params(tag_results):
    result = tag_results["Meta Pixel"]
    assert result.fired, "Meta Pixel tag never fired a request"
    assert not result.missing_params, f"Meta Pixel tag is missing required param(s): {result.missing_params}"


def test_broken_tag_is_flagged_invalid(tag_results):
    """The demo page ships one deliberately misconfigured tag. This test
    passes when the suite correctly detects it as invalid - if it starts
    failing, either the demo page or the detection logic has regressed."""
    result = tag_results["Custom Conversion Tag"]
    assert result.fired, "Broken tag should still fire a request, just an invalid one"
    assert "value" in result.missing_params, (
        "Expected the broken tag to be missing its 'value' param, "
        f"but missing params were: {result.missing_params}"
    )
    assert not result.passed, "QA suite failed to flag the broken tag as invalid"
