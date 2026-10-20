import pytest

from tasks.second_largest_distinct.solution import second_largest


def test_returns_second_largest_distinct_value():
    assert second_largest([2, 5, 3, 5]) == 3


def test_handles_negative_values():
    assert second_largest([-8, -2, -5]) == -5


def test_requires_two_distinct_values():
    with pytest.raises(ValueError):
        second_largest([4, 4, 4])
