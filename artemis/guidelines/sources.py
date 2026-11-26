"""The guideline documents the app may search, and the country each one belongs to.

A Ugandan clinic gets Ugandan guidance only (owner, 2026-11-25): no passage from another
country's guideline may reach a search. The app indexes only the registered files for its
practice country, so a file is never searched just because it sits in the guideline folder, and
every search path (the AI screening, the citations, the plan step) draws from that index alone.
The South African and WHO files were moved to `Data/Not searched - other countries/` and are not
registered. tests/test_guideline_sources.py checks that every indexed passage is Ugandan.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

PRACTICE_COUNTRY = "UG"


@dataclass(frozen=True)
class GuidelineSource:
    file: str  # the Markdown file in Data/MarkDown Files
    country: str  # ISO 3166 code
    title: str
    short: str  # how a citation names it, before the printed page


SOURCES: Dict[str, GuidelineSource] = {s.file: s for s in (
    GuidelineSource("HIV_Guidelines_ART.extraction.md", "UG",
                    "Consolidated Guidelines for the Prevention and Treatment of HIV and AIDS in Uganda, 2022 (ART)",
                    "Uganda HIV Guidelines 2022"),
    GuidelineSource("HIV_Guidelines_Co_infectionScreening.extraction.md", "UG",
                    "Consolidated Guidelines for the Prevention and Treatment of HIV and AIDS in Uganda, 2022 "
                    "(co-infections and screening)", "Uganda HIV Guidelines 2022"),
)}


def citation_name(source_path: object) -> str:
    """The guideline's name in a citation; "Guidelines" for a file outside the register."""
    source = SOURCES.get(Path(str(source_path or "")).name)
    return source.short if source else "Guidelines"


def guideline_paths(folder: Path, country: str) -> List[Path]:
    """The registered guideline files of one country that are present in the folder."""
    return sorted(Path(folder) / s.file for s in SOURCES.values()
                  if s.country == country and (Path(folder) / s.file).is_file())
