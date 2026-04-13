from decimal import Decimal
from typing import Any


def calculate_bmi(weight_kg: Any, height_cm: Any) -> Decimal | None:
    """Compute BMI = kg / (m^2). Returns None if inputs invalid."""
    if weight_kg is None or height_cm is None:
        return None
    try:
        w = Decimal(str(weight_kg))
        h_cm = Decimal(str(height_cm))
    except Exception:
        return None
    if w <= 0 or h_cm <= 0:
        return None
    h_m = h_cm / Decimal("100")
    bmi = w / (h_m * h_m)
    return bmi.quantize(Decimal("0.01"))
