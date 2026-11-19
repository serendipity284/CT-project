"""Infer a common ingredient list for a dish and persist it to ``dishes``.

The result represents a typical recipe for the dish, not a particular restaurant's
actual recipe. Ingredient names use Vietnamese labels with diacritics.
"""
from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from services.ingredient_names import normalize_ingredient, canonical_ingredients
from services.ingredient_catalog import resolve_names

ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(ENV_PATH, override=True)
logger = logging.getLogger(__name__)


class IngredientResponse(BaseModel):
    ingredients: list[str] = Field(default_factory=list)


# Explicitly exclude seasoning and cooking staples. Keep the list conservative:
# sauces/soups that define a dish are not removed merely because they are liquid.
_SEASONINGS = {
    "muối", "đường", "tiêu", "hạt tiêu", "tiêu đen", "tiêu trắng", "bột ớt",
    "ớt bột", "ớt khô", "tương ớt", "nước mắm", "nước tương", "xì dầu",
    "dầu hào", "giấm", "dấm", "dầu ăn", "dầu thực vật", "dầu mè", "dầu vừng",
    "bột ngọt", "mì chính", "hạt nêm", "bột nêm", "ngũ vị hương", "tỏi",
    "hành tím", "gừng", "sả", "mỡ hành",
    "salt", "sugar", "pepper", "black pepper", "white pepper", "chili powder",
    "chili flakes", "chili sauce", "fish sauce", "soy sauce", "oyster sauce",
    "vinegar", "cooking oil", "vegetable oil", "sesame oil", "msg",
    "monosodium glutamate", "seasoning powder", "five spice powder",
    "garlic", "shallot", "ginger", "lemongrass", "scallion oil",
}

def _clean_ingredients(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for raw in values:
        value = re.sub(r"\s+", " ", str(raw)).strip(" .,-\t\n")
        if not value or len(value) > 80:
            continue
        key = normalize_ingredient(value)
        if key in _SEASONINGS or key in seen:
            continue
        seen.add(key)
        result.append(key)
    return result[:40]


def infer_ingredients(dish_name: str) -> list[str]:
    """Ask Gemini for typical non-seasoning ingredients; fail closed on errors."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured")

    model = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
    client = genai.Client(api_key=api_key)
    prompt = f"""Identify the common, recognizable food ingredients of the Vietnamese dish named below.
Use the common/traditional recipe, not a specific restaurant menu. The restaurant's
actual recipe may differ, so return only ingredients that commonly define the dish.
Write every ingredient name in concise lowercase Vietnamese with full diacritics.
Use one name per ingredient, without translations or aliases in parentheses.
Follow the database vocabulary, e.g. "thịt heo" for pork and "lạc" for peanuts.
Include the main food components and common toppings.
Exclude seasonings, spices, cooking oils, aromatics used only for seasoning, and
condiments. Do not invent optional ingredients. If the name is too ambiguous, return
an empty list. Output JSON matching {{"ingredients": ["..."]}} only.

Dish: {dish_name.strip()}
"""
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=IngredientResponse,
            temperature=0.1,
        ),
    )
    if not response.text:
        raise ValueError("Gemini returned an empty ingredient response")
    parsed = IngredientResponse.model_validate_json(response.text)
    return _clean_ingredients(parsed.ingredients)


def analyze_dish(conn: Any, dish_id: int, dish_name: str, *, force: bool = False) -> dict[str, Any]:
    """Infer and persist ingredients, preserving existing user-provided values."""
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("SELECT ingredients FROM dishes WHERE id = %s", (dish_id,))
        row = cur.fetchone()
        if not row:
            return {"dish_id": dish_id, "status": "not_found"}
        raw = row.get("ingredients")
        if isinstance(raw, (bytes, bytearray)):
            raw = raw.decode("utf-8")
        try:
            existing = json.loads(raw) if isinstance(raw, str) else raw
        except (TypeError, ValueError):
            existing = []
        if existing and not force:
            return {"dish_id": dish_id, "status": "already_has_ingredients"}

        ingredients = infer_ingredients(dish_name)
        # Empty output means unknown; do not mark it complete, allowing a later retry.
        if not ingredients:
            return {"dish_id": dish_id, "status": "no_confident_result", "ingredients": []}
        ingredients = canonical_ingredients(ingredients, resolve_names(ingredients))
        condition = "" if force else " AND (ingredients IS NULL OR JSON_LENGTH(ingredients) = 0)"
        cur.execute(
            "UPDATE dishes SET ingredients = %s WHERE id = %s" + condition,
            (json.dumps(ingredients, ensure_ascii=False), dish_id),
        )
        conn.commit()
        if not cur.rowcount and not force:
            return {"dish_id": dish_id, "status": "already_has_ingredients"}
        return {"dish_id": dish_id, "status": "analyzed", "ingredients": ingredients}
    finally:
        cur.close()


def analyze_dishes_background(dish_ids: list[int]) -> None:
    """Background task entry point; each dish gets an isolated DB connection."""
    # Import lazily to avoid a circular import while app.py imports this module.
    from app import MYSQL
    import mysql.connector

    for dish_id in dish_ids:
        conn = None
        try:
            conn = mysql.connector.connect(**MYSQL)
            cur = conn.cursor(dictionary=True)
            cur.execute("SELECT name FROM dishes WHERE id = %s", (dish_id,))
            row = cur.fetchone()
            cur.close()
            if row:
                analyze_dish(conn, dish_id, row["name"])
        except Exception:
            logger.exception("Automatic ingredient analysis failed for dish_id=%s", dish_id)
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    pass
        finally:
            if conn:
                conn.close()


def analyze_missing_batch(limit: int = 20) -> list[dict[str, Any]]:
    """Backfill a bounded batch of dishes whose ingredient JSON is empty."""
    from app import MYSQL
    import mysql.connector

    conn = mysql.connector.connect(**MYSQL)
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            "SELECT id, name FROM dishes WHERE ingredients IS NULL OR ingredients = JSON_ARRAY() "
            "ORDER BY id LIMIT %s",
            (limit,),
        )
        rows = cur.fetchall()
        cur.close()
        results = []
        for row in rows:
            try:
                results.append(analyze_dish(conn, row["id"], row["name"]))
            except Exception as exc:
                logger.exception("Ingredient backfill failed for dish_id=%s", row["id"])
                results.append({"dish_id": row["id"], "status": "error", "detail": str(exc)[:240]})
        return results
    finally:
        conn.close()
