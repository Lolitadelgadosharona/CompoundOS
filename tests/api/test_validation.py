import pytest
from pydantic import ValidationError

from apps.api.schemas import HouseholdCreate


def test_household_name_is_trimmed() -> None:
    payload = HouseholdCreate(household_name="  Home  ", base_currency="USD")
    assert payload.household_name == "Home"


@pytest.mark.parametrize("currency", ["usd", "US", "USDD", "12A"])
def test_base_currency_requires_three_uppercase_letters(currency: str) -> None:
    with pytest.raises(ValidationError):
        HouseholdCreate(household_name="Home", base_currency=currency)


def test_household_text_limits_are_enforced() -> None:
    with pytest.raises(ValidationError):
        HouseholdCreate(household_name="Home", base_currency="USD", notes="x" * 8_001)
