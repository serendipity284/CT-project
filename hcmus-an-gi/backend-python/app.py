"""
HCMUS An Gi — FastAPI + MySQL
Chay: uvicorn app:app --reload --port 8000
"""

from __future__ import annotations

import httpx
import unicodedata
import math
import os
import re
import uuid
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from typing import Any, Optional
from pathlib import Path

import mysql.connector
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, Header, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from jose import JWTError, jwt
import bcrypt
from pydantic import BaseModel, EmailStr, Field

import io
from fastapi.staticfiles import StaticFiles
from PIL import Image, ImageOps

from menu_scan import scan_menu_images
from starlette.concurrency import run_in_threadpool
from rate_limit import (
    check_contribute_allowed,
    queue_enter,
    queue_leave,
    queue_stats,
    record_contribute,
)

ENV_PATH = Path(__file__).resolve().parent / ".env"
load_dotenv(ENV_PATH, override=True)

from auth_deps import current_user, verified_user
from input_understanding.extractor import extract_intent
from input_understanding.validator import validate_intent
from input_understanding.context import UNLIMITED_PATTERNS, merge_context, merge_limits
from input_understanding.normalizer import normalize_budget, normalize_budget_text
from input_understanding.food import slugify_food, extract_search_keywords, fallback_extract_food

import firebase_admin
from firebase_admin import credentials, auth as fb_auth

_sa = (os.getenv("FIREBASE_SERVICE_ACCOUNT") or "").strip().strip('"').strip("'")
if not firebase_admin._apps:
    if not _sa:
        raise RuntimeError("Khong doc duoc FIREBASE_SERVICE_ACCOUNT tu .env (kiem tra ten bien, file .env co luu chua)")
    _sa_path = Path(_sa)
    if not _sa_path.is_absolute():
        _sa_path = Path(__file__).resolve().parent / _sa_path   # tinh theo thu muc cua app.py
    if not _sa_path.exists():
        raise RuntimeError(f"Khong thay file Firebase JSON tai: {_sa_path}")
    firebase_admin.initialize_app(credentials.Certificate(str(_sa_path)))


load_dotenv()

MYSQL = {
    "host": os.getenv("MYSQL_HOST", "127.0.0.1"),
    "port": int(os.getenv("MYSQL_PORT", "3306")),
    "user": os.getenv("MYSQL_USER", "root"),
    "password": os.getenv("MYSQL_PASSWORD", ""),
    "database": os.getenv("MYSQL_DATABASE", "hcmus_an_gi"),
}
JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-change-me")
def hash_password(password: str) -> str:
    pwd_bytes = password.encode("utf-8")[:72]
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        pwd_bytes = plain_password.encode("utf-8")[:72]
        return bcrypt.checkpw(pwd_bytes, hashed_password.encode("utf-8"))
    except Exception:
        return False

app = FastAPI(title="HCMUS An Gi API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
from routers.heana import router as heana_router
app.include_router(heana_router, prefix="/api/heana")

# ---------------------------------------------------------------- avatar
UPLOAD_DIR = Path(__file__).resolve().parent / "uploads"
AVATAR_DIR = UPLOAD_DIR / "avatars"
AVATAR_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")


@app.on_event("startup")
def ensure_avatar_column():
    """Tự thêm cột users.avatar_url nếu DB cũ chưa có."""
    try:
        conn = mysql.connector.connect(**MYSQL)
    except mysql.connector.Error:
        return
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT COUNT(*) FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA=%s AND TABLE_NAME='users' AND COLUMN_NAME='avatar_url'",
            (MYSQL["database"],),
        )
        if cur.fetchone()[0] == 0:
            cur.execute("ALTER TABLE users ADD COLUMN avatar_url VARCHAR(500) NULL AFTER name")
            conn.commit()
    finally:
        cur.close()
        conn.close()


def _public_user(row: dict) -> dict:
    return {
        "id": row["id"],
        "email": row["email"],
        "name": row["name"],
        "avatar_url": row.get("avatar_url"),
    }


def _save_avatar_file(raw: bytes, user_id: str) -> str:
    """Mở lại bằng Pillow (chặn file giả ảnh), cắt vuông 256x256, lưu JPEG."""
    img = Image.open(io.BytesIO(raw))
    img = ImageOps.exif_transpose(img).convert("RGB")
    img = ImageOps.fit(img, (256, 256), Image.LANCZOS)
    name = f"{user_id}_{int(time.time())}.jpg"
    img.save(AVATAR_DIR / name, "JPEG", quality=88)
    return f"/uploads/avatars/{name}"


def _delete_avatar_file(url: Optional[str]):
    if url and url.startswith("/uploads/avatars/"):
        try:
            (AVATAR_DIR / Path(url).name).unlink(missing_ok=True)
        except OSError:
            pass


@app.get("/users/me")
def get_me(user: dict = Depends(current_user)):
    conn = get_conn()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("SELECT id, email, name, avatar_url FROM users WHERE id=%s", (user["id"],))
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "Khong tim thay tai khoan")
        return _public_user(row)
    finally:
        cur.close()
        conn.close()


@app.post("/users/me/avatar")
async def upload_avatar(file: UploadFile = File(...), user: dict = Depends(current_user)):
    if not (file.content_type or "").startswith("image/"):
        raise HTTPException(400, "Chi nhan file anh")
    raw = await file.read()
    if not raw:
        raise HTTPException(400, "File anh rong")
    if len(raw) > 5 * 1024 * 1024:
        raise HTTPException(400, "Anh toi da 5MB")
    try:
        new_url = await run_in_threadpool(_save_avatar_file, raw, user["id"])
    except Exception:
        raise HTTPException(400, "Khong doc duoc file anh (jpeg/png/webp)")

    conn = get_conn()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("SELECT avatar_url FROM users WHERE id=%s", (user["id"],))
        old = (cur.fetchone() or {}).get("avatar_url")
        cur.execute("UPDATE users SET avatar_url=%s WHERE id=%s", (new_url, user["id"]))
        conn.commit()
        cur.execute("SELECT id, email, name, avatar_url FROM users WHERE id=%s", (user["id"],))
        row = cur.fetchone()
    finally:
        cur.close()
        conn.close()
    _delete_avatar_file(old)
    return {"ok": True, "user": _public_user(row)}


@app.delete("/users/me/avatar")
def reset_avatar(user: dict = Depends(current_user)):
    """Về avatar mặc định."""
    conn = get_conn()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("SELECT avatar_url FROM users WHERE id=%s", (user["id"],))
        old = (cur.fetchone() or {}).get("avatar_url")
        cur.execute("UPDATE users SET avatar_url=NULL WHERE id=%s", (user["id"],))
        conn.commit()
        cur.execute("SELECT id, email, name, avatar_url FROM users WHERE id=%s", (user["id"],))
        row = cur.fetchone()
    finally:
        cur.close()
        conn.close()
    _delete_avatar_file(old)
    return {"ok": True, "user": _public_user(row)}

# ---------------------------------------------------------------- dinh vi dia chi
GEO_UA = "hcmus-an-gi/1.0 (student project)"


def _nominatim(q: str):
    url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode(
        {
            "format": "jsonv2",
            "limit": 1,
            "countrycodes": "vn",
            "q": q,
            "viewbox": "106.3,11.2,107.1,10.3",
            "bounded": 0,
        }
    )
    req = urllib.request.Request(url, headers={"User-Agent": GEO_UA, "Accept-Language": "vi"})
    with urllib.request.urlopen(req, timeout=8) as r:
        data = json.loads(r.read().decode("utf-8"))
    if data:
        return float(data[0]["lat"]), float(data[0]["lon"])
    return None


def geocode_address(address: str):
    """Dia chi -> (lat, lng, approx). Thu day du truoc, rut gon dan neu khong tim thay.
    approx=True nghia la phai bo bot chi tiet (vd so nha/hem) nen vi tri chi gan dung.
    Tra ve None neu khong tim duoc; raise HTTPException 503 neu khong goi duoc dich vu."""
    base = " ".join(address.split())
    low = base.lower()
    has_city = any(k in low for k in ("hồ chí minh", "ho chi minh", "hcm", "tphcm", "sài gòn", "sai gon"))
    suffix = "" if has_city else ", Thành phố Hồ Chí Minh"

    cleaned = re.sub(r"\b(\d+)[A-Za-z]?(?:\s*[/\\]\s*\d+[A-Za-z]?)+", r"\1", base)
    parts = [x.strip() for x in cleaned.split(",") if x.strip()]
    tries: list[tuple[str, bool]] = [(base + suffix, False)]
    if cleaned != base:
        tries.append((cleaned + suffix, True))
    for i in (1, 2):
        if len(parts) > i:
            tries.append((", ".join(parts[i:]) + suffix, True))

    seen, uniq = set(), []
    for q, approx in tries:
        if q not in seen:
            seen.add(q)
            uniq.append((q, approx))

    net_errors = 0
    for i, (q, approx) in enumerate(uniq[:5]):
        if i:
            time.sleep(1.1)  # Nominatim: toi da 1 request/giay
        try:
            got = _nominatim(q)
        except (urllib.error.URLError, TimeoutError, ValueError):
            net_errors += 1
            continue
        if got:
            return got[0], got[1], approx
    if net_errors == len(uniq[:5]):
        raise HTTPException(503, "Khong goi duoc dich vu dinh vi dia chi (Nominatim). Kiem tra mang.")
    return None


_GOOGLE_HOST = re.compile(r"(^|\.)google\.[a-z.]+$")
_SHORT_HOSTS = ("maps.app.goo.gl", "goo.gl")
_COORD_PATTERNS = [
    r"!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)",  # ghim cua dia diem (chinh xac nhat)
    r"@(-?\d+\.\d+),(-?\d+\.\d+)",
    r"[?&](?:q|ll|query|destination|center)=(-?\d+\.\d+),\s*(-?\d+\.\d+)",
]


def _is_google_host(host: Optional[str]) -> bool:
    h = (host or "").lower()
    return h in _SHORT_HOSTS or bool(_GOOGLE_HOST.search(h))


def _parse_coords(url: str):
    text = urllib.parse.unquote(url)
    for pat in _COORD_PATTERNS:
        m = re.search(pat, text)
        if m:
            lat, lng = float(m.group(1)), float(m.group(2))
            if 8 <= lat <= 24 and 102 <= lng <= 110:  # trong khoang Viet Nam
                return lat, lng
    return None


def coords_from_maps_url(url: str):
    """Link Google Maps (day du hoac rut gon maps.app.goo.gl) -> (lat, lng) hoac None."""
    url = url.strip()
    u = urllib.parse.urlparse(url)
    if u.scheme not in ("http", "https") or not _is_google_host(u.hostname):
        return None
    got = _parse_coords(url)
    if got:
        return got
    if (u.hostname or "").lower() in _SHORT_HOSTS:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 hcmus-an-gi"})
            with urllib.request.urlopen(req, timeout=8) as r:
                final = r.geturl()
            if _is_google_host(urllib.parse.urlparse(final).hostname):
                return _parse_coords(final)
        except (urllib.error.URLError, TimeoutError, ValueError):
            return None
    return None


def resolve_location(address: str, lat, lng, maps_url: Optional[str] = None):
    """Tra ve (lat, lng, approx, source). Uu tien: toa do client > link Google Maps > dia chi."""
    if lat is not None and lng is not None:
        return lat, lng, False, "client"
    if maps_url and maps_url.strip():
        got = coords_from_maps_url(maps_url)
        if not got:
            raise HTTPException(
                422,
                "Khong doc duoc toa do tu link Google Maps. Hay dan link day du cua quan "
                "(Chia se > Sao chep lien ket) hoac de trong de dinh vi theo dia chi.",
            )
        return got[0], got[1], False, "maps_link"
    got = geocode_address(address)
    if not got:
        raise HTTPException(
            422,
            "Khong dinh vi duoc dia chi nay. Hay nhap day du hon (so nha, ten duong, phuong, quan) "
            "hoac dan link Google Maps cua quan.",
        )
    return got[0], got[1], got[2], "address"


def derive_prices(pmin, pmax, dishes):
    """Bo trong gia -> lay min/max tu gia cac mon AI doc duoc (khong co thi 0 = chua ro)."""
    prices = [d.price for d in dishes if d.price is not None and d.price > 0]
    lo = pmin if pmin is not None else (min(prices) if prices else 0)
    hi = pmax if pmax is not None else (max(prices) if prices else lo)
    return lo, max(hi, lo)

def _parse_ings(v) -> list[str]:
    if not v:
        return []
    if isinstance(v, (bytes, bytearray)):
        v = v.decode("utf-8")
    if isinstance(v, str):
        try:
            v = json.loads(v)
        except ValueError:
            return []
    return [str(x).strip() for x in v if str(x).strip()] if isinstance(v, list) else []


def _clean_ings(items) -> list[str]:
    seen, out = set(), []
    for x in items or []:
        s = str(x).strip().lower()[:60]
        if s and s not in seen:
            seen.add(s)
            out.append(s)
    return out[:20]

def fetch_menu(cur, place_ids):
    """Load menu rows from the canonical dishes table."""
    dishes: dict[int, list] = {}
    meta: dict[int, dict] = {}
    if not place_ids:
        return dishes, meta
    fmt = ",".join(["%s"] * len(place_ids))
    try:
        cur.execute(
            f"SELECT id, place_id, name, price, description, image_url, ingredients "
            f"FROM dishes WHERE place_id IN ({fmt}) AND is_available = 1 ORDER BY id",
            list(place_ids),
        )
        for d in cur.fetchall():
            dishes.setdefault(d["place_id"], []).append(
                {
                    "id": d["id"],
                    "name": d["name"],
                    "category": None,
                    "price": d["price"],
                    "note": d["description"],
                    "ingredients": _parse_ings(d["ingredients"]),
                    "image_url": d["image_url"],
                }
            )
    except Exception:
        pass
    # Phone and free-form menu metadata are not part of the canonical schema.
    return dishes, meta


CAMPUSES = {
    "q5": {"lat": 10.762622, "lng": 106.68236, "short": "Quan 5"},
    "lang": {"lat": 10.87005, "lng": 106.8004, "short": "Lang DH"},
}


def get_conn():
    try:
        return mysql.connector.connect(**MYSQL)
    except mysql.connector.Error as e:
        raise HTTPException(503, f"MySQL khong ket noi duoc: {e}")


def haversine(a_lat, a_lng, b_lat, b_lng):
    r = 6371000.0
    d_lat = math.radians(b_lat - a_lat)
    d_lng = math.radians(b_lng - a_lng)
    s = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(a_lat))
        * math.cos(math.radians(b_lat))
        * math.sin(d_lng / 2) ** 2
    )
    return 2 * r * math.asin(min(1.0, math.sqrt(s)))


def make_token(user_id: str, email: str, ev: bool = False) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "ev": ev,
        "exp": datetime.utcnow() + timedelta(days=7),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")



class SignUpIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    name: str = Field(min_length=1, max_length=120)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


@app.post("/auth/signup")
def signup(body: SignUpIn):
    conn = get_conn()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("SELECT id FROM users WHERE email = %s", (body.email.lower(),))
        if cur.fetchone():
            raise HTTPException(400, "Email da duoc dung")
        uid = str(uuid.uuid4())
        cur.execute(
            "INSERT INTO users (id, email, name, password_hash) VALUES (%s, %s, %s, %s)",
            (uid, body.email.lower(), body.name.strip(), hash_password(body.password)),
        )
        conn.commit()
        token = make_token(uid, body.email.lower())
        return {
            "token": token,
            "user": {"id": uid, "email": body.email.lower(), "name": body.name.strip(), "avatar_url": None},
        }
    finally:
        cur.close()
        conn.close()


@app.post("/auth/login")
def login(body: LoginIn):
    conn = get_conn()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("SELECT * FROM users WHERE email = %s", (body.email.lower(),))
        row = cur.fetchone()
        if not row or not verify_password(body.password, row["password_hash"]):
            raise HTTPException(401, "Email hoac mat khau sai")
        token = make_token(row["id"], row["email"], bool(row.get("email_verified")))
        return {
            "token": token,
            "user": {
                **_public_user(row),
                "email_verified": bool(row.get("email_verified")),
            },
        }
    finally:
        cur.close()
        conn.close()
class FirebaseIn(BaseModel):
    id_token: str
GOOGLE_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "")


def _find_google_place_id(name: str, address: str, lat: float, lng: float) -> Optional[str]:
    r = httpx.post(
        "https://places.googleapis.com/v1/places:searchText",
        headers={"X-Goog-Api-Key": GOOGLE_KEY, "X-Goog-FieldMask": "places.id"},
        json={
            "textQuery": f"{name} {address}",
            "languageCode": "vi",
            "locationBias": {"circle": {"center": {"latitude": lat, "longitude": lng}, "radius": 200.0}},
        },
        timeout=8,
    )
    r.raise_for_status()
    places = r.json().get("places") or []
    return places[0]["id"] if places else None


@app.get("/places/{place_id}/google-reviews")
def google_reviews(place_id: int):
    if not GOOGLE_KEY:
        raise HTTPException(503, "Chua cau hinh GOOGLE_MAPS_API_KEY")
    conn = get_conn()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("SELECT name, address, lat, lng, google_place_id FROM places WHERE id=%s", (place_id,))
        p = cur.fetchone()
        if not p:
            raise HTTPException(404, "Khong tim thay quan")
        gid = p["google_place_id"]
        if not gid:
            gid = _find_google_place_id(p["name"], p["address"].split(" | ")[0], float(p["lat"]), float(p["lng"]))
            if not gid:
                return {"found": False, "reviews": []}
            cur.execute("UPDATE places SET google_place_id=%s WHERE id=%s", (gid, place_id))
            conn.commit()
    finally:
        cur.close()
        conn.close()

    r = httpx.get(
        f"https://places.googleapis.com/v1/places/{gid}",
        headers={
            "X-Goog-Api-Key": GOOGLE_KEY,
            "X-Goog-FieldMask": "rating,userRatingCount,googleMapsUri,reviews",
        },
        params={"languageCode": "vi"},
        timeout=8,
    )
    r.raise_for_status()
    d = r.json()
    return {
        "found": True,
        "rating": d.get("rating"),
        "count": d.get("userRatingCount"),
        "url": d.get("googleMapsUri"),
        "reviews": [
            {
                "author": (x.get("authorAttribution") or {}).get("displayName"),
                "rating": x.get("rating"),
                "when": x.get("relativePublishTimeDescription"),
                "text": ((x.get("text") or {}).get("text")),
            }
            for x in d.get("reviews", [])
        ],
    }

@app.post("/auth/firebase")
def firebase_login(body: FirebaseIn):
    try:
        d = fb_auth.verify_id_token(body.id_token)
    except Exception:
        raise HTTPException(401, "Token Firebase không hợp lệ")
    uid, email = d["uid"], (d.get("email") or "").lower()
    name = d.get("name") or email.split("@")[0]
    ev = bool(d.get("email_verified"))
    conn = get_conn(); cur = conn.cursor(dictionary=True)
    try:
        cur.execute("SELECT id FROM users WHERE firebase_uid=%s", (uid,))
        row = cur.fetchone()
        if not row:
            cur.execute("SELECT id FROM users WHERE email=%s", (email,))
            legacy = cur.fetchone()
            if legacy:
                if not ev:
                    raise HTTPException(403, "Hay xac minh email truoc khi lien ket tai khoan cu")
                row = legacy
        if row:   # gồm cả tài khoản cũ cùng email → liên kết
            user_id = row["id"]
            cur.execute("UPDATE users SET firebase_uid=%s, email_verified=%s WHERE id=%s", (uid, ev, user_id))
        else:
            user_id = str(uuid.uuid4())
            cur.execute("INSERT INTO users (id,email,name,password_hash,firebase_uid,email_verified) "
                        "VALUES (%s,%s,%s,'',%s,%s)", (user_id, email, name, uid, ev))
        conn.commit()
        return {"token": make_token(user_id, email, ev),
                "user": {"id": user_id, "email": email, "name": name, "email_verified": ev}}
    finally:
        cur.close(); conn.close()
@app.get("/places")
def list_places(
   campus: str = "q5",
    budget: Optional[int] = None,
    radius_m: Optional[int] = None,
    food: Optional[str] = None,
    cuisine: Optional[str] = None,

):
    if campus not in CAMPUSES:
        raise HTTPException(400, "campus phai la q5 hoac lang")
    origin = CAMPUSES[campus]
    conn = get_conn()
    cur = conn.cursor(dictionary=True)
    try:
        sql = (
            "SELECT id, name, campus, lat, lng, price_min, price_max, cuisine, address, hours_text AS hours "
            "FROM places WHERE campus = %s"
        )
        params: list[Any] = [campus]
        if budget is not None:
            sql += " AND price_min <= %s"
            params.append(budget)

        food_target = food or cuisine
        if food_target:
            search_terms = extract_search_keywords(food_target, slugify_food(food_target))
            if not search_terms:
                search_terms = [food_target]
            or_clauses = " OR ".join(["LOWER(cuisine) LIKE %s OR LOWER(name) LIKE %s"] * len(search_terms))
            sql += f" AND ({or_clauses})"
            for term in search_terms:
                p = f"%{term.lower()}%"
                params.extend([p, p])

        cur.execute(sql, tuple(params))
        rows = cur.fetchall()

        dish_names: dict[int, list[str]] = {}
        if rows:
            fmt = ",".join(["%s"] * len(rows))
            try:
                cur.execute(
                    f"SELECT place_id, name FROM dishes "
                    f"WHERE place_id IN ({fmt}) AND is_available = 1",
                    [r["id"] for r in rows],
                )
                for d in cur.fetchall():
                    dish_names.setdefault(d["place_id"], []).append(d["name"])
            except Exception:
                pass
    finally:
        cur.close()
        conn.close()

    out = []
    for p in rows:
        lat, lng = float(p["lat"]), float(p["lng"])
        meters = haversine(origin["lat"], origin["lng"], lat, lng)
        if radius_m is not None and meters > radius_m:
            continue
        out.append(
            {
                "id": p["id"],
                "name": p["name"],
                "campus": p["campus"],
                "lat": lat,
                "lng": lng,
                "price_min": int(p["price_min"]), 
                "price_max": int(p["price_max"]),
                "cuisine": p["cuisine"],
                "address": p["address"],
                "hours": p["hours"],
                "meters": round(meters),
                "dish_names": dish_names.get(p["id"], []),
            }
        )
#Auto relax 
    if len(out) == 0 and radius_m is not None:
         for p in rows:
                lat, lng = float(p["lat"]), float(p["lng"])
                meters = haversine(origin["lat"], origin["lng"], lat, lng)
        
                
                if meters > radius_m*1.20:
                    continue
                out.append(
                    {
                        "id": p["id"],
                        "name": p["name"],
                        "campus": p["campus"],
                        "lat": lat,
                        "lng": lng,
                        "price_min": int(p["price_min"]), 
                        "price_max": int(p["price_max"]),
                        "cuisine": p["cuisine"],
                        "address": p["address"],
                        "hours": p["hours"],
                        "meters": round(meters),
                        "dish_names": dish_names.get(p["id"], []),
                    }
                )


    out.sort(key=lambda x: x["meters"])
    return out

class ReviewIn(BaseModel):
    place_id: int
    rating: int = Field(ge=1, le=5)
    body: str = Field(min_length=4, max_length=500)


@app.get("/reviews")
def list_reviews(place_id: Optional[int] = None):
    conn = get_conn()
    cur = conn.cursor(dictionary=True)
    try:
        if place_id:
            cur.execute(
                "SELECT r.id, r.place_id, r.rating, r.body, r.created_at, u.name AS author_name "
                "FROM reviews r JOIN users u ON u.id = r.user_id WHERE r.place_id = %s "
                "ORDER BY r.id DESC LIMIT 50",
                (place_id,),
            )
        else:
            cur.execute(
                "SELECT r.id, r.place_id, r.rating, r.body, r.created_at, u.name AS author_name "
                "FROM reviews r JOIN users u ON u.id = r.user_id ORDER BY r.id DESC LIMIT 100"
            )
        return cur.fetchall()
    finally:
        cur.close()
        conn.close()


@app.post("/reviews")
def add_review(body: ReviewIn, user: dict = Depends(verified_user)):
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO reviews (place_id, user_id, rating, body) VALUES (%s, %s, %s, %s)",
            (body.place_id, user["id"], body.rating, body.body.strip()),
        )
        conn.commit()
        return {"ok": True}
    finally:
        cur.close()
        conn.close()


@app.get("/saves")
def list_saves(user: dict = Depends(current_user)):
    conn = get_conn()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("SELECT place_id FROM saves WHERE user_id = %s", (user["id"],))
        return [r["place_id"] for r in cur.fetchall()]
    finally:
        cur.close()
        conn.close()


@app.post("/saves/{place_id}")
def toggle_save(place_id: int, user: dict = Depends(current_user)):
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT 1 FROM saves WHERE user_id = %s AND place_id = %s",
            (user["id"], place_id),
        )
        if cur.fetchone():
            cur.execute(
                "DELETE FROM saves WHERE user_id = %s AND place_id = %s",
                (user["id"], place_id),
            )
            conn.commit()
            return {"saved": False}
        cur.execute(
            "INSERT INTO saves (user_id, place_id) VALUES (%s, %s)",
            (user["id"], place_id),
        )
        conn.commit()
        return {"saved": True}
    finally:
        cur.close()
        conn.close()


class HistoryIn(BaseModel):
    campus: str
    budget: Optional[int]
    radius_m: Optional[int]
    query: str


@app.get("/history")
def list_history(user: dict = Depends(current_user)):
    conn = get_conn()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(
            "SELECT id, campus, budget, radius_m, required_dish, query_text AS query, result_count, created_at FROM search_history "
            "WHERE user_id = %s ORDER BY id DESC LIMIT 30",
            (user["id"],),
        )
        return cur.fetchall()
    finally:
        cur.close()
        conn.close()


@app.post("/history")
def add_history(body: HistoryIn, user: dict = Depends(current_user)):
    if body.campus not in CAMPUSES:
        raise HTTPException(400, "campus khong hop le")
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO search_history (user_id, campus, budget, radius_m, query_text) "
            "VALUES (%s, %s, %s, %s, %s)",
            (user["id"], body.campus, body.budget, body.radius_m, body.query[:300]),
        )
        conn.commit()
        return {"ok": True}
    finally:
        cur.close()
        conn.close()


CAMPUS_Q5 = re.compile(r"quan\s*5|q\.?\s*5|nguyen van cu|nvc", re.I)
CAMPUS_LANG = re.compile(r"lang|linh trung|thu duc", re.I)
def normalize_text(text: str) -> str:
    text = text.lower().replace("đ", "d")

    text = unicodedata.normalize("NFD", text)

    text = "".join(
        char
        for char in text
        if unicodedata.category(char) != "Mn"
    )

    return text

def parse_money(text: str):
    """Nhan dien ngan sach trong van ban thuong (fallback khi Gemini loi).
    Dung normalize_budget_text tu normalizer.py de ho tro day du cac dinh dang VND."""
    return normalize_budget_text(text)



def parse_radius(text: str):
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*(km|m|met)\b", text, re.I)
    if not m:
        return None
    n = float(m.group(1).replace(",", "."))
    return int(n * 1000) if m.group(2).lower() == "km" else int(n)



class ChatBody(BaseModel):
    message: str
    campus: Optional[str] = None
    budget: Optional[int] = None
    budget_unlimited: bool = False
    budget_is_default: Optional[bool] = False
    radius_m: Optional[int] = None
    radius_unlimited: bool = False
    radius_is_default: Optional[bool] = False
    food_name: Optional[str] = None
    place_name: Optional[str] = None
    preference: Optional[str] = None
    cuisine: Optional[str] = None
    keywords: list[str] = Field(default_factory=list)
    # Emotion context
    emotion: Optional[dict] = None
    emotion_turn: Optional[int] = None
    turn_count: Optional[int] = None


def _build_emotion_reply(intent: dict) -> Optional[str]:
    """
    Tạo câu trả lời cảm xúc nếu intent là emotion_based_food_suggestion.
    Trả về None nếu không cần trả lời cảm xúc.
    """
    emotion = intent.get("emotion")
    if not emotion or not isinstance(emotion, dict):
        return None

    category = emotion.get("category")
    wants_food = emotion.get("wants_food_suggestion", False)

    # Map cảm xúc → gợi ý món ăn phù hợp (không bịa quán)
    suggestions = {
        "sadness": (
            "Mình hiểu cảm giác buồn không dễ chịu chút nào 🥺 "
            "Những lúc này, món ăn ấm áp như cháo, súp, hoặc một tô phở thường giúp cảm thấy dễ chịu hơn. "
            "Bạn muốn mình tìm quán gần trường không?"
        ),
        "stress": (
            "Deadline căng thẳng thật 😮‍💨 "
            "Bạn nên ăn gì đó nhẹ nhàng để nạp năng lượng — cháo, bún, hoặc cơm bình thường đều ổn. "
            "Muốn mình tìm quán phù hợp không?"
        ),
        "tiredness": (
            "Mệt rồi thì cần ăn ngon để lấy lại sức 💪 "
            "Món có nhiều chất như cơm, bún bò, hoặc phở sẽ giúp bạn tỉnh táo hơn. "
            "Bạn muốn tìm quán nào không?"
        ),
        "happiness": (
            "Vui quá thì phải ăn gì ngon chứ 🎉 "
            "Bạn thử đồ ăn đặc sản hoặc quán nổi tiếng gần trường xem sao? "
            "Nói cho mình biết ngân sách và khu vực, mình tìm cho nhé!"
        ),
        "celebration": (
            "Chúc mừng bạn 🥳 Dịp đặc biệt thì xứng đáng được ăn ngon! "
            "Bạn muốn đặc sản hay món bình thường? Và ở cơ sở nào?"
        ),
        "boredom": (
            "Chán ăn cơm mãi rồi hả 😄 "
            "Thử đổi sang bún, phở, bánh mì, hay đồ ăn vặt xem sao? "
            "Mình có thể tìm quán mới gần đây cho bạn!"
        ),
        "comfort": (
            "Muốn ăn gì đó nhẹ nhàng dễ chịu á 🍲 "
            "Cháo, súp, hoặc bún riêu thường là lựa chọn tốt. "
            "Bạn muốn mình tìm quán không?"
        ),
    }

    if wants_food and category in suggestions:
        return suggestions[category]

    # Cảm xúc nhận ra nhưng chưa hỏi về ăn uống
    empathy = {
        "sadness": "Mình nghe thấy bạn đang buồn 🥺 Nếu muốn ăn gì đó để cảm thấy tốt hơn, bảo mình nhé!",
        "stress": "Stress thật rồi 😮‍💨 Nếu muốn tìm chỗ ăn để thư giãn, mình sẵn sàng giúp!",
        "tiredness": "Nghỉ ngơi chút đi nhé 😴 Nếu muốn ăn gì đó lấy sức, bảo mình!",
        "happiness": "Vui ghê! 😊 Muốn tìm quán ăn không?",
        "celebration": "Chúc mừng bạn! 🎊 Muốn đi ăn gì để ăn mừng không?",
        "boredom": "Chán ăn rồi à 😄 Muốn mình gợi ý đổi món không?",
        "comfort": "Muốn ăn gì nhẹ nhàng à? Bảo mình nhé!",
    }

    return empathy.get(category)


@app.post("/chat")
def chat(body: ChatBody):

    previous = {
        "campus": body.campus,
        "budget": None if body.budget_is_default else body.budget,
        "budget_unlimited": body.budget_unlimited,
        "budget_is_default": body.budget_is_default or False,
        "radius_m": None if body.radius_is_default else body.radius_m,
        "radius_unlimited": body.radius_unlimited,
        "radius_is_default": body.radius_is_default or False,
        "food_name": body.food_name,
        "place_name": body.place_name,
        "preference": body.preference,
        "cuisine": body.cuisine,
        "keywords": body.keywords,
        # Truyền emotion context từ frontend vào ngữ cảnh hội thoại
        "emotion": body.emotion,
        "emotion_turn": body.emotion_turn,
        "turn_count": body.turn_count or 0,
    }

    normalized_message = normalize_text(body.message)
    unlimited = {f"{key}_unlimited": True for key, pattern in UNLIMITED_PATTERNS.items()
                 if pattern.search(normalized_message)}
    try:
        extracted = extract_intent(body.message, previous)
        extracted = validate_intent(extracted)
        intent = merge_context(previous, extracted.model_copy(update=unlimited))

    except Exception as e:
        print(
            f"[INPUT UNDERSTANDING ERROR] "
            f"{type(e).__name__}: {e}"
        )

        # Chuyển văn bản về dạng không dấu để Regex dễ nhận diện

        # Giữ lại ngữ cảnh trước đó
        intent = previous.copy()

        # Nhận diện địa điểm
        if CAMPUS_Q5.search(normalized_message):
            intent["campus"] = "q5"

        if CAMPUS_LANG.search(normalized_message):
            intent["campus"] = "lang"

        # Nhận diện ngân sách – dùng normalizer (hỗ trợ 200000, 200k, v.v.)
        food_res = fallback_extract_food(body.message)
        budget_message = body.message
        if food_res.place_name:
            budget_message = budget_message.replace(food_res.place_name, "", 1)
        money = parse_money(budget_message)
        if money is None:
            money = parse_money(normalize_text(budget_message))

        radius = parse_radius(normalized_message)

        # Fallback nhận diện món ăn (Food Understanding - không dùng danh sách cứng)
        if food_res.food_name:
            intent["food_name"] = food_res.food_name
        if food_res.place_name:
            intent["place_name"] = food_res.place_name
        if food_res.preference:
            intent["preference"] = food_res.preference

        # Fallback nhận diện cảm xúc (khi Gemini offline)
        low_msg = body.message.lower()
        emo_cat = None
        if any(w in low_msg for w in ("stress", "căng thẳng", "cang thang", "áp lực", "ap luc", "deadline")):
            emo_cat = "stress"
        elif any(w in low_msg for w in ("buồn", "buon", "thất vọng", "that vong", "cô đơn", "co don")):
            emo_cat = "sadness"
        elif any(w in low_msg for w in ("mệt", "met", "kiệt sức", "kiet suc", "uể oải", "ue oai", "đuối", "duoi")):
            emo_cat = "tiredness"
        elif any(w in low_msg for w in ("vui", "hạnh phúc", "hanh phuc", "phấn khởi")):
            emo_cat = "happiness"
        elif any(w in low_msg for w in ("tự thưởng", "tu thuong", "ăn mừng", "an mung")):
            emo_cat = "celebration"
        elif any(w in low_msg for w in ("chán", "chan", "ngán", "ngan")):
            emo_cat = "boredom"

        turn = (previous.get("turn_count") or 0) + 1
        intent["turn_count"] = turn

        if emo_cat:
            wants_food = any(w in low_msg for w in ("ăn", "an", "món", "mon", "quán", "quan", "gợi ý", "goi y"))
            intent["intent"] = "emotion_based_food_suggestion"
            intent["emotion"] = {"category": emo_cat, "confidence": 0.85, "wants_food_suggestion": wants_food}
            intent["emotion_turn"] = turn

        merge_limits(intent, {"budget": money, "radius_m": radius, **unlimited})

    # --- Xác định reply ---
    detected_intent = intent.get("intent", "search_food")
    food_display = intent.get("food_name") or ""

    # Trường hợp emotion-based: trả lời cảm xúc nếu không đủ thông tin tìm kiếm
    emotion_reply = _build_emotion_reply(intent)

    if detected_intent == "emotion_based_food_suggestion" and emotion_reply and not intent.get("place_name"):
        reply = emotion_reply
        ready = False

    elif not intent.get("campus") and not intent.get("place_name"):
        # Nếu có cảm xúc, hỏi kèm theo ngữ cảnh cảm xúc
        if emotion_reply:
            reply = emotion_reply
        elif food_display:
            reply = f"Bạn muốn tìm {food_display} ở cơ sở Quận 5 hay Làng Đại học?"
        else:
            reply = "Bạn muốn tìm quán ở cơ sở Quận 5 hay Làng Đại học?"
        ready = False

    elif not intent.get("budget") and not intent.get("budget_unlimited"):
        reply = "Ngân sách tối đa mỗi người của bạn là bao nhiêu?"
        ready = False

    elif not intent.get("radius_m") and not intent.get("radius_unlimited"):
        reply = "Bạn muốn tìm quán trong khoảng cách bao xa?"
        ready = False

    else:
        details = []
        if food_display:
            details.append(f"món {food_display}")
        if intent.get("place_name"):
            details.append(f"quán {intent['place_name']}")
        if intent.get("campus") in CAMPUSES:
            campus_label = "Quận 5" if intent["campus"] == "q5" else "Làng Đại học"
            details.append(f"khu vực {campus_label}")
        if intent.get("preference"):
            details.append(f"sở thích {intent['preference']}")
        budget_label = "ngân sách mặc định" if intent.get("budget_is_default") else "ngân sách"
        radius_label = "bán kính mặc định" if intent.get("radius_is_default") else "bán kính"
        if intent.get("budget_unlimited"):
            details.append("không giới hạn giá")
        else:
            budget_text = f"{intent['budget']:,}".replace(",", ".")
            details.append(f"{budget_label} {budget_text}đ")
        if intent.get("radius_unlimited"):
            details.append("không giới hạn bán kính")
        else:
            details.append(f"{radius_label} {intent['radius_m']} m")
        reply = "Mình đã ghi nhận " + ", ".join(details) + "."
        ready = True

    return {
        "ready": ready,
        "campus": intent.get("campus"),
        "budget": intent.get("budget"),
        "budget_unlimited": intent.get("budget_unlimited", False),
        "budget_is_default": intent.get("budget_is_default", False),
        "radius_m": intent.get("radius_m"),
        "radius_unlimited": intent.get("radius_unlimited", False),
        "radius_is_default": intent.get("radius_is_default", False),
        "food_name": intent.get("food_name"),
        "place_name": intent.get("place_name"),
        "preference": intent.get("preference"),
        "reply": reply,
        # Trả về emotion context để frontend lưu và gửi lại lượt sau
        "emotion": intent.get("emotion"),
        "emotion_turn": intent.get("emotion_turn"),
        "turn_count": intent.get("turn_count"),
    }

class ContributeIn(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    campus: str
    lat: Optional[float] = None  # bo trong -> server tu dinh vi tu dia chi
    lng: Optional[float] = None
    maps_url: Optional[str] = Field(default=None, max_length=2000)  # link Google Maps (tuy chon)
    price_min: Optional[int] = Field(default=None, ge=0)  # bo trong -> AI/server tu tinh
    price_max: Optional[int] = Field(default=None, ge=0)
    cuisine: str = Field(min_length=1, max_length=80)
    address: str = Field(min_length=2)
    hours: str = Field(default="", max_length=255)
    note: Optional[str] = None


@app.post("/places/contribute")
def contribute_place(
    body: ContributeIn,
    request: Request,
    user: dict = Depends(verified_user),
):
    """Dong gop quan + rate limit + chong trung."""
    if body.campus not in CAMPUSES:
        raise HTTPException(400, "campus phai la q5 hoac lang")
    if (
        body.price_min is not None
        and body.price_max is not None
        and body.price_max < body.price_min
    ):
        raise HTTPException(400, "price_max phai >= price_min")
    name = body.name.strip()

    ip = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    if not ip:
        ip = request.client.host if request.client else "unknown"

    ok, msg = check_contribute_allowed(user["id"], ip)
    if not ok:
        raise HTTPException(status_code=429, detail=msg)

    depth = queue_enter()
    try:
        if depth > 50:
            raise HTTPException(503, "He thong dang tai cao. Thu lai sau.")
        lat, lng, approx, source = resolve_location(body.address, body.lat, body.lng, body.maps_url)
        price_min, price_max = derive_prices(body.price_min, body.price_max, [])

        conn = get_conn()
        cur = conn.cursor(dictionary=True)
        try:
            cur.execute(
                "SELECT id FROM places WHERE campus = %s AND LOWER(name) = LOWER(%s) LIMIT 1",
                (body.campus, name),
            )
            if cur.fetchone():
                raise HTTPException(409, "Quan nay da co (trung ten + co so).")

            note = (body.note or "").strip()
            address = body.address.strip()
            if note:
                address = f"{address} | {note}"
            address = address[:255]

            cur.execute(
                """INSERT INTO places
                (name, campus, lat, lng, price_min, price_max, cuisine, address, hours_text)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (name, body.campus, lat, lng, price_min, price_max,
                 body.cuisine.strip(), address, (body.hours or "Chua ro")[:80] or None),
            )
            conn.commit()
            new_id = cur.lastrowid
            record_contribute(user["id"], ip)
            return {
                "ok": True,
                "id": new_id,
                "lat": lat,
                "lng": lng,
                "approx_location": approx,
                "location_source": source,
                "rate_limit": queue_stats(),
            }
        finally:
            cur.close()
            conn.close()
    finally:
        queue_leave()




@app.post("/menu/scan")
async def menu_scan(
    request: Request,
    files: list[UploadFile] = File(default=[]),
    file: Optional[UploadFile] = File(default=None),
    user: dict = Depends(verified_user),
):
    """Nhan 1..10 anh (cac trang cua cung 1 menu), Gemini Vision doc -> mon + gia + thong tin quan."""
    ip = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    if not ip and request.client:
        ip = request.client.host
    check_contribute_allowed(user["id"], ip or "unknown")

    uploads = list(files) + ([file] if file else [])
    if not uploads:
        raise HTTPException(400, "Chua co anh nao")
    if len(uploads) > 10:
        raise HTTPException(400, "Toi da 10 anh moi lan")

    images: list[tuple[bytes, str]] = []
    total = 0
    for up in uploads:
        mime = (up.content_type or "image/jpeg").lower()
        if not mime.startswith("image/"):
            raise HTTPException(400, "Chi nhan file anh (jpeg/png/webp)")
        raw = await up.read()
        if not raw:
            raise HTTPException(400, "Co file anh rong")
        if len(raw) > 8 * 1024 * 1024:
            raise HTTPException(400, "Moi anh toi da 8MB")
        total += len(raw)
        if total > 25 * 1024 * 1024:
            raise HTTPException(400, "Tong dung luong anh toi da 25MB")
        images.append((raw, mime))

    try:
        # chay trong thread de khong chan cac request khac (Gemini mat vai chuc giay)
        result = await run_in_threadpool(scan_menu_images, images)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(502, f"Loi Gemini OCR: {e}")

    return {"ok": True, "images": len(images), **result}


class DishIn(BaseModel):
    name: str = Field(min_length=1, max_length=180)
    price: Optional[int] = Field(default=None, ge=0)
    category: Optional[str] = Field(default=None, max_length=120)
    note: Optional[str] = None
    ingredients: list[str] = Field(default_factory=list)


class MenuMetaIn(BaseModel):
    phone: Optional[str] = Field(default=None, max_length=60)
    hours: Optional[str] = Field(default=None, max_length=255)
    notes: Optional[str] = None


class ContributeWithMenuIn(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    campus: str
    lat: Optional[float] = None  # bo trong -> server tu dinh vi tu dia chi
    lng: Optional[float] = None
    maps_url: Optional[str] = Field(default=None, max_length=2000)  # link Google Maps (tuy chon)
    price_min: Optional[int] = Field(default=None, ge=0)  # bo trong -> AI/server tu tinh
    price_max: Optional[int] = Field(default=None, ge=0)
    cuisine: str = Field(min_length=1, max_length=80)
    address: str = Field(min_length=2)
    hours: str = Field(default="", max_length=255)
    note: Optional[str] = None
    dishes: list[DishIn] = []
    menu_meta: Optional[MenuMetaIn] = None


@app.post("/places/contribute-with-menu")
def contribute_with_menu(
    body: ContributeWithMenuIn,
    request: Request,
    user: dict = Depends(verified_user),
):
    """Tao quan + luu danh sach mon (sau khi user xac nhan ket qua OCR)."""
    if body.campus not in CAMPUSES:
        raise HTTPException(400, "campus phai la q5 hoac lang")
    if (
        body.price_min is not None
        and body.price_max is not None
        and body.price_max < body.price_min
    ):
        raise HTTPException(400, "price_max phai >= price_min")

    ip = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    if not ip and request.client:
        ip = request.client.host
    ok, msg = check_contribute_allowed(user["id"], ip or "unknown")
    if not ok:
        raise HTTPException(429, msg)

    depth = queue_enter()
    try:
        if depth > 50:
            raise HTTPException(503, "He thong dang tai cao.")
        lat, lng, approx, source = resolve_location(body.address, body.lat, body.lng, body.maps_url)
        price_min, price_max = derive_prices(body.price_min, body.price_max, body.dishes)
        name = body.name.strip()
        conn = get_conn()
        cur = conn.cursor(dictionary=True)
        try:
            cur.execute(
                "SELECT id FROM places WHERE campus = %s AND LOWER(name) = LOWER(%s) LIMIT 1",
                (body.campus, name),
            )
            if cur.fetchone():
                raise HTTPException(409, "Quan da ton tai (trung ten + co so).")

            note = (body.note or "").strip()
            address = body.address.strip()
            if note:
                address = f"{address} | {note}"
            address = address[:255]

            cur.execute(
                """INSERT INTO places
                (name, campus, lat, lng, price_min, price_max, cuisine, address, hours_text)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (name, body.campus, lat, lng, price_min, price_max,
                 body.cuisine.strip(), address, (body.hours or "Chua ro")[:80] or None),
            )
            place_id = cur.lastrowid

            for d in body.dishes[:150]:
                cur.execute(
                    "INSERT INTO dishes (place_id, name, price, ingredients, description, image_url) "
                    "VALUES (%s,%s,%s,%s,%s,%s)",
                    (
                        place_id,
                        d.name.strip()[:180],
                        d.price if d.price is not None else 0,
                        json.dumps(_clean_ings(d.ingredients), ensure_ascii=False),
                        (d.note or d.category or "").strip()[:300] or None,
                        None,
                    ),
                )
            mm = body.menu_meta
            if mm and mm.hours:
                cur.execute("UPDATE places SET hours_text = %s WHERE id = %s", (mm.hours.strip()[:80], place_id))
            conn.commit()
            record_contribute(user["id"], ip or "unknown")
            return {
                "ok": True,
                "id": place_id,
                "lat": lat,
                "lng": lng,
                "approx_location": approx,
                "location_source": source,
                "price_min": price_min,
                "price_max": price_max,
                "dishes_saved": min(len(body.dishes), 150),
            }
        finally:
            cur.close()
            conn.close()
    finally:
        queue_leave()


@app.get("/places/saved")
def list_saved_places(user: dict = Depends(current_user)):
    """Quan user da luu: day du thong tin + menu, khong loc theo ban kinh."""
    conn = get_conn()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(
            "SELECT p.id, p.name, p.campus, p.lat, p.lng, p.price_min, p.price_max, "
            "p.cuisine, p.address, p.hours_text AS hours "
            "FROM saves s JOIN places p ON p.id = s.place_id "
            "WHERE s.user_id = %s ORDER BY p.id DESC",
            (user["id"],),
        )
        rows = cur.fetchall()
        dishes, meta = fetch_menu(cur, [r["id"] for r in rows])
        return [
            {
                "id": r["id"],
                "name": r["name"],
                "campus": r["campus"],
                "lat": float(r["lat"]),
                "lng": float(r["lng"]),
                "price_min": int(r["price_min"]),
                "price_max": int(r["price_max"]),
                "cuisine": r["cuisine"],
                "address": r["address"],
                "hours": r["hours"],
                "dishes": dishes.get(r["id"], []),
                "menu_meta": meta.get(r["id"]),
            }
            for r in rows
        ]
    finally:
        cur.close()
        conn.close()


@app.get("/places/{place_id}/info")
def place_info(place_id: int):
    """Menu (mon, gia, nhom) + thong tin AI doc duoc tu anh menu cua 1 quan."""
    conn = get_conn()
    cur = conn.cursor(dictionary=True)
    try:
        dishes, meta = fetch_menu(cur, [place_id])
        return {"dishes": dishes.get(place_id, []), "menu_meta": meta.get(place_id)}
    finally:
        cur.close()
        conn.close()


@app.get("/places/{place_id}/dishes")
def list_dishes(place_id: int):
    conn = get_conn()
    cur = conn.cursor(dictionary=True)
    try:
        try:
            cur.execute(
                "SELECT id, name, NULL AS category, price, description AS note FROM dishes WHERE place_id = %s AND is_available = 1 ORDER BY id",
                (place_id,),
            )
            return cur.fetchall()
        except Exception:
            return []
    finally:
        cur.close()
        conn.close()


@app.get("/health")
def health():
    try:
        conn = get_conn()
        conn.close()
        mysql_ok = True
    except Exception:
        mysql_ok = False
    return {"status": "ok", "mysql": mysql_ok, "rate_limit": queue_stats()}
