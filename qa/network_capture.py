"""Helpers for matching captured network requests against TagSpecs and
producing a human-readable pass/fail report."""

from dataclasses import dataclass
from typing import Iterable
from urllib.parse import parse_qsl, urlparse

from qa.tag_definitions import TagSpec


@dataclass
class CapturedRequest:
    url: str


@dataclass
class TagResult:
    name: str
    fired: bool
    params: dict
    missing_params: list

    @property
    def passed(self) -> bool:
        return self.fired and not self.missing_params


def parse_request_params(url: str) -> dict:
    return dict(parse_qsl(urlparse(url).query))


def evaluate_tag(tag_spec: TagSpec, captured_requests: Iterable[CapturedRequest]) -> TagResult:
    match = next((r for r in captured_requests if tag_spec.url_substring in r.url), None)

    if match is None:
        return TagResult(
            name=tag_spec.name,
            fired=False,
            params={},
            missing_params=list(tag_spec.required_params),
        )

    params = parse_request_params(match.url)
    missing = [p for p in tag_spec.required_params if not params.get(p)]
    return TagResult(name=tag_spec.name, fired=True, params=params, missing_params=missing)


def format_report(results: Iterable[TagResult]) -> str:
    lines = ["Tag Firing QA Report", "=" * 40]
    for r in results:
        status = "PASS" if r.passed else "FAIL"
        lines.append(f"[{status}] {r.name}")
        if not r.fired:
            lines.append("    - Tag did not fire any matching request")
        elif r.missing_params:
            lines.append(f"    - Missing required param(s): {', '.join(r.missing_params)}")
        else:
            lines.append(f"    - All required params present: {', '.join(r.params.keys())}")
    return "\n".join(lines)
