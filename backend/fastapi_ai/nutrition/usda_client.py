"""
USDA FoodData Central validation layer.

Endpoint : https://api.nal.usda.gov/fdc/v1/foods/search
API key  : optional — get one free at https://fdc.nal.usda.gov/api-key-signup.html
           DEMO_KEY = 30 req/min; real key = 1 000 req/min.

Rate-limit strategy
-------------------
A 7-day meal plan fires ~112–140 USDA queries.  With DEMO_KEY (30 req/min) the
API starts returning 429s after the first ~30 calls, silently turning every
remaining ingredient into "not found".  We handle this with two mechanisms:

1. Module-level ingredient cache  — the same ingredient name (e.g. "chicken
   breast") recurring across multiple days hits USDA only once per process
   lifetime.  This alone typically cuts unique queries by 40–60 %.

2. Per-request throttle  — a configurable sleep between uncached requests.
   Default: 2.1 s (≈ 28 req/min, safely under the 30 req/min DEMO_KEY cap).
   Set USDA_REQUEST_DELAY=0.1 in .env when you have a real API key.
"""
import os
import re
import time
import requests
from typing import Optional

USDA_BASE    = "https://api.nal.usda.gov/fdc/v1"
USDA_API_KEY = os.environ.get("USDA_API_KEY", "DEMO_KEY")

# Seconds to sleep between uncached USDA requests.
# 2.1 s → ~28 req/min (safe under DEMO_KEY 30/min cap).
# Set to 0.1 with a real API key for fast lookups.
_DELAY = float(os.environ.get("USDA_REQUEST_DELAY", "2.1" if USDA_API_KEY == "DEMO_KEY" else "0.1"))

# Module-level cache: ingredient name → USDA food entry (or None if not found).
# Survives for the lifetime of the FastAPI process, eliminating duplicate calls
# for the same ingredient appearing across multiple days of the same plan.
_cache: dict[str, Optional[dict]] = {}

# Ingredient unit strings → approximate grams
UNIT_TO_GRAMS: dict[str, float] = {
    "g": 1,        "gram": 1,        "grams": 1,
    "kg": 1000,    "kilogram": 1000, "kilograms": 1000,
    "oz": 28.35,   "ounce": 28.35,   "ounces": 28.35,
    "lb": 453.6,   "pound": 453.6,   "pounds": 453.6,
    "cup": 240,    "cups": 240,
    "tbsp": 15,    "tablespoon": 15,  "tablespoons": 15,
    "tsp": 5,      "teaspoon": 5,     "teaspoons": 5,
    "ml": 1,       "l": 1000,
    "slice": 30,   "slices": 30,
    "piece": 50,   "pieces": 50,
    "handful": 30,
}

# USDA nutrient IDs we care about
NUTRIENT_IDS: dict[str, int] = {
    "calories_kcal": 1008,   # Energy
    "carbs_g":       1005,   # Carbohydrate, by difference
    "protein_g":     1003,   # Protein
    "fat_g":         1004,   # Total lipid (fat)
    "sugar_g":       2000,   # Sugars, total including NLEA
}
_ID_TO_KEY = {v: k for k, v in NUTRIENT_IDS.items()}


def parse_quantity_grams(ingredient_str: str) -> tuple[float, str]:
    """
    "150g salmon"   → (150.0, "salmon")
    "1 cup quinoa"  → (240.0, "quinoa")
    "2 tbsp olive oil" → (30.0, "olive oil")
    Falls back to (100.0, full_string) when format is unrecognised.
    """
    pattern = r"^([\d.]+)\s*([a-zA-Z]+)\s+(.+)$"
    m = re.match(pattern, ingredient_str.strip())
    if m:
        qty_str, unit, name = m.group(1), m.group(2).lower(), m.group(3)
        grams_per_unit = UNIT_TO_GRAMS.get(unit)
        if grams_per_unit:
            return float(qty_str) * grams_per_unit, name
    return 100.0, ingredient_str


def search_food(query: str) -> Optional[dict]:
    """
    Return the best-match USDA food entry or None on any error.
    Results are cached by query string; uncached calls are throttled
    to respect the DEMO_KEY 30 req/min rate limit.
    """
    key = query.lower().strip()
    if key in _cache:
        return _cache[key]

    # Throttle before every real network request
    time.sleep(_DELAY)

    params = {
        "query":    query,
        "dataType": ["SR Legacy", "Foundation", "Branded"],
        "pageSize": 1,
        "api_key":  USDA_API_KEY,
    }
    try:
        r = requests.get(f"{USDA_BASE}/foods/search", params=params, timeout=10)
        r.raise_for_status()
        foods = r.json().get("foods", [])
        result = foods[0] if foods else None
    except Exception:
        result = None

    _cache[key] = result
    return result


def _extract_nutrients_per_100g(food: dict) -> dict[str, float]:
    result = {k: 0.0 for k in NUTRIENT_IDS}
    for n in food.get("foodNutrients", []):
        nid = n.get("nutrientId") or (n.get("nutrient") or {}).get("id")
        if nid in _ID_TO_KEY:
            result[_ID_TO_KEY[nid]] = float(n.get("value") or 0)
    return result


def validate_meal_macros(ingredients: list[str]) -> dict:
    """
    Look up every ingredient in USDA FoodData Central, scale by quantity,
    and return summed meal macros alongside a per-ingredient breakdown.

    Return schema:
    {
      "source":        "usda_validated" | "llm_estimated",
      "calories_kcal": float,
      "carbs_g":       float,
      "protein_g":     float,
      "fat_g":         float,
      "sugar_g":       float,
      "breakdown": [
        {
          "ingredient":   str,
          "grams":        float,
          "usda_name":    str | None,
          "usda_fdc_id":  int | None,
          "calories_kcal": float,   # only when found
          "carbs_g":       float,
          "protein_g":     float,
          "fat_g":         float,
          "sugar_g":       float,
          "note":          str,     # only when not found
        }
      ]
    }
    """
    totals: dict[str, float] = {k: 0.0 for k in NUTRIENT_IDS}
    breakdown: list[dict]    = []
    any_found = False

    for ing_str in ingredients:
        grams, name = parse_quantity_grams(ing_str)
        food = search_food(name)

        if food:
            per_100g = _extract_nutrients_per_100g(food)
            scale    = grams / 100.0
            scaled   = {k: round(v * scale, 2) for k, v in per_100g.items()}
            for k in totals:
                totals[k] += scaled[k]
            breakdown.append({
                "ingredient":  ing_str,
                "grams":       grams,
                "usda_name":   food.get("description", name),
                "usda_fdc_id": food.get("fdcId"),
                **scaled,
            })
            any_found = True
        else:
            breakdown.append({
                "ingredient": ing_str,
                "grams":      grams,
                "usda_name":  None,
                "note":       "not found in USDA",
            })

    return {
        "source": "usda_validated" if any_found else "llm_estimated",
        **{k: round(v, 1) for k, v in totals.items()},
        "breakdown": breakdown,
    }
