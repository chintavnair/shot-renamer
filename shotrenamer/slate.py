"""Turn a spoken slate ("Scene 12A, Shot 3, Take 2") into numbers.

Deliberately free of ffmpeg and Whisper: this takes the text an ASR engine
produced and either finds one complete, plausible slate or returns nothing.
Keeping it pure is what makes the behaviour testable without a model.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# ASR routinely mis-hears the three keywords on a noisy set.
SCENE_WORDS = frozenset({"scene", "seen", "scenes"})
SHOT_WORDS = frozenset({"shot", "shots", "shop"})
TAKE_WORDS = frozenset({"take", "takes"})

_UNITS = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
}
_TENS = {
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
}

# Slates spell scene suffixes with a letter, often a phonetic alphabet word.
_PHONETIC = {
    "alpha": "A", "apple": "A",
    "bravo": "B", "boy": "B",
    "charlie": "C",
    "delta": "D",
    "echo": "E",
    "foxtrot": "F",
    "golf": "G",
    "hotel": "H",
    "india": "I",
    "juliett": "J", "juliet": "J",
    "kilo": "K",
    "lima": "L",
    "mike": "M",
    "november": "N",
    "oscar": "O",
    "papa": "P",
    "quebec": "Q",
    "romeo": "R",
    "sierra": "S",
    "tango": "T",
    "uniform": "U",
    "victor": "V",
    "whiskey": "W",
    "xray": "X", "x-ray": "X",
    "yankee": "Y",
    "zulu": "Z",
}

# Words a confident reader might drop between labels ("scene 12, and shot 3").
MAX_GAP = 2


@dataclass(frozen=True)
class Slate:
    scene: int
    letter: str | None
    shot: int
    take: int

    def __str__(self) -> str:
        return f"Scene{self.scene}{self.letter or ''} Shot{self.shot} Take{self.take}"

    def is_plausible(self) -> bool:
        return (
            1 <= self.scene <= 999
            and 1 <= self.shot <= 999
            and 1 <= self.take <= 99
        )


def _tokens(text: str) -> list[str]:
    """Lowercase, split glued words/numbers, drop punctuation."""
    s = text.lower()
    s = re.sub(r"(?<=\d)(?=[a-z])", " ", s)  # "12a" -> "12 a"
    s = re.sub(r"(?<=[a-z])(?=\d)", " ", s)  # "shot3" -> "shot 3"
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return s.split()


def _read_number(tokens: list[str], i: int) -> tuple[int | None, int]:
    """Read a number that may be digits, words, or spoken digit-by-digit."""
    if i >= len(tokens):
        return None, i

    if tokens[i].isdigit():
        digits = []
        j = i
        while j < len(tokens) and tokens[j].isdigit():
            digits.append(tokens[j])
            j += 1
        return int("".join(digits)), j

    values: list[int] = []
    j = i
    while j < len(tokens):
        token = tokens[j]
        if token in _UNITS:
            values.append(_UNITS[token])
        elif token in _TENS:
            values.append(_TENS[token])
        elif token == "hundred" and values:
            values.append(100)
        elif token == "thousand" and values:
            values.append(1000)
        else:
            break
        j += 1

    if not values:
        return None, i
    if len(values) > 1 and all(v < 10 for v in values):
        # "one two" is a spoken twelve, not a sum.
        return int("".join(str(v) for v in values)), j

    total = 0
    for value in values:
        if value == 100:
            total = (total or 1) * 100
        elif value == 1000:
            total = (total or 1) * 1000
        else:
            total += value
    return total, j


def _seek(tokens: list[str], i: int, words: frozenset[str]) -> int | None:
    for k in range(i, min(i + MAX_GAP + 1, len(tokens))):
        if tokens[k] in words:
            return k
    return None


def _read_letter(tokens: list[str], i: int) -> tuple[str | None, int]:
    if i < len(tokens):
        token = tokens[i]
        if len(token) == 1 and token.isalpha():
            return token.upper(), i + 1
        if token in _PHONETIC:
            return _PHONETIC[token], i + 1
    return None, i


def parse(text: str) -> Slate | None:
    """Return the first complete slate in ``text``, or ``None``."""
    tokens = _tokens(text or "")

    for i, token in enumerate(tokens):
        if token not in SCENE_WORDS:
            continue

        scene, j = _read_number(tokens, i + 1)
        if scene is None:
            continue

        letter, j = _read_letter(tokens, j)

        shot_label = _seek(tokens, j, SHOT_WORDS)
        if shot_label is None:
            continue
        shot, j = _read_number(tokens, shot_label + 1)
        if shot is None:
            continue

        take_label = _seek(tokens, j, TAKE_WORDS)
        if take_label is None:
            continue
        take, j = _read_number(tokens, take_label + 1)
        if take is None:
            continue

        slate = Slate(scene, letter, shot, take)
        if slate.is_plausible():
            return slate

    return None
