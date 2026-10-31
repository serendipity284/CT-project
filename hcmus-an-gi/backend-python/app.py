"""
HCMUS An Gi — FastAPI + MySQL
Chay: uvicorn app:app --reload --port 8000
"""

from __future__ import annotations

import math
import os
import re
import uuid
from datetime import datetime, timedelta
from typing import Any, Optional

import mysql.connector
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr, Field

load_dotenv()

MYSQL = {
    "host": os.getenv("MYSQL_HOST", "127.0.0.1"),
    "port": int(os.getenv("MYSQL_PORT", "3306")),
    "user": os.getenv("MYSQL_USER", "root"),
    "password": os.getenv("MYSQL_PASSWORD", ""),
    "database": os.getenv("MYSQL_DATABASE", "hcmus_an_gi"),
}
JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-change-me")
pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")

app = FastAPI(title="HCMUS An Gi API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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


def make_token(user_id: str, email: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "exp": datetime.utcnow() + timedelta(days=7),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def current_user(authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Can dang nhap")
    token = authorization[7:].strip()
    try:
        data = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return {"id": data["sub"], "email": data.get("email", "")}
    except JWTError:
        raise HTTPException(401, "Token khong hop le")


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
            (uid, body.email.lower(), body.name.strip(), pwd.hash(body.password)),
        )
        conn.commit()
        token = make_token(uid, body.email.lower())
        return {
            "token": token,
            "user": {"id": uid, "email": body.email.lower(), "name": body.name.strip()},
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
        if not row or not pwd.verify(body.password, row["password_hash"]):
            raise HTTPException(401, "Email hoac mat khau sai")
        token = make_token(row["id"], row["email"])
        return {
            "token": token,
            "user": {"id": row["id"], "email": row["email"], "name": row["name"]},
        }
    finally:
        cur.close()
        conn.close()


@app.get("/places")
def list_places(campus: str = "q5", budget: int = 50000, radius_m: int = 800):
    if campus not in CAMPUSES:
        raise HTTPException(400, "campus phai la q5 hoac lang")
    origin = CAMPUSES[campus]
    conn = get_conn()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(
            "SELECT id, name, campus, lat, lng, price_min, price_max, cuisine, address, hours "
            "FROM places WHERE campus = %s AND price_min <= %s",
            (campus, budget),
        )
        rows = cur.fetchall()
    finally:
        cur.close()
        conn.close()

    out = []
    for p in rows:
        lat, lng = float(p["lat"]), float(p["lng"])
        meters = haversine(origin["lat"], origin["lng"], lat, lng)
        if meters > radius_m:
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
def add_review(body: ReviewIn, user: dict = Depends(current_user)):
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
    budget: int
    radius_m: int
    query: str


@app.get("/history")
def list_history(user: dict = Depends(current_user)):
    conn = get_conn()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(
            "SELECT id, campus, budget, radius_m, query, created_at FROM search_history "
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
            "INSERT INTO search_history (user_id, campus, budget, radius_m, query) "
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


def parse_money(text: str):
    m = re.search(
        r"(?:duoi|toi da|max|<)\s*(\d+(?:[.,]\d+)?)\s*(k|nghin|tr)?",
        text,
        re.I,
    ) or re.search(r"(\d+(?:[.,]\d+)?)\s*(k|nghin|trieu|tr)\b", text, re.I)
    if not m:
        return None
    raw = float(m.group(1).replace(",", "."))
    unit = (m.group(2) or "").lower()
    if unit.startswith("tr"):
        return int(raw * 1_000_000)
    if unit in ("k",) or unit.startswith("ngh"):
        return int(raw * 1000)
    if raw < 500:
        return int(raw * 1000)
    return int(raw)


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
    radius_m: Optional[int] = None


@app.post("/chat")
def chat(body: ChatBody):
    campus, budget, radius_m = body.campus, body.budget, body.radius_m
    text = body.message
    if CAMPUS_Q5.search(text):
        campus = "q5"
    if CAMPUS_LANG.search(text):
        campus = "lang"
    money = parse_money(text)
    if money is not None:
        budget = money
    rad = parse_radius(text)
    if rad is not None:
        radius_m = rad
    if not campus:
        return {"ready": False, "campus": campus, "budget": budget, "radius_m": radius_m, "reply": "Co so nao? q5 hay lang"}
    if not budget:
        return {"ready": False, "campus": campus, "budget": budget, "radius_m": radius_m, "reply": "Ngan sach toi da?"}
    if not radius_m:
        return {"ready": False, "campus": campus, "budget": budget, "radius_m": radius_m, "reply": "Ban kinh di bo?"}
    return {
        "ready": True,
        "campus": campus,
        "budget": budget,
        "radius_m": radius_m,
        "reply": f"OK loc {campus}, {budget}d, {radius_m}m",
    }


@app.get("/health")
def health():
    try:
        conn = get_conn()
        conn.close()
        mysql_ok = True
    except Exception:
        mysql_ok = False
    return {"status": "ok", "mysql": mysql_ok}
