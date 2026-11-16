"""Server tərəfli rol əsaslı giriş (demo): hesab yoxlaması, yaddaşda token sessiyaları və rol asılılıqları.

Qeyd: sessiyalar proses yaddaşındadır (server yenidən başlayanda silinir, bir proses üçündür).
Hesablar .env-dən dəyişdirilə bilər (DEMO_EMPLOYEE_*, DEMO_MANAGER_*); verilməyibsə README-dəki demo dəyərlər işləyir.
IDE genişləndirməsi və simulyator işçi kimi deyil, INGEST_KEY gizli açarı (X-Ingest-Key başlığı) ilə daxil olur.
"""
import hmac
import os
import secrets
import threading
import time
from collections import deque
from typing import Optional

from fastapi import Depends, Header, HTTPException

TOKEN_TTL = 8 * 3600  # saniyə
_sessions: dict = {}  # token -> {"role", "email", "exp"}

# Brute-force qoruması: IP limitindən (ratelimit.py) əlavə, hesab üzrə və ümumi uğursuz cəhd sayğacı.
# Bir e-poçta 15 dəqiqədə 5 səhv cəhd -> həmin hesab 15 dəqiqə kilidlənir (IP dəyişsə də).
# Bütün hesablara 15 dəqiqədə 50 səhv cəhd -> giriş müvəqqəti hamı üçün dayanır (paylanmış hücum).
LOCK_WINDOW = 15 * 60
MAX_FAILS_PER_ACCOUNT = 5
MAX_FAILS_GLOBAL = 50
_fails: dict = {}  # normallaşdırılmış e-poçt -> deque[vaxt]
_fails_all: deque = deque()
_fails_lock = threading.Lock()


def _accounts() -> dict:
    return {
        "employee": (os.environ.get("DEMO_EMPLOYEE_EMAIL", "dev@company.com"),
                     os.environ.get("DEMO_EMPLOYEE_PASSWORD", "emp123")),
        "manager": (os.environ.get("DEMO_MANAGER_EMAIL", "manager@company.com"),
                    os.environ.get("DEMO_MANAGER_PASSWORD", "admin123")),
    }


def uses_default_passwords() -> bool:
    """DEMO_*_PASSWORD təyin olunmayıbsa README-dəki ictimai demo parolları işləyir."""
    return not (os.environ.get("DEMO_EMPLOYEE_PASSWORD") and os.environ.get("DEMO_MANAGER_PASSWORD"))


def employee_ref() -> str:
    """Demo işçi hesabının IDE hadisələrindəki təxəllüslü istinadı."""
    return os.environ.get("DEMO_EMPLOYEE_REF", "dev_a91f")


def _same(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


def _purge() -> None:
    now = time.time()
    for t in [t for t, s in _sessions.items() if s["exp"] <= now]:
        _sessions.pop(t, None)


def _trim(q: deque, now: float) -> None:
    while q and q[0] <= now - LOCK_WINDOW:
        q.popleft()


def _locked(key: str) -> bool:
    now = time.time()
    with _fails_lock:
        _trim(_fails_all, now)
        q = _fails.get(key)
        if q is not None:
            _trim(q, now)
            if not q:
                _fails.pop(key, None)
        return len(_fails_all) >= MAX_FAILS_GLOBAL or (q is not None and len(q) >= MAX_FAILS_PER_ACCOUNT)


def _record_fail(key: str) -> None:
    now = time.time()
    with _fails_lock:
        if len(_fails) > 10_000:  # yaddaş sərhədi
            _fails.clear()
        _fails.setdefault(key, deque()).append(now)
        _fails_all.append(now)


def reset_lockouts() -> None:
    """Testlər üçün."""
    with _fails_lock:
        _fails.clear()
        _fails_all.clear()


def login(email: str, password: str, role: Optional[str]) -> dict:
    """Doğru e-poçt+parol -> token. Səhv məlumat 401, rol uyğunsuzluğu 403, kilid 429 verir."""
    key = email.strip().lower()
    if _locked(key):
        raise HTTPException(429, "çox sayda uğursuz cəhd, 15 dəqiqə sonra yenidən cəhd edin",
                            headers={"Retry-After": str(LOCK_WINDOW)})
    found = None
    for acc_role, (acc_email, acc_pass) in _accounts().items():
        ok_mail = _same(email.strip().lower(), acc_email.lower())
        ok_pass = _same(password, acc_pass)
        if ok_mail and ok_pass:
            found = (acc_role, acc_email)
    if not found:
        _record_fail(key)
        raise HTTPException(401, "səhv e-poçt və ya parol")
    with _fails_lock:
        _fails.pop(key, None)
    if role and role != found[0]:
        raise HTTPException(403, "bu hesab həmin panelə aid deyil")
    _purge()
    token = secrets.token_urlsafe(32)
    _sessions[token] = {"role": found[0], "email": found[1], "exp": time.time() + TOKEN_TTL,
                        "developer_ref": employee_ref() if found[0] == "employee" else None}
    return {"token": token, "role": found[0], "email": found[1]}


def _bearer(authorization: Optional[str]) -> Optional[str]:
    if not authorization:
        return None
    scheme, _, value = authorization.partition(" ")
    return value.strip() if scheme.lower() == "bearer" and value.strip() else None


def session_of(authorization: Optional[str]) -> Optional[dict]:
    token = _bearer(authorization)
    s = _sessions.get(token) if token else None
    if s and s["exp"] <= time.time():
        _sessions.pop(token, None)
        return None
    return s


def logout(authorization: Optional[str]) -> None:
    token = _bearer(authorization)
    if token:
        _sessions.pop(token, None)


def optional_session(authorization: Optional[str] = Header(default=None)) -> Optional[dict]:
    return session_of(authorization)


def require_manager(session: Optional[dict] = Depends(optional_session)) -> dict:
    if not session:
        raise HTTPException(401, "giriş tələb olunur", headers={"WWW-Authenticate": "Bearer"})
    if session["role"] != "manager":
        raise HTTPException(403, "bu əməliyyat yalnız menecer üçündür")
    return session


def has_ingest_key(value: Optional[str]) -> bool:
    """INGEST_KEY təyin olunmayıbsa heç bir açar qəbul edilmir (fail-closed)."""
    key = os.environ.get("INGEST_KEY", "")
    return bool(key and value and _same(value, key))


def require_ingest(x_ingest_key: Optional[str] = Header(default=None)) -> None:
    if not has_ingest_key(x_ingest_key):
        raise HTTPException(401, "IDE açarı (X-Ingest-Key) tələb olunur")


def caller(session: Optional[dict] = Depends(optional_session),
           x_ingest_key: Optional[str] = Header(default=None)) -> dict:
    return {"ingest": has_ingest_key(x_ingest_key), "session": session}


def developer_ref(c: dict, requested: Optional[str]) -> str:
    """Sorğunun kimin adından olduğunu müəyyən edir.

    IDE açarı ilə gələn sorğu istənilən developer_ref göstərə bilər; işçi isə yalnız öz sessiyasındakı ref ilə işləyir.
    """
    if c["ingest"]:
        if not requested:
            raise HTTPException(422, "developer_ref tələb olunur")
        return requested
    s = c["session"]
    if not s:
        raise HTTPException(401, "giriş tələb olunur", headers={"WWW-Authenticate": "Bearer"})
    if s["role"] != "employee":
        raise HTTPException(403, "bu əməliyyat yalnız işçi üçündür")
    if requested and requested != s["developer_ref"]:
        raise HTTPException(403, "başqa developerin məlumatına giriş yoxdur")
    return s["developer_ref"]


def require_manager_or_ingest(c: dict = Depends(caller)) -> dict:
    if c["ingest"]:
        return c
    return require_manager(c["session"])
