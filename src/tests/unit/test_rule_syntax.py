import re

import pytest

from src.services.rule_syntax import allowed_values, format_allowed_values, portable_pattern

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(("pattern", "matches", "misses"), [
    (r"\d+", "123", "１２３"), (r"\w+", "A_z9", "café"),
    (r"\s+", " \t\n", "\u00a0"), (r"\D+", "abc", "123"),
    (r"\W+", "!@", "abc"), (r"\S+", "abc", " \t"),
    (r"[\dA-F]+", "A12F", "G"), (r"[a\-z]+", "a-z", "m"),
    (r"(?:ab|cd){2,3}", "abcdab", "ab"), (r"a.b", "a\rb", "a\nb"),
    (r"\[x\]\{2\}", "[x]{2}", "xx"),
])
def test_portable_regex_matching(pattern: str, matches: str, misses: str) -> None:
    compiled = re.compile(portable_pattern(pattern), re.ASCII)
    assert compiled.fullmatch(matches)
    assert compiled.fullmatch(misses) is None


@pytest.mark.parametrize("pattern", [
    "", "é", "a" * 201, "\\", r"\bword", r"\1", r"\u1234", r"[\D]",
    "[]", "[^]", "[abc", "[a[b]]", "[a&&b]", "[a~~b]", "[a--b]", "[a||b]",
    "]", "}", "a{", "a{,2}", "a{1000001}", "a{3,2}", "a{2}+", "a*+", "a++",
    "a?+", "(?i)a", "(?=a)", "(?<=a)b", "(?P<x>a)", "(", "*a",
])
def test_nonportable_or_invalid_regex_is_rejected(pattern: str) -> None:
    with pytest.raises(ValueError):
        portable_pattern(pattern)


def test_regex_length_limit_is_inclusive() -> None:
    assert portable_pattern("a" * 200) == "a" * 200


@pytest.mark.parametrize(("text", "expected"), [
    ("open, closed", ["open", "closed"]),
    ('"a,b", "say ""hello"""', ["a,b", 'say "hello"']),
    (' " padded " , plain ', [" padded ", "plain"]),
    ('"line\nbreak", café', ["line\nbreak", "café"]),
    ("A, a", ["A", "a"]),
])
def test_allowed_values_preserve_exact_values(text: str, expected: list[str]) -> None:
    assert allowed_values(text) == expected
    assert allowed_values(format_allowed_values(expected)) == expected


@pytest.mark.parametrize("text", ["", " ", ",a", "a,", "a,,b", "a,a", "a, a", '""',
                                         '" "', '"unclosed', '"a" tail', 'a"b', '"a","a"'])
def test_malformed_allowed_values_are_rejected(text: str) -> None:
    with pytest.raises(ValueError):
        allowed_values(text)
