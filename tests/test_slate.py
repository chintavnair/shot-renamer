from shotrenamer.slate import Slate, parse

CASES = [
    # (transcript, expected)
    ("Scene 12, Shot 3, Take 2.", Slate(12, None, 3, 2)),
    ("SCENE 12. SHOT 3. TAKE 2.", Slate(12, None, 3, 2)),
    ("scene twelve shot three take two", Slate(12, None, 3, 2)),
    ("Scene 12A, Shot 3, Take 2", Slate(12, "A", 3, 2)),
    ("scene 12 a shot 3 take 2", Slate(12, "A", 3, 2)),
    ("scene 12 apple shot 3 take 2", Slate(12, "A", 3, 2)),
    ("scene twelve alpha shot three take two", Slate(12, "A", 3, 2)),
    ("Scene 12A Shot 3 Take 2, marker.", Slate(12, "A", 3, 2)),
    ("Roll 4, scene 7, shot 2, take 1, marker", Slate(7, None, 2, 1)),
    ("scene twelve, and shot three, take two.", Slate(12, None, 3, 2)),
    ("scene one two, shot three, take two", Slate(12, None, 3, 2)),
    ("scene ten a, shot ten, take ten", Slate(10, "A", 10, 10)),
    ("scene twenty one shot four take two", Slate(21, None, 4, 2)),
    ("scene nine hundred twelve shot three take two", Slate(912, None, 3, 2)),
    ("scene 100 shot 12 take 10", Slate(100, None, 12, 10)),
    ("seen 12 shots 3 take 2", Slate(12, None, 3, 2)),
    ("Scene 3a Shot 3 Take 1", Slate(3, "A", 3, 1)),
    ("scene12 shot3 take2", Slate(12, None, 3, 2)),
    ("... scene 5 shot 5 take 5 ...", Slate(5, None, 5, 5)),
    # First complete slate wins over a later one.
    ("scene 1 shot 2 take 3. scene 9 shot 8 take 7", Slate(1, None, 2, 3)),
]

MISSES = [
    "",
    "no slate here at all",
    "scene 12 shot 3",  # take missing
    "take 2 scene 12 shot 3",  # wrong order
    "scene 0 shot 3 take 2",  # implausible scene
    "scene 12 shot 3 take 120",  # implausible take
    "scene 12 take 2",  # shot missing
    "shot 3 take 2",  # scene missing
    "scene twelve shot three",  # still no take
]


def test_parses_expected_cases():
    for text, expected in CASES:
        assert parse(text) == expected, text


def test_rejects_incomplete_or_implausible():
    for text in MISSES:
        assert parse(text) is None, text


def test_first_valid_slate_wins_when_earlier_is_incomplete():
    assert parse("scene 12 take 2. scene 4 shot 5 take 6") == Slate(4, None, 5, 6)


def test_slate_is_plausible_range():
    assert Slate(1, None, 1, 1).is_plausible()
    assert not Slate(0, None, 1, 1).is_plausible()
    assert not Slate(1, None, 1, 100).is_plausible()
