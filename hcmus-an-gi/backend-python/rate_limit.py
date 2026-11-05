"""Rate limit in-memory cho POST /places/contribute."""
from __future__ import annotations
import threading
import time
from collections import defaultdict, deque
from typing import Deque, Dict, Tuple

_lock = threading.Lock()
_user_events: Dict[str, Deque[float]] = defaultdict(deque)
_ip_events: Dict[str, Deque[float]] = defaultdict(deque)
_user_last: Dict[str, float] = {}
_queue_depth = 0
_queue_lock = threading.Lock()

COOLDOWN_SEC = 60
USER_DAILY_MAX = 10
IP_HOURLY_MAX = 30
WINDOW_DAY = 24 * 3600
WINDOW_HOUR = 3600

def _prune(dq: Deque[float], window: float, now: float) -> None:
    while dq and now - dq[0] > window:
        dq.popleft()

def check_contribute_allowed(user_id: str, ip: str) -> Tuple[bool, str]:
    now = time.time()
    with _lock:
        last = _user_last.get(user_id)
        if last is not None and now - last < COOLDOWN_SEC:
            wait = int(COOLDOWN_SEC - (now - last)) + 1
            return False, f"Dang qua nhanh. Thu lai sau {wait}s (chong spam)."
        uq = _user_events[user_id]
        _prune(uq, WINDOW_DAY, now)
        if len(uq) >= USER_DAILY_MAX:
            return False, f"Vuot gioi han {USER_DAILY_MAX} quan / ngay / tai khoan."
        iq = _ip_events[ip or "unknown"]
        _prune(iq, WINDOW_HOUR, now)
        if len(iq) >= IP_HOURLY_MAX:
            return False, f"IP nay da gui qua {IP_HOURLY_MAX} request / gio."
        return True, ""

def record_contribute(user_id: str, ip: str) -> None:
    now = time.time()
    with _lock:
        _user_last[user_id] = now
        _user_events[user_id].append(now)
        _ip_events[ip or "unknown"].append(now)

def queue_enter() -> int:
    global _queue_depth
    with _queue_lock:
        _queue_depth += 1
        return _queue_depth

def queue_leave() -> None:
    global _queue_depth
    with _queue_lock:
        _queue_depth = max(0, _queue_depth - 1)

def queue_stats() -> dict:
    with _queue_lock:
        depth = _queue_depth
    with _lock:
        return {
            "queue_depth": depth,
            "tracked_users": len(_user_events),
            "cooldown_sec": COOLDOWN_SEC,
            "user_daily_max": USER_DAILY_MAX,
            "ip_hourly_max": IP_HOURLY_MAX,
        }
