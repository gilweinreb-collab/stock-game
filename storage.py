"""שכבות אחסון למצב המשחק: קובץ JSON מקומי או Supabase (דרך REST, בלי ספריות נוספות).

כל backend מממש:
    load() -> (state_dict | None, rev)
    save(state_dict, rev) -> None      # מעלה ConflictError אם מישהו אחר שמר בינתיים
"""
from __future__ import annotations

import json
import os
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path


class ConflictError(Exception):
    """מישהו אחר עדכן את המצב בין הטעינה לשמירה."""


class StorageError(Exception):
    """תקלה באחסון (הודעה בעברית שמתאימה להצגה למשתמש)."""


# ---------------------------------------------------------------- קובץ מקומי
class FileBackend:
    name = "קובץ מקומי"

    def __init__(self, path: Path):
        self.path = Path(path)

    def load(self):
        if not self.path.exists():
            return None, 0
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                return json.load(f), 0
        except json.JSONDecodeError as e:
            backup = self.path.with_suffix(f".corrupt-{int(time.time())}.json")
            os.replace(self.path, backup)   # לא מוחקים קובץ פגום
            raise StorageError(f"קובץ הנתונים היה פגום ונשמר בשם {backup.name}. רעננו כדי להתחיל משחק חדש.") from e

    def save(self, state: dict, rev: int) -> None:
        """כתיבה אטומית: קובץ זמני ואז החלפה. ההגנה מפני כתיבה בו-זמנית היא הנעילה בתהליך (engine.LOCK)."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, prefix=".tmp_game_", suffix=".json")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self.path)
        except BaseException:
            if os.path.exists(tmp):
                os.remove(tmp)
            raise


# ---------------------------------------------------------------- Supabase
class SupabaseBackend:
    """שורה אחת (id=1) בטבלה game_state: data (jsonb) ו-rev (מספר גרסה).
    שמירה היא PATCH עם תנאי rev=eq.<הגרסה שטענו>, ולכן אם מישהו הקדים אותנו לא נדרוס אותו."""

    name = "Supabase"
    TABLE = "game_state"
    ROW_ID = 1
    TIMEOUT = 15

    def __init__(self, url: str, key: str, session=None):
        import requests

        self.base = url.rstrip("/") + f"/rest/v1/{self.TABLE}"
        self.s = session or requests.Session()
        headers = {"apikey": key, "Content-Type": "application/json"}
        if key.startswith("eyJ"):   # מפתח JWT ישן; מפתחות sb_secret_... נשלחים רק ב-apikey
            headers["Authorization"] = f"Bearer {key}"
        self.s.headers.update(headers)

    def _call(self, method: str, url: str, **kw):
        try:
            r = self.s.request(method, url, timeout=self.TIMEOUT, **kw)
        except Exception as e:  # רשת, DNS, timeout
            raise StorageError("אין חיבור לבסיס הנתונים. נסו שוב בעוד רגע.") from e
        return r

    def load(self):
        r = self._call("GET", self.base, params={"id": f"eq.{self.ROW_ID}", "select": "data,rev"})
        if r.status_code != 200:
            raise StorageError(f"שגיאת בסיס נתונים ({r.status_code}). בדקו את ה-URL והמפתח ב-secrets ואת יצירת הטבלה.")
        rows = r.json()
        if not rows:
            return None, 0
        return rows[0]["data"], int(rows[0]["rev"])

    def save(self, state: dict, rev: int) -> None:
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        if rev == 0:   # יצירה ראשונה; אם מישהו יצר במקביל נקבל 409
            r = self._call("POST", self.base, headers={"Prefer": "return=minimal"},
                           json={"id": self.ROW_ID, "data": state, "rev": 1, "updated_at": now})
            if r.status_code == 409:
                raise ConflictError()
            if r.status_code not in (200, 201, 204):
                raise StorageError(f"שמירה נכשלה ({r.status_code}).")
            return
        r = self._call("PATCH", self.base, headers={"Prefer": "return=representation"},
                       params={"id": f"eq.{self.ROW_ID}", "rev": f"eq.{rev}"},
                       json={"data": state, "rev": rev + 1, "updated_at": now})
        if r.status_code not in (200, 204):
            raise StorageError(f"שמירה נכשלה ({r.status_code}).")
        if r.status_code == 200 and not r.json():
            raise ConflictError()


def default_backend(default_file: Path):
    url, key = os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_SERVICE_KEY")
    if url and key:
        return SupabaseBackend(url, key)
    return FileBackend(Path(os.environ.get("PAPER_DATA_FILE", default_file)))
