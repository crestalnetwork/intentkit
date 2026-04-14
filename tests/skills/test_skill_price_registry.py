"""Regression tests for the global skill price registry."""

from decimal import Decimal

from intentkit.skills import base as skill_base
from intentkit.skills.base import IntentKitSkill, build_skill_prices, get_skill_price


class _DummyPricedSkill(IntentKitSkill):  # pyright: ignore[reportUnusedClass]
    """Test-only skill with a sentinel price that won't collide with real skills."""

    name: str = "_dummy_priced_skill_for_test"
    description: str = "test fixture"
    category: str = "_test"
    price: Decimal = Decimal("999.5")

    async def _arun(self, **_: object) -> str:
        return ""


def _rebuild_registry() -> None:
    """Force a clean rebuild of the global price registry."""
    skill_base._SKILL_PRICES.clear()  # pyright: ignore[reportPrivateUsage]
    skill_base._registry_built = False  # pyright: ignore[reportPrivateUsage]
    build_skill_prices()


def test_registry_is_populated():
    _rebuild_registry()
    assert len(skill_base._SKILL_PRICES) > 0, (  # pyright: ignore[reportPrivateUsage]
        "Skill price registry is empty — skills will all be charged the fallback "
        "instead of their declared prices."
    )


def test_dummy_skill_price_is_registered():
    """Proves the mechanism: a Pydantic field default becomes the registered price."""
    _rebuild_registry()
    assert get_skill_price("_dummy_priced_skill_for_test") == Decimal("999.5")


def test_real_skills_match_their_field_defaults():
    """Every registered skill's price must equal its class `price` field default."""
    _rebuild_registry()
    for cls in skill_base._collect_subclasses(IntentKitSkill):  # pyright: ignore[reportPrivateUsage]
        name = cls.model_fields["name"].default
        if not isinstance(name, str) or not name:
            continue
        expected = cls.model_fields["price"].default
        assert get_skill_price(name) == expected, (
            f"{cls.__name__}({name!r}) registered price differs from field default"
        )


def test_unknown_skill_falls_back_to_default():
    _rebuild_registry()
    assert get_skill_price("definitely_not_a_real_skill_name_xyz") == Decimal("1")
