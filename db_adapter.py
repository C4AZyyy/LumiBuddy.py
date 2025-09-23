# db_adapter.py
from __future__ import annotations
import os, json, logging
from typing import Dict, Any

DB_URL = os.getenv("DATABASE_URL", "").strip()
STATE_FILE = os.getenv("STATE_FILE", "users.json")


class Store:
    def init_schema(self) -> None: ...
    def load_all(self) -> Dict[str, Dict[str, Any]]: ...
    def save_all(self, users: Dict[str, Dict[str, Any]]) -> None: ...
    def is_db(self) -> bool: ...


def get_store() -> Store:
    """Выбирает Postgres при наличии DATABASE_URL, иначе — файл."""
    if DB_URL:
        try:
            import psycopg  # noqa: F401
        except Exception as e:
            logging.warning("psycopg не доступен, перехожу в файловый режим: %r", e)
            return FileStore(STATE_FILE)
        return PostgresStore(DB_URL)
    return FileStore(STATE_FILE)


# ---------- Файловое хранилище ----------

class FileStore(Store):
    def __init__(self, path: str):
        self.path = path

    def init_schema(self) -> None:
        # Для файла схемы нет
        pass

    def load_all(self) -> Dict[str, Dict[str, Any]]:
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for v in data.values():
                v.setdefault("history", [])
            return data
        except Exception:
            return {}

    def save_all(self, users: Dict[str, Dict[str, Any]]) -> None:
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(users, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logging.exception("FileStore save error: %r", e)

    def is_db(self) -> bool:
        return False


# ---------- Postgres ----------

class PostgresStore(Store):
    def __init__(self, dsn: str):
        self.dsn = dsn

    def _conn(self):
        import psycopg
        return psycopg.connect(self.dsn, autocommit=True)

    def init_schema(self) -> None:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS users(
                  chat_id         BIGINT PRIMARY KEY,
                  language        TEXT NOT NULL DEFAULT 'ru',
                  policy_shown    BOOLEAN NOT NULL DEFAULT FALSE,
                  accepted_at     TEXT,
                  free_used       INTEGER NOT NULL DEFAULT 0,
                  premium_plan    TEXT,
                  premium_until   TEXT,
                  permanent_plan  TEXT,
                  news_opt_out    BOOLEAN NOT NULL DEFAULT FALSE,
                  news_opted_at   TEXT,
                  last_support    TEXT,
                  offer_prompted  BOOLEAN NOT NULL DEFAULT FALSE,
                  offer_remind_at TEXT,
                  last_username   TEXT,
                  last_full_name  TEXT,
                  last_first_name TEXT,
                  last_last_name  TEXT
                );
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS histories(
                  chat_id BIGINT PRIMARY KEY,
                  history JSONB NOT NULL DEFAULT '[]'::jsonb
                );
                """
            )

    def load_all(self) -> Dict[str, Dict[str, Any]]:
        from psycopg.rows import dict_row
        data: Dict[str, Dict[str, Any]] = {}
        with self._conn() as conn, conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT * FROM users;")
            for r in cur.fetchall():
                cid = str(r["chat_id"])
                data[cid] = dict(r)
                data[cid].setdefault("history", [])
            cur.execute("SELECT chat_id, history FROM histories;")
            for r in cur.fetchall():
                cid = str(r["chat_id"])
                data.setdefault(cid, {})["history"] = r["history"] or []
        return data

    def save_all(self, users: Dict[str, Dict[str, Any]]) -> None:
        import json as _json
        with self._conn() as conn, conn.cursor() as cur:
            for cid, info in users.items():
                chat_id = int(cid)
                cur.execute(
                    """
                    INSERT INTO users(
                        chat_id, language, policy_shown, accepted_at, free_used,
                        premium_plan, premium_until, permanent_plan,
                        news_opt_out, news_opted_at, last_support,
                        offer_prompted, offer_remind_at,
                        last_username, last_full_name, last_first_name, last_last_name
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (chat_id) DO UPDATE SET
                        language=EXCLUDED.language,
                        policy_shown=EXCLUDED.policy_shown,
                        accepted_at=EXCLUDED.accepted_at,
                        free_used=EXCLUDED.free_used,
                        premium_plan=EXCLUDED.premium_plan,
                        premium_until=EXCLUDED.premium_until,
                        permanent_plan=EXCLUDED.permanent_plan,
                        news_opt_out=EXCLUDED.news_opt_out,
                        news_opted_at=EXCLUDED.news_opted_at,
                        last_support=EXCLUDED.last_support,
                        offer_prompted=EXCLUDED.offer_prompted,
                        offer_remind_at=EXCLUDED.offer_remind_at,
                        last_username=EXCLUDED.last_username,
                        last_full_name=EXCLUDED.last_full_name,
                        last_first_name=EXCLUDED.last_first_name,
                        last_last_name=EXCLUDED.last_last_name;
                    """,
                    (
                        chat_id,
                        info.get("language") or "ru",
                        bool(info.get("policy_shown", False)),
                        info.get("accepted_at"),
                        int(info.get("free_used", 0)),
                        info.get("premium_plan"),
                        info.get("premium_until"),
                        info.get("permanent_plan"),
                        bool(info.get("news_opt_out", False)),
                        info.get("news_opted_at"),
                        info.get("last_support"),
                        bool(info.get("offer_prompted", False)),
                        info.get("offer_remind_at"),
                        info.get("last_username"),
                        info.get("last_full_name"),
                        info.get("last_first_name"),
                        info.get("last_last_name"),
                    ),
                )
                cur.execute(
                    """
                    INSERT INTO histories(chat_id, history)
                    VALUES (%s, %s)
                    ON CONFLICT (chat_id) DO UPDATE SET history = EXCLUDED.history;
                    """,
                    (chat_id, _json.dumps(info.get("history") or [])),
                )

    def is_db(self) -> bool:
        return True
