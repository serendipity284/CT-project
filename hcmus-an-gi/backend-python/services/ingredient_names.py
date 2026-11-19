"""Shared Vietnamese ingredient vocabulary for menus, inference and search."""
import json
import unicodedata


# Prefer labels already used in dishes. Only group names for the same food.
_GROUPS = {
    "thịt heo": ("thịt lợn", "pork"),
    "thịt bò": ("beef",),
    "thịt gà": ("gà", "chicken"),
    "lạc": ("đậu phộng", "đậu phụng", "peanut", "peanuts"),
    "dưa chuột": ("dưa leo", "cucumber"),
    "rau mùi": ("ngò", "ngò rí", "rau ngò rí", "cilantro", "coriander leaves"),
    "hành lá": ("hành hoa", "scallion", "green onion"),
    "mè": ("vừng", "hạt vừng", "hạt mè", "sesame seeds"),
    "đậu phụ": ("đậu hũ", "đậu khuôn", "tofu"),
    "chả lụa": ("giò lụa",),
    "giò heo": ("chân giò heo", "chân giò lợn",),
    "pate": ("pâté", "pa tê", "pa-tê",),
    "ngô": ("bắp", "corn", "maize"),
    "dứa": ("trái thơm", "quả dứa", "pineapple"),
    "mộc nhĩ": ("nấm mèo",),
    "xà lách": ("rau xà lách", "lettuce"),
    "cà chua": ("tomato", "tomatoes"),
    "bột ngọt": ("mì chính",),
    "nước tương": ("xì dầu",),
}
_ALIASES = {alias: name for name, aliases in _GROUPS.items() for alias in aliases}


def normalize_ingredient(value: str) -> str:
    name = unicodedata.normalize("NFC", " ".join(value.casefold().split()))
    return _ALIASES.get(name, name)


def canonical_ingredients(values: list[str], catalog: dict[str, str] | None = None) -> list[str]:
    names = (normalize_ingredient(value) for value in values)
    if catalog:
        names = (catalog.get(name, name) for name in names)
    return list(dict.fromkeys(name for name in names if name))


def stored_vocabulary(conn) -> list[str]:
    """Read unique stored labels for Gemini to reuse for additional synonyms."""
    with conn.cursor() as cur:
        cur.execute("SELECT DISTINCT ingredients FROM dishes WHERE ingredients IS NOT NULL")
        names = set()
        for (raw,) in cur:
            values = json.loads(raw) if isinstance(raw, (str, bytes, bytearray)) else raw
            if isinstance(values, list):
                names.update(canonical_ingredients(values))
    return sorted(names)


def normalize_existing_dishes(conn) -> int:
    """Normalize existing lists atomically, retaining ingredient order."""
    from services.ingredient_catalog import resolve_names

    mapping = resolve_names(stored_vocabulary(conn))
    changed = 0
    with conn.cursor() as cur:
        cur.execute("SELECT id, ingredients FROM dishes WHERE ingredients IS NOT NULL FOR UPDATE")
        for dish_id, raw in cur.fetchall():
            values = json.loads(raw) if isinstance(raw, (str, bytes, bytearray)) else raw
            if not isinstance(values, list):
                continue
            normalized = canonical_ingredients(values, mapping)
            if normalized != values:
                cur.execute("UPDATE dishes SET ingredients = %s WHERE id = %s",
                            (json.dumps(normalized, ensure_ascii=False), dish_id))
                changed += 1
    conn.commit()
    return changed


if __name__ == "__main__":
    import mysql.connector
    from app import MYSQL

    with mysql.connector.connect(**MYSQL) as conn:
        print(f"Updated dishes: {normalize_existing_dishes(conn)}")
