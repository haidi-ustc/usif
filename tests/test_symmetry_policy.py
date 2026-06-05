"""Tests for explicit symmetry import policies."""

import pytest

from usif.exceptions import ValidationError
from usif.symmetry import SymmetryPolicy


def test_symmetry_policy_analyze_uses_full_atomic_when_properties_exist():
    policy = SymmetryPolicy(mode="analyze")

    try_symmetric, drop_properties = policy.resolve_atomic_properties(True, "forces")

    assert try_symmetric is False
    assert drop_properties is False


def test_symmetry_policy_reduce_rejects_implicit_property_loss():
    policy = SymmetryPolicy(mode="reduce")

    with pytest.raises(ValidationError):
        policy.resolve_atomic_properties(True, "forces/charges")


def test_symmetry_policy_reduce_can_drop_or_fallback_explicitly():
    drop_policy = SymmetryPolicy(mode="reduce", drop_atomic_properties=True)
    fallback_policy = SymmetryPolicy(mode="reduce", fallback_full_atomic=True)

    assert drop_policy.resolve_atomic_properties(True, "forces") == (True, True)
    assert fallback_policy.resolve_atomic_properties(True, "forces") == (False, False)


def test_symmetry_policy_none_disables_symmetry_attempts():
    policy = SymmetryPolicy(mode="none")

    assert policy.resolve_atomic_properties(False, "") == (False, False)
