"""Reading medicines the way they were written, so the rules see the drugs.

A regimen may be stored as clean codes (["TDF", "3TC", "DTG"]), as one sentence ("TDF/3TC/DTG
(TLD) fixed-dose combination once daily"), or split badly (["TDF", " 3TC", " EFV"]).
`regimen_codes` finds the antiretroviral drugs in any of these, by code, by name, or by a
common combination's short name (TLD, TLE).
"""

from __future__ import annotations

import re
from typing import Dict, Iterable, List

# Antiretroviral codes, and the names and spellings that mean each one.
_ARV_NAMES: Dict[str, List[str]] = {
    "TDF": ["tdf", "tenofovir disoproxil", "tenofovir"],
    "TAF": ["taf", "tenofovir alafenamide"],
    "3TC": ["3tc", "lamivudine"],
    "FTC": ["ftc", "emtricitabine"],
    "DTG": ["dtg", "dolutegravir"],
    "EFV": ["efv", "efavirenz"],
    "NVP": ["nvp", "nevirapine"],
    "AZT": ["azt", "zdv", "zidovudine"],
    "ABC": ["abc", "abacavir"],
    "ATV/r": ["atv/r", "atv", "atazanavir"],
    "LPV/r": ["lpv/r", "lpv", "lopinavir"],
    "DRV/r": ["drv/r", "drv", "darunavir"],
    "RAL": ["ral", "raltegravir"],
    "d4T": ["d4t", "stavudine"],
}
# Fixed-dose combinations, by their usual short names.
COMBINATIONS: Dict[str, List[str]] = {
    "TLD": ["TDF", "3TC", "DTG"],
    "TLE": ["TDF", "3TC", "EFV"],
    "TEE": ["TDF", "FTC", "EFV"],
    "ALD": ["ABC", "3TC", "DTG"],
}
# What the add-case form offers: combinations first, then single drugs.
REGIMEN_CHOICES: List[str] = list(COMBINATIONS) + list(_ARV_NAMES)

NSAIDS = [
    "ibuprofen",
    "diclofenac",
    "naproxen",
    "meloxicam",
    "indomethacin",
    "piroxicam",
    "ketoprofen",
    "celecoxib",
    "nsaid",
]

# Text that means "no medicine" rather than naming one.
_NONE_WORDS = re.compile(r"^\s*(none|nil|no|n/a|na|-)\b", re.IGNORECASE)


def _patterns() -> List[tuple]:
    pairs = []
    for code, names in _ARV_NAMES.items():
        for name in names:
            pairs.append((name, code))
    for short, codes in COMBINATIONS.items():
        pairs.append((short.lower(), short))
    # Longer names first, so "tenofovir alafenamide" wins over "tenofovir".
    return sorted(pairs, key=lambda p: -len(p[0]))


_PATTERNS = _patterns()


def regimen_codes(items: Iterable[str]) -> List[str]:
    """The antiretroviral codes named in the regimen, in the order written, without repeats."""
    text = " ; ".join(str(i) for i in items or [])
    found: List[tuple] = []  # (position, code)
    taken = [False] * len(text)
    low = text.lower()
    for name, code in _PATTERNS:
        for m in re.finditer(rf"(?<![a-z0-9]){re.escape(name)}(?![a-z0-9])", low):
            if any(taken[m.start():m.end()]):
                continue
            for i in range(m.start(), m.end()):
                taken[i] = True
            found.append((m.start(), code))
    out: List[str] = []
    for _, code in sorted(found):
        for c in COMBINATIONS.get(code, [code]):
            if c not in out:
                out.append(c)
    return out


def other_medicines(items: Iterable[str]) -> List[str]:
    """The medicine list without entries that only say there are none ("None", "Nil")."""
    return [s.strip() for s in items or [] if s and s.strip() and not _NONE_WORDS.match(s)]
