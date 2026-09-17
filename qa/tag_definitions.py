"""Declarative definitions of the tags the QA suite checks for.

Each TagSpec says: what URL identifies this tag's request, and which query
parameters must be present (and non-empty) for the tag to be considered
correctly configured. Add a new tag to check by adding a new TagSpec here —
no test code needs to change.
"""

from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class TagSpec:
    name: str
    url_substring: str
    required_params: Sequence[str]


TAGS: list[TagSpec] = [
    TagSpec(
        name="GA4",
        url_substring="google-analytics.com/g/collect",
        required_params=("tid", "en", "cid"),
    ),
    TagSpec(
        name="Meta Pixel",
        url_substring="facebook.com/tr",
        required_params=("id", "ev"),
    ),
    TagSpec(
        name="Custom Conversion Tag",
        url_substring="tracking.example.com/collect",
        required_params=("conv_id", "value"),
    ),
]
