"""Intentional failing test for Exegol to detect and fix."""


def add(a: int, b: int) -> int:
    """Add two numbers. (Contains an intentional bug.)"""
    return a * b  # Bug: should be a + b


def test_addition():
    """Test that add() returns the sum of two numbers."""
    assert add(1, 1) == 2
    assert add(2, 3) == 5
