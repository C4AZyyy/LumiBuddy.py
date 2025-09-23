# migrate_state.py
from __future__ import annotations
import os
import argparse
import logging
from typing import Dict, Any

# Берём готовые классы из твоего адаптера
from db_adapter import FileStore, PostgresStore

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")

def migrate(src_store, dst_store) -> int:
    """Копирует всех пользователей из src в dst."""
    # Если целевой стор — Postgres, на всякий случай создадим схему
    if isinstance(dst_store, PostgresStore):
        dst_store.init_schema()

    data: Dict[str, Dict[str, Any]] = src_store.load_all()
    dst_store.save_all(data)
    return len(data)

def main():
    parser = argparse.ArgumentParser(
        description="Миграция состояния между users.json и Postgres."
    )
    parser.add_argument(
        "direction",
        choices=["import", "export"],
        help="import: файл → Postgres; export: Postgres → файл",
    )
    parser.add_argument(
        "--file",
        default=os.getenv("STATE_FILE", "users.json"),
        help="Путь к файлу состояния (по умолчанию из STATE_FILE или users.json)",
    )
    parser.add_argument(
        "--dsn",
        default=os.getenv("DATABASE_URL", ""),
        help="Строка подключения Postgres (по умолчанию из DATABASE_URL)",
    )
    args = parser.parse_args()

    if not args.dsn:
        raise SystemExit("DATABASE_URL не задан. Укажи --dsn или переменную окружения.")

    if args.direction == "import":
        # файл -> postgres
        src = FileStore(args.file)
        dst = PostgresStore(args.dsn)
        logging.info("Импорт из файла %s в Postgres…", args.file)
    else:
        # postgres -> файл (бэкап)
        src = PostgresStore(args.dsn)
        dst = FileStore(args.file)
        logging.info("Экспорт из Postgres в файл %s…", args.file)

    count = migrate(src, dst)
    logging.info("Готово. Перенесено записей: %s", count)

if __name__ == "__main__":
    main()
