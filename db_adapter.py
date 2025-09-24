# db_adapter.py
import os
import json
from typing import Iterable, Dict, Any, List

DB_URL = os.getenv("DATABASE_URL", "").strip()
STATE_FILE = os.getenv("STATE_FILE", "users.json")


# ---------- File store ----------
class FileStore:
    def __init__(self, path: str | None = None):
        self.path = path or STATE_FILE

    def is_db(self) -> bool:
        return False

    def init_schema(self) -> None:
        pass  # нет схемы для файлового режима

    def load_all(self) -> List[Dict[str, Any]]:
        if not os.path.exists(self.path):
            return []
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}

        out: List[Dict[str, Any]] = []
        if isinstance(data, dict):
            for k, v in data.items():
                try:
                    chat_id = int(k)
                except Exception:
                    continue
                row = {"chat_id": chat_id}
                if isinstance(v, dict):
                    row.update(v)
                out.append(row)
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and "chat_id" in item:
                    out.append(item)
        return out

    # для совместимости со старым кодом миграции
    def load_users_from_file(self) -> Iterable[Dict[str, Any]]:
        return self.load_all()

    # НОВОЕ: сохранить всех пользователей в файл (если где-то вызывается store.save_all)
    def save_all(self, users: List[Dict[str, Any]]) -> None:
        data = {}
        for u in users or []:
            if "chat_id" not in u:
                continue
            cid = str(int(u["chat_id"]))
            # не пишем chat_id в тело — он ключ
            data[cid] = {k: v for k, v in u.items() if k != "chat_id"}
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


# ---------- Postgres store ----------
class DbStore:
    def __init__(self, url: str):
        import psycopg  # v3
        self.psycopg = psycopg
        self.url = url

    def is_db(self) -> bool:
        return True

    def init_schema(self) -> None:
        psycopg = self.psycopg
        with psycopg.connect(self.url) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        chat_id BIGINT PRIMARY KEY
                    );
                """)
                cur.execute("""
                    ALTER TABLE users
                      ADD COLUMN IF NOT EXISTS language                   TEXT,
                      ADD COLUMN IF NOT EXISTS policy_shown               BOOLEAN     DEFAULT FALSE,
                      ADD COLUMN IF NOT EXISTS accepted_at                TIMESTAMPTZ,
                      ADD COLUMN IF NOT EXISTS free_used                  INTEGER     DEFAULT 0,
                      ADD COLUMN IF NOT EXISTS premium_plan               TEXT,
                      ADD COLUMN IF NOT EXISTS premium_until              TIMESTAMPTZ,
                      ADD COLUMN IF NOT EXISTS permanent_plan             TEXT,
                      ADD COLUMN IF NOT EXISTS news_opt_out               BOOLEAN     DEFAULT FALSE,
                      ADD COLUMN IF NOT EXISTS news_opted_at              TIMESTAMPTZ,
                      ADD COLUMN IF NOT EXISTS history                    JSONB       DEFAULT '[]'::jsonb,
                      ADD COLUMN IF NOT EXISTS offer_prompted             BOOLEAN     NOT NULL DEFAULT FALSE,
                      ADD COLUMN IF NOT EXISTS offer_remind_at            TIMESTAMPTZ NULL,
                      ADD COLUMN IF NOT EXISTS abuse_strikes              INTEGER     NOT NULL DEFAULT 0,
                      ADD COLUMN IF NOT EXISTS lyrics_expected            BOOLEAN     NOT NULL DEFAULT FALSE,
                      ADD COLUMN IF NOT EXISTS last_seen_at               TIMESTAMPTZ NULL,
                      ADD COLUMN IF NOT EXISTS last_username              TEXT        NULL,
                      ADD COLUMN IF NOT EXISTS last_first_name            TEXT        NULL,
                      ADD COLUMN IF NOT EXISTS last_last_name             TEXT        NULL,
                      ADD COLUMN IF NOT EXISTS last_full_name             TEXT        NULL,
                      ADD COLUMN IF NOT EXISTS last_vent_at               TIMESTAMPTZ NULL,
                      ADD COLUMN IF NOT EXISTS last_vent_note             TEXT        NULL,
                      ADD COLUMN IF NOT EXISTS premium_source             TEXT        NULL,
                      ADD COLUMN IF NOT EXISTS premium_started_at         TIMESTAMPTZ NULL,
                      ADD COLUMN IF NOT EXISTS premium_payment_method     TEXT        NULL,
                      ADD COLUMN IF NOT EXISTS premium_payment_reference  TEXT        NULL
                ;
                """)
            conn.commit()

# сразу после большого ALTER TABLE users ... ADD COLUMN ...
cur.execute("ALTER TABLE users ALTER COLUMN language SET DEFAULT 'ru';")
cur.execute("UPDATE users SET language = COALESCE(language, 'ru');")
cur.execute("ALTER TABLE users ALTER COLUMN language DROP NOT NULL;")

    
    def load_all(self) -> List[Dict[str, Any]]:
        psycopg = self.psycopg
        out: List[Dict[str, Any]] = []
        with psycopg.connect(self.url) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM users;")
                cols = [d.name if hasattr(d, "name") else d[0] for d in cur.description]
                for row in cur.fetchall():
                    out.append(dict(zip(cols, row)))
        return out

def bulk_upsert_users(self, rows: Iterable[Dict[str, Any]]) -> int:
    psycopg = self.psycopg
    default_lang = (os.getenv("DEFAULT_LANGUAGE", "ru") or "ru").lower()
    count = 0
    with psycopg.connect(self.url) as conn:
        with conn.cursor() as cur:
            for r in rows:
                if "chat_id" not in r:
                    continue

                # 🔧 дефолты, чтобы не слать NULL куда не надо
                if not r.get("language"):
                    r["language"] = default_lang
                if r.get("history") is None:
                    r["history"] = []  # jsonb

                cols = list(r.keys())
                vals = [r[k] for k in cols]
                placeholders = ", ".join(["%s"] * len(vals))
                columns = ", ".join(cols)
                updates = ", ".join([f"{k}=EXCLUDED.{k}" for k in cols if k != "chat_id"])

                cur.execute(
                    f"INSERT INTO users ({columns}) VALUES ({placeholders}) "
                    f"ON CONFLICT (chat_id) DO UPDATE SET {updates};",
                    vals,
                )
                count += 1
        conn.commit()
    return count


    # НОВОЕ: совместимость с кодом, который вызывает store.save_all(...)
    def save_all(self, users: List[Dict[str, Any]]) -> None:
        # просто апсертим всё в БД
        self.bulk_upsert_users(users or [])


# ---------- factory & helpers ----------
def get_store():
    if DB_URL:
        return DbStore(DB_URL)
    return FileStore()

store = get_store()

def db_init() -> None:
    store.init_schema()

def auto_migrate_file_to_db() -> None:
    """
    Если включена БД — читаем всех из файла и апсертим в Postgres.
    Совместимо с проектами, где load_all/save_all ожидаются у стора.
    """
    if isinstance(store, DbStore):
        file_store = FileStore()
        rows = list(file_store.load_all())
        if rows:
            inserted = store.bulk_upsert_users(rows)
            print(f">>> migrated {inserted} users from file to DB", flush=True)
        else:
            print(">>> no users.json or it is empty — nothing to migrate", flush=True)
