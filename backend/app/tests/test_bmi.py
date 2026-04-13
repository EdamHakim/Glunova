from decimal import Decimal

from app.utils.bmi import calculate_bmi


def test_bmi_normal() -> None:
    bmi = calculate_bmi(Decimal("70"), Decimal("175"))
    assert bmi == Decimal("22.86")


def test_bmi_none_if_missing() -> None:
    assert calculate_bmi(None, 170) is None
    assert calculate_bmi(70, None) is None
