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
        # No schema for file mode
        pass

    def load_all(self) -> List[Dict[str, Any]]:
        """
        Возвращает список словарей пользователей из users.json.
        Формат ожидается { "<chat_id>": { ... } }.
        """
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
            # иногда файл уже в виде списка
            for item in data:
                if isinstance(item, dict) and "chat_id" in item:
                    out.append(item)
        return out

    # Вспомогательная функция, которой пользуется авто-миграция в нашем коде ниже.
    def load_users_from_file(self) -> Iterable[Dict[str, Any]]:
        return self.load_all()


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
                # base table
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS users (
                        chat_id BIGINT PRIMARY KEY
                    );
                    """
                )

                # idempotent column adds (safe if they already exist)
                cur.execute(
                    """
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

                      -- new fields used by current code
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

                      -- payment fields
                      ADD COLUMN IF NOT EXISTS premium_source             TEXT        NULL,
                      ADD COLUMN IF NOT EXISTS premium_started_at         TIMESTAMPTZ NULL,
                      ADD COLUMN IF NOT EXISTS premium_payment_method     TEXT        NULL,
                      ADD COLUMN IF NOT EXISTS premium_payment_reference  TEXT        NULL
                    ;
                    """
                )
            conn.commit()

    def load_all(self) -> List[Dict[str, Any]]:
        """
        Возвращает список словарей пользователей из таблицы users.
        """
        psycopg = self.psycopg
        out: List[Dict[str, Any]] = []
        with psycopg.connect(self.url) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM users;")
                cols = [desc.name if hasattr(desc, "name") else desc[0] for desc in cur.description]
                for row in cur.fetchall():
                    d = dict(zip(cols, row))
                    out.append(d)
        return out

    def bulk_upsert_users(self, rows: Iterable[Dict[str, Any]]) -> int:
        psycopg = self.psycopg
        count = 0
        with psycopg.connect(self.url) as conn:
            with conn.cursor() as cur:
                for r in rows:
                    if "chat_id" not in r:
                        continue
                    chat_id = int(r.get("chat_id"))

                    # фильтруем ключи под понятные колонкам имена
                    # (если вдруг в файле были лишние поля — Postgres их не знает)
                    # Тут допускаем все поля — ALTER уже добавил нужные колонки.
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
    Если включена БД — забираем всех пользователей из файла и заливаем в Postgres.
    В Lumi.py это вызывается после db_init().
    """
    if isinstance(store, DbStore):
        file_store = FileStore()
        rows = list(file_store.load_all())
        if rows:
            inserted = store.bulk_upsert_users(rows)
            print(f">>> migrated {inserted} users from file to DB", flush=True)
        else:
            print(">>> no users.json or it is empty — nothing to migrate", flush=True)
