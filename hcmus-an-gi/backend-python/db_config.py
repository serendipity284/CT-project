"""Cau hinh MySQL dung chung cho toan backend (XAMPP local, may trong nhom hoac cloud)."""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env", override=True)


def mysql_config() -> dict:
    cfg = {
        "host": os.getenv("MYSQL_HOST", "127.0.0.1"),
        "port": int(os.getenv("MYSQL_PORT", "3306")),
        "user": os.getenv("MYSQL_USER", "root"),
        "password": os.getenv("MYSQL_PASSWORD", ""),
        "database": os.getenv("MYSQL_DATABASE", "hcmus_an_gi"),
        "connection_timeout": 15,
        # Moi may va server deu dung gio VN de cot TIMESTAMP khong lech nhau
        "time_zone": "+07:00",
    }
    # Database cloud bat buoc TLS: dat MYSQL_SSL=true trong .env
    if os.getenv("MYSQL_SSL", "").strip().lower() in ("1", "true", "yes"):
        ca = os.getenv("MYSQL_SSL_CA", "").strip()
        if ca:
            path = Path(ca) if Path(ca).is_absolute() else BASE_DIR / ca
        else:
            import certifi  # bo chung chi goc cong khai

            path = Path(certifi.where())
        if not path.exists():
            raise RuntimeError(f"Khong thay file chung chi CA: {path}")
        cfg.update(
            ssl_ca=str(path),
            ssl_verify_cert=True,
            ssl_verify_identity=True,
            use_pure=True,
        )
    return cfg


MYSQL = mysql_config()
