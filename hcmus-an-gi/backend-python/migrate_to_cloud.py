"""Chuyen database tu XAMPP (may ban) len database cloud khai bao trong .env.

Chi MOT nguoi chay, MOT lan:   python migrate_to_cloud.py
XAMPP co mat khau/ten DB khac: python migrate_to_cloud.py --src-password abc --src-db ten_db
Script khong sua gi tren XAMPP.
"""
import argparse
import re
import sys

import mysql.connector

from db_config import BASE_DIR, MYSQL

SCHEMA_FILE = BASE_DIR.parent / "heana_schema.sql"
# Thu tu: bang cha truoc, bang con sau
TABLES = [
    "users", "user_preferences", "places", "ingredient_aliases", "dishes",
    "alley_nodes", "alley_edges", "reviews", "saves", "search_history",
]
JSON_COLUMNS = {("dishes", "ingredients"), ("user_preferences", "allergies")}


def create_statements() -> list[str]:
    sql = SCHEMA_FILE.read_text(encoding="utf-8")
    sql = "\n".join(l for l in sql.splitlines() if not l.lstrip().startswith("--"))
    found = re.findall(r"CREATE TABLE IF NOT EXISTS .*?ENGINE=[^;]*", sql, re.S)
    out = []
    for stmt in found:
        # TiDB chi nhan default dang ham cho cot JSON, khong nhan chuoi '[]'
        stmt = stmt.replace("DEFAULT ('[]')", "DEFAULT (JSON_ARRAY())")
        # TiDB: cap ID tang dan giong MySQL (may chu khac bo qua comment nay)
        if "AUTO_INCREMENT" in stmt:
            stmt += " /*T![auto_id_cache] AUTO_ID_CACHE=1 */"
        out.append(stmt)
    return out


def tables_of(cur) -> set[str]:
    cur.execute("SHOW TABLES")
    return {r[0] for r in cur.fetchall()}


def columns_of(cur, table: str) -> list[str]:
    cur.execute(f"SHOW COLUMNS FROM `{table}`")
    return [r[0] for r in cur.fetchall()]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src-host", default="127.0.0.1")
    ap.add_argument("--src-port", type=int, default=3306)
    ap.add_argument("--src-user", default="root")
    ap.add_argument("--src-password", default="")
    ap.add_argument("--src-db", default="hcmus_an_gi")
    a = ap.parse_args()

    if MYSQL["host"] in ("127.0.0.1", "localhost") and MYSQL["port"] == a.src_port:
        sys.exit("File .env van dang tro vao XAMPP. Hay dien thong tin database cloud truoc.")
    db = MYSQL["database"]
    if not re.fullmatch(r"\w+", db):
        sys.exit("MYSQL_DATABASE chi duoc gom chu, so va dau _")

    src = mysql.connector.connect(
        host=a.src_host, port=a.src_port, user=a.src_user,
        password=a.src_password, database=a.src_db, time_zone="+07:00",
    )
    dst = mysql.connector.connect(**{k: v for k, v in MYSQL.items() if k != "database"})
    s, d = src.cursor(), dst.cursor()

    print(f"[1/3] Tao bang tren {MYSQL['host']} / {db}")
    d.execute(f"CREATE DATABASE IF NOT EXISTS `{db}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
    d.execute(f"USE `{db}`")
    for stmt in create_statements():
        d.execute(stmt)
    if "avatar_url" not in columns_of(d, "users"):
        d.execute("ALTER TABLE users ADD COLUMN avatar_url VARCHAR(500) NULL AFTER name")

    print("[2/3] Kiem tra truoc khi chep")
    src_tables = tables_of(s)
    problems = []
    for t in TABLES:
        d.execute(f"SELECT COUNT(*) FROM `{t}`")
        if d.fetchone()[0]:
            problems.append(f"Bang cloud '{t}' da co du lieu (khong ghi de)")
        if t in src_tables:
            extra = set(columns_of(s, t)) - set(columns_of(d, t))
            if extra:
                problems.append(f"Bang '{t}' o XAMPP co cot khong co trong schema: {sorted(extra)}")
    if problems:
        sys.exit("DUNG, chua chep gi:\n - " + "\n - ".join(problems))
    skipped = sorted(src_tables - set(TABLES))
    if skipped:
        print(f"  Luu y: bo qua bang ngoai schema chuan: {skipped}")

    print("[3/3] Chep du lieu")
    d.execute("SET FOREIGN_KEY_CHECKS = 0")
    try:
        for t in TABLES:
            if t not in src_tables:
                print(f"  {t}: XAMPP khong co bang nay")
                continue
            cols = columns_of(s, t)
            names = ",".join(f"`{c}`" for c in cols)
            s.execute(f"SELECT {names} FROM `{t}`")
            rows = [
                tuple("[]" if (t, c) in JSON_COLUMNS and v in (None, "", b"") else v
                      for c, v in zip(cols, row))
                for row in s.fetchall()
            ]
            insert = f"INSERT INTO `{t}` ({names}) VALUES ({','.join(['%s'] * len(cols))})"
            for i in range(0, len(rows), 500):
                d.executemany(insert, rows[i:i + 500])
            d.execute(f"SELECT COUNT(*) FROM `{t}`")
            total = d.fetchone()[0]
            if total != len(rows):
                raise RuntimeError(f"{t}: XAMPP {len(rows)} dong, cloud {total} dong")
            print(f"  {t}: {total} dong")
        dst.commit()  # chi ghi khi TAT CA bang deu on
    except Exception:
        dst.rollback()
        print("Loi -> da huy toan bo, cloud chua co du lieu nao duoc ghi.")
        raise
    finally:
        d.execute("SET FOREIGN_KEY_CHECKS = 1")
        src.close()
    dst.close()
    print("XONG.")


if __name__ == "__main__":
    main()
