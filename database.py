import os
import json
import time
import logging
import sqlite3
from datetime import datetime

logger = None  # устанавливается из main.py после инициализации логирования

DEBUG_LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "debug-2a8cbc.log")
DEBUG_SESSION_ID = "2a8cbc"


def _agent_debug_log(hypothesis_id: str, message: str, data: dict | None = None, run_id: str = "run1") -> None:
    try:
        ts_ms = int(time.time() * 1000)
        payload = {
            "sessionId": DEBUG_SESSION_ID,
            "id": f"log_{ts_ms}",
            "timestamp": ts_ms,
            "location": "main.py",
            "message": message,
            "data": data or {},
            "runId": run_id,
            "hypothesisId": hypothesis_id,
        }
        with open(DEBUG_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception as e:
        if logger:
            logger.debug("Debug log write failed: %s", e)


class DatabaseManager:
    def __init__(self, path: str):
        self.path = path
        try:
            self.conn = sqlite3.connect(self.path)
            self.conn.row_factory = sqlite3.Row
            self._init_db()
        except Exception as e:
            if logger:
                logger.exception("Database init failed: %s", e)
            raise

    def _init_db(self):
        cur = self.conn.cursor()

        # Подразделения
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS units (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL
            )
            """
        )

        # Категории имущества
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL
            )
            """
        )
        for cat in ("ЛТО", "ПДИ", "Высотное снаряжение", "Чехлы и палатки"):
            cur.execute("INSERT OR IGNORE INTO categories(name) VALUES (?)", (cat,))

        # Изделия
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                base_code TEXT NOT NULL,
                uom TEXT NOT NULL,
                type TEXT NOT NULL CHECK (type IN ('qty', 'serial'))
            )
            """
        )

        # Варианты (размеры)
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS variants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
                size_name TEXT NOT NULL,
                full_code TEXT NOT NULL UNIQUE
            )
            """
        )

        # Количественный учет (материальные средства)
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS stock_qty (
                variant_id INTEGER PRIMARY KEY REFERENCES variants(id) ON DELETE CASCADE,
                quantity INTEGER NOT NULL DEFAULT 0
            )
            """
        )

        # Серийный учет (основные средства)
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS stock_serial (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                variant_id INTEGER NOT NULL REFERENCES variants(id) ON DELETE CASCADE,
                factory_sn TEXT NOT NULL UNIQUE
            )
            """
        )

        # Журнал операций
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS journal (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                op_type TEXT NOT NULL CHECK (op_type IN ('IN','OUT')),
                variant_id INTEGER NOT NULL REFERENCES variants(id),
                quantity INTEGER,
                factory_sn TEXT,
                unit_id INTEGER REFERENCES units(id),
                doc_name TEXT
            )
            """
        )

        # Audit log для критичных операций (приоритет 2)
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                action TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                entity_id INTEGER,
                details TEXT
            )
            """
        )

        # Заполним пару подразделений по умолчанию
        cur.execute("INSERT OR IGNORE INTO units(name) VALUES (?)", ("Склад-основной",))
        cur.execute("INSERT OR IGNORE INTO units(name) VALUES (?)", ("Цех-1",))

        self.conn.commit()

        # Миграция: добавляем поле doc_name в journal, если его нет (старые БД)
        cur.execute("PRAGMA table_info(journal)")
        cols = [r[1] for r in cur.fetchall()]
        if "doc_name" not in cols:
            cur.execute("ALTER TABLE journal ADD COLUMN doc_name TEXT")
            self.conn.commit()

        # Миграция: добавляем поле category_id в items, если его нет (старые БД)
        cur.execute("PRAGMA table_info(items)")
        item_cols = [r[1] for r in cur.fetchall()]
        if "category_id" not in item_cols:
            cur.execute("ALTER TABLE items ADD COLUMN category_id INTEGER REFERENCES categories(id)")
            self.conn.commit()

        # region agent log
        _agent_debug_log(
            hypothesis_id="H3",
            message="Database initialized",
            data={"db_path": self.path},
        )
        # endregion

        # Если справочник пустой – заполняем образцами
        cur.execute("SELECT COUNT(*) AS cnt FROM items")
        row = cur.fetchone()
        if row and row["cnt"] == 0:
            self._seed_sample_data()

    def _seed_sample_data(self):
        cur = self.conn.cursor()

        cur.execute("SELECT id, name FROM categories")
        cat_by_name = {r["name"]: r["id"] for r in cur.fetchall()}

        # Вспомогательная функция: вставка изделия + вариантов
        def add_item(name, base_code, uom, itype, cat_name, variants):
            """variants: list of (size_name, full_code_10digits)"""
            cat_id = cat_by_name.get(cat_name)
            cur.execute(
                "INSERT INTO items(name, base_code, uom, type, category_id) VALUES (?,?,?,?,?)",
                (name, base_code, uom, itype, cat_id),
            )
            iid = cur.lastrowid
            for size_name, full_code in variants:
                cur.execute(
                    "INSERT INTO variants(item_id, size_name, full_code) VALUES (?,?,?)",
                    (iid, size_name, full_code),
                )
                vid = cur.lastrowid
                if itype == "qty":
                    cur.execute("INSERT INTO stock_qty(variant_id, quantity) VALUES (?,0)", (vid,))

        # ── ЛТО — одежда (размерный ряд, qty) ───────────────────────────────
        SIZES_C = ["44-170", "46-170", "48-176", "50-176", "52-182", "54-182", "56-188", "58-188"]
        SIZES_F = ["39", "40", "41", "42", "43", "44", "45", "46"]

        def variants_sized(base10, sizes):
            return [(s, base10[:8] + f"{i+1:02d}") for i, s in enumerate(sizes)]

        lto_clothing = [
            ("Костюм лётный летний",             "1776000101", "шт", SIZES_C),
            ("Костюм лётный зимний",             "1776000201", "шт", SIZES_C),
            ("Куртка лётная демисезонная",        "1776000301", "шт", SIZES_C),
            ("Куртка лётная зимняя утеплённая",   "1776000401", "шт", SIZES_C),
            ("Брюки лётные летние",               "1776000501", "шт", SIZES_C),
            ("Брюки лётные зимние",               "1776000601", "шт", SIZES_C),
            ("Комбинезон лётный лёгкий",          "1776000701", "шт", SIZES_C),
            ("Комбинезон технический",            "1776000801", "шт", SIZES_C),
            ("Рубашка форменная длинный рукав",   "1776000901", "шт", SIZES_C),
            ("Рубашка форменная короткий рукав",  "1776001001", "шт", SIZES_C),
            ("Майка форменная",                   "1776001101", "шт", SIZES_C),
            ("Кепи форменное летнее",             "1776001201", "шт", SIZES_C),
            ("Кепи форменное зимнее",             "1776001301", "шт", SIZES_C),
            ("Берет форменный",                   "1776001401", "шт", SIZES_C),
            ("Пилотка",                           "1776001501", "шт", SIZES_C),
            ("Шапка-ушанка меховая",              "1776001601", "шт", SIZES_C),
            ("Перчатки лётные кожаные",           "1776001701", "шт", SIZES_C),
            ("Перчатки зимние утеплённые",        "1776001801", "шт", SIZES_C),
            ("Шарф форменный шерстяной",          "1776001901", "шт", SIZES_C),
            ("Галстук форменный",                 "1776002001", "шт", SIZES_C),
            ("Ремень поясной форменный",          "1776002101", "шт", SIZES_C),
            ("Носки форменные хлопок",            "1776002201", "шт", SIZES_C),
            ("Носки форменные шерстяные",         "1776002301", "шт", SIZES_C),
            ("Нательное бельё комплект летний",   "1776002401", "шт", SIZES_C),
            ("Нательное бельё комплект зимний",   "1776002501", "шт", SIZES_C),
        ]
        lto_footwear = [
            ("Ботинки лётные хромовые",   "1776100101", "пар", SIZES_F),
            ("Сапоги форменные хромовые", "1776100201", "пар", SIZES_F),
            ("Полуботинки форменные",     "1776100301", "пар", SIZES_F),
            ("Ботинки зимние утеплённые", "1776100401", "пар", SIZES_F),
        ]

        for name, base10, uom, sizes in lto_clothing:
            add_item(name, base10, uom, "qty", "ЛТО", variants_sized(base10, sizes))
        for name, base10, uom, sizes in lto_footwear:
            add_item(name, base10, uom, "qty", "ЛТО", variants_sized(base10, sizes))

        # ── ПДИ — серийный учёт ──────────────────────────────────────────────
        pdi_items = [
            ("Парашют десантный Д-10",           "9306000101"),
            ("Парашют десантный Д-6 серия 4",    "9306000201"),
            ("Парашют запасной З-5",             "9306000301"),
            ("Парашют запасной З-6П",            "9306000401"),
            ("Страховочный прибор ППК-У",        "9306000501"),
            ("Страховочный прибор ППКУ-165А",    "9306000601"),
            ("Ранец парашюта основной",          "9306000701"),
            ("Ранец парашюта запасной",          "9306000801"),
            ("Карабин страховочный десантный",   "9306000901"),
            ("Грузовой контейнер УГКП-500",      "9306001001"),
            ("Подвесная система ПС-Д10",         "9306001101"),
            ("Вытяжной фал 15м",                 "9306001201"),
            ("Кольцо вытяжного троса",           "9306001301"),
            ("Шпилька предохранительная",        "9306001401"),
            ("Соединительное звено",             "9306001501"),
            ("Слинг стропы 7мм",                 "9306001601"),
            ("Чехол стабилизирующего купола",    "9306001701"),
            ("Укладочная доска",                 "9306001801"),
            ("Прибор контроля укладки",          "9306001901"),
            ("Сумка укладчика",                  "9306002001"),
            ("Журнал контроля парашюта",         "9306002101"),
            ("Паспорт парашюта",                 "9306002201"),
        ]
        for name, base10 in pdi_items:
            add_item(name, base10, "шт", "serial", "ПДИ", [("Без размера", base10)])

        # ── Высотное снаряжение ──────────────────────────────────────────────
        high_serial = [
            ("Каска альпинистская PETZL Vertex",            "6506000101"),
            ("Каска защитная CAMP Ares",                    "6506000201"),
            ("Беседка страховочная Singing Rock",           "6506000301"),
            ("Беседка комбинированная CAMP Jasper CR3",     "6506000401"),
            ("Жумар левый PETZL Ascension",                 "6506000501"),
            ("Жумар правый PETZL Ascension",                "6506000601"),
            ("Рюкзак-контейнер для верёвки 70л",            "6506000701"),
            ("Спусковое устройство PETZL Pirana",           "6506000801"),
            ("Спусковое устройство CAMP Raft",              "6506000901"),
            ("Тянущее устройство PETZL BASIC",              "6506001001"),
            ("Блок-ролик одинарный PETZL Fixe",             "6506001101"),
            ("Блок-ролик двойной PETZL Tandem",             "6506001201"),
            ("Страховочное устройство PETZL GriGri",        "6506001301"),
            ("Карабин D-образный муфтованный",              "6506001401"),
            ("Карабин HMS муфтованный",                     "6506001501"),
        ]
        high_qty = [
            ("Верёвка статическая 10мм (бухта 50м)",  "5607000101", "м"),
            ("Верёвка статическая 11мм (бухта 50м)",  "5607000201", "м"),
            ("Верёвка динамическая 9мм (бухта 60м)",  "5607000301", "м"),
            ("Стропа петлевая 16мм (бухта 50м)",      "5607000401", "м"),
            ("Репшнур 6мм (бухта 30м)",               "5607000501", "м"),
            ("Петля готовая из стропы 120см",         "5607000601", "шт"),
            ("Лента стропа 25мм (бухта 50м)",         "5607000701", "м"),
        ]
        for name, base10 in high_serial:
            add_item(name, base10, "шт", "serial", "Высотное снаряжение", [("Без размера", base10)])
        for name, base10, uom in high_qty:
            add_item(name, base10, uom, "qty", "Высотное снаряжение", [("Без размера", base10)])

        # ── Чехлы и палатки — qty ────────────────────────────────────────────
        tents_items = [
            ("Палатка армейская 2-местная УСБ-56",   "6301000101", "шт"),
            ("Палатка армейская 4-местная ПБ-1",     "6301000201", "шт"),
            ("Палатка 10-местная ПУС-2",             "6301000301", "шт"),
            ("Палатка командно-штабная КШМ-4",       "6301000401", "шт"),
            ("Тент армейский маскировочный 12×12м",  "6301000501", "шт"),
            ("Тент армейский защитный 6×9м",         "6301000601", "шт"),
            ("Чехол для парашюта Д-10",              "6301000701", "шт"),
            ("Чехол для парашюта З-5",               "6301000801", "шт"),
            ("Чехол для карабина АКМ",               "6301000901", "шт"),
            ("Чехол для карабина АК-74",             "6301001001", "шт"),
            ("Чехол для пулемёта РПК",               "6301001101", "шт"),
            ("Чехол для снайперской винтовки",       "6301001201", "шт"),
            ("Чехол для бинокля",                    "6301001301", "шт"),
            ("Чехол для радиостанции Р-168",         "6301001401", "шт"),
            ("Мешок вещевой армейский",              "6301001501", "шт"),
            ("Рюкзак полевой 60л",                   "6301001601", "шт"),
            ("Рюкзак десантный РД-54",               "6301001701", "шт"),
            ("Сумка полевая командира",              "6301001801", "шт"),
            ("Сумка медицинская войсковая",          "6301001901", "шт"),
            ("Спальный мешок летний",                "6301002001", "шт"),
            ("Спальный мешок зимний -20°C",          "6301002101", "шт"),
            ("Коврик пенополиуретановый",            "6301002201", "шт"),
            ("Накидка плащ-палатка",                 "6301002301", "шт"),
            ("Куртка дождевая",                      "6301002401", "шт"),
            ("Чехол для касок комплект 10шт",        "6301002501", "компл"),
        ]
        for name, base10, uom in tents_items:
            add_item(name, base10, uom, "qty", "Чехлы и палатки", [("Без размера", base10)])

        self.conn.commit()

    # --- Items & Variants ---

    def get_categories(self):
        cur = self.conn.cursor()
        cur.execute("SELECT id, name FROM categories ORDER BY id")
        return cur.fetchall()

    def get_items(self):
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT i.id, i.name, i.base_code, i.uom, i.type,
                   COALESCE(c.name, '—') AS category_name, i.category_id
            FROM items i
            LEFT JOIN categories c ON c.id = i.category_id
            ORDER BY c.name COLLATE NOCASE, i.name COLLATE NOCASE
            """
        )
        return cur.fetchall()

    def add_item(self, name: str, base_code: str, uom: str, item_type: str, category_id: int | None = None):
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO items(name, base_code, uom, type, category_id) VALUES (?, ?, ?, ?, ?)",
            (name.strip(), base_code.strip(), uom.strip(), item_type, category_id),
        )
        iid = cur.lastrowid
        self.conn.commit()
        self._audit("ITEM_INSERT", "items", iid, f"name={name.strip()} base_code={base_code.strip()}")
        return iid

    def get_variants_for_item(self, item_id: int):
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT id, size_name, full_code
            FROM variants
            WHERE item_id = ?
            ORDER BY size_name COLLATE NOCASE
            """,
            (item_id,),
        )
        return cur.fetchall()

    def get_item(self, item_id: int):
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM items WHERE id = ?", (item_id,))
        return cur.fetchone()

    def add_variant(self, item_id: int, size_name: str, full_code: str, item_type: str):
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO variants(item_id, size_name, full_code) VALUES (?, ?, ?)",
            (item_id, size_name.strip(), full_code.strip()),
        )
        variant_id = cur.lastrowid
        if item_type == "qty":
            cur.execute(
                "INSERT OR IGNORE INTO stock_qty(variant_id, quantity) VALUES (?, 0)",
                (variant_id,),
            )
        self.conn.commit()
        self._audit("VARIANT_INSERT", "variants", variant_id, f"item_id={item_id} size={size_name.strip()} full_code={full_code.strip()}")
        return variant_id

    # --- Units ---

    def get_units(self):
        cur = self.conn.cursor()
        cur.execute("SELECT id, name FROM units ORDER BY name COLLATE NOCASE")
        return cur.fetchall()

    def add_unit(self, name: str):
        cur = self.conn.cursor()
        cur.execute("INSERT INTO units(name) VALUES (?)", (name.strip(),))
        uid = cur.lastrowid
        self.conn.commit()
        self._audit("UNIT_INSERT", "units", uid, f"name={name.strip()}")
        return uid

    def delete_unit(self, unit_id: int):
        cur = self.conn.cursor()
        cur.execute("DELETE FROM units WHERE id = ?", (unit_id,))
        self.conn.commit()
        self._audit("UNIT_DELETE", "units", unit_id, "")

    def has_journal_entries_for_item(self, item_id: int) -> bool:
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT COUNT(*) AS cnt FROM journal j
            JOIN variants v ON v.id = j.variant_id
            WHERE v.item_id = ?
            """,
            (item_id,),
        )
        return (cur.fetchone()["cnt"] or 0) > 0

    def has_journal_entries_for_variant(self, variant_id: int) -> bool:
        cur = self.conn.cursor()
        cur.execute(
            "SELECT COUNT(*) AS cnt FROM journal WHERE variant_id = ?",
            (variant_id,),
        )
        return (cur.fetchone()["cnt"] or 0) > 0

    def delete_item(self, item_id: int):
        """Удаляет изделие и все связанные варианты, остатки и записи журнала."""
        cur = self.conn.cursor()
        cur.execute("SELECT id FROM variants WHERE item_id = ?", (item_id,))
        variant_ids = [r["id"] for r in cur.fetchall()]
        for vid in variant_ids:
            cur.execute("DELETE FROM journal WHERE variant_id = ?", (vid,))
            cur.execute("DELETE FROM stock_qty WHERE variant_id = ?", (vid,))
            cur.execute("DELETE FROM stock_serial WHERE variant_id = ?", (vid,))
        cur.execute("DELETE FROM variants WHERE item_id = ?", (item_id,))
        cur.execute("DELETE FROM items WHERE id = ?", (item_id,))
        self.conn.commit()
        self._audit("ITEM_DELETE", "items", item_id, f"variants={variant_ids}")

    def delete_variant(self, variant_id: int):
        """Удаляет вариант (размер) и все связанные остатки и записи журнала."""
        cur = self.conn.cursor()
        cur.execute("DELETE FROM journal WHERE variant_id = ?", (variant_id,))
        cur.execute("DELETE FROM stock_qty WHERE variant_id = ?", (variant_id,))
        cur.execute("DELETE FROM stock_serial WHERE variant_id = ?", (variant_id,))
        cur.execute("DELETE FROM variants WHERE id = ?", (variant_id,))
        self.conn.commit()
        self._audit("VARIANT_DELETE", "variants", variant_id, "")

    def get_or_create_unit(self, name: str | None):
        if not name:
            return None
        name = name.strip()
        if not name:
            return None
        cur = self.conn.cursor()
        cur.execute("SELECT id FROM units WHERE name = ?", (name,))
        row = cur.fetchone()
        if row:
            return row["id"]
        cur.execute("INSERT INTO units(name) VALUES (?)", (name,))
        self.conn.commit()
        return cur.lastrowid

    # --- Search & Info ---

    def search_variants(self, text: str, only_in_stock: bool = False):
        pattern = f"%{text.strip()}%"
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT
                v.id AS variant_id,
                v.full_code,
                v.size_name,
                i.name AS item_name,
                i.type AS item_type,
                i.uom AS uom,
                COALESCE(c.name, '—') AS category_name,
                CASE
                    WHEN i.type = 'qty' THEN COALESCE(sq.quantity, 0)
                    ELSE (SELECT COUNT(*) FROM stock_serial ss WHERE ss.variant_id = v.id)
                END AS stock_value
            FROM variants v
            JOIN items i ON v.item_id = i.id
            LEFT JOIN categories c ON c.id = i.category_id
            LEFT JOIN stock_qty sq ON sq.variant_id = v.id
            WHERE v.full_code LIKE ? OR i.name LIKE ?
            ORDER BY i.name COLLATE NOCASE, v.size_name COLLATE NOCASE
            """,
            (pattern, pattern),
        )
        rows = cur.fetchall()
        if only_in_stock:
            rows = [r for r in rows if (r["stock_value"] or 0) > 0]
        return rows

    def get_variant_with_item(self, variant_id: int):
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT
                v.id AS variant_id,
                v.full_code,
                v.size_name,
                i.id AS item_id,
                i.name AS item_name,
                i.base_code,
                i.uom,
                i.type AS item_type
            FROM variants v
            JOIN items i ON v.item_id = i.id
            WHERE v.id = ?
            """,
            (variant_id,),
        )
        return cur.fetchone()

    # --- Stock operations ---

    def get_qty_stock(self, variant_id: int) -> int:
        cur = self.conn.cursor()
        cur.execute(
            "SELECT quantity FROM stock_qty WHERE variant_id = ?", (variant_id,)
        )
        row = cur.fetchone()
        return int(row["quantity"]) if row else 0

    def adjust_qty_stock(self, variant_id: int, delta: int):
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT INTO stock_qty(variant_id, quantity)
            VALUES (?, ?)
            ON CONFLICT(variant_id) DO UPDATE SET quantity = quantity + excluded.quantity
            """,
            (variant_id, delta),
        )
        self.conn.commit()

    def serial_exists(self, factory_sn: str) -> bool:
        cur = self.conn.cursor()
        cur.execute(
            "SELECT id FROM stock_serial WHERE factory_sn = ?", (factory_sn.strip(),)
        )
        return cur.fetchone() is not None

    def serial_exists_for_variant(self, variant_id: int, factory_sn: str) -> bool:
        cur = self.conn.cursor()
        cur.execute(
            "SELECT id FROM stock_serial WHERE variant_id = ? AND factory_sn = ?",
            (variant_id, factory_sn.strip()),
        )
        return cur.fetchone() is not None

    def add_serial(self, variant_id: int, factory_sn: str):
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO stock_serial(variant_id, factory_sn) VALUES (?, ?)",
            (variant_id, factory_sn.strip()),
        )
        self.conn.commit()

    def remove_serial(self, variant_id: int, factory_sn: str) -> bool:
        cur = self.conn.cursor()
        cur.execute(
            "DELETE FROM stock_serial WHERE variant_id = ? AND factory_sn = ?",
            (variant_id, factory_sn.strip()),
        )
        deleted = cur.rowcount > 0
        self.conn.commit()
        return deleted

    # --- Journal ---

    def _audit(self, action: str, entity_type: str, entity_id: int | None, details: str = ""):
        try:
            cur = self.conn.cursor()
            cur.execute(
                """
                INSERT INTO audit_log(ts, action, entity_type, entity_id, details)
                VALUES (?, ?, ?, ?, ?)
                """,
                (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), action, entity_type, entity_id or 0, details),
            )
            self.conn.commit()
        except Exception as e:
            if logger:
                logger.exception("Audit log write failed: %s", e)

    def add_journal_record(
        self,
        op_type: str,
        variant_id: int,
        quantity: int | None,
        factory_sn: str | None,
        unit_id: int | None,
        doc_name: str,
    ):
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT INTO journal(date, op_type, variant_id, quantity, factory_sn, unit_id, doc_name)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                op_type,
                variant_id,
                quantity,
                factory_sn.strip() if factory_sn else None,
                unit_id,
                doc_name.strip(),
            ),
        )
        jid = cur.lastrowid
        self.conn.commit()
        self._audit("JOURNAL_INSERT", "journal", jid, f"op={op_type} variant_id={variant_id} doc={doc_name.strip()}")

    # --- Stock view ---

    def get_stock_view(self):
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT
                i.id AS item_id,
                i.name AS item_name,
                i.base_code,
                i.type AS item_type,
                i.uom AS uom,
                COALESCE(c.name, '—') AS category_name,
                COALESCE(
                    CASE
                        WHEN i.type = 'qty' THEN SUM(sq.quantity)
                        ELSE COUNT(ss.id)
                    END,
                    0
                ) AS stock_value
            FROM items i
            LEFT JOIN categories c ON c.id = i.category_id
            LEFT JOIN variants v ON v.item_id = i.id
            LEFT JOIN stock_qty sq ON sq.variant_id = v.id
            LEFT JOIN stock_serial ss ON ss.variant_id = v.id
            GROUP BY i.id, i.name, i.base_code, i.type, i.uom, c.name
            HAVING stock_value > 0
            ORDER BY c.name COLLATE NOCASE, i.name COLLATE NOCASE
            """
        )
        return cur.fetchall()

    def get_journal_view(
        self,
        limit: int = 200,
        date_from: str | None = None,
        date_to: str | None = None,
        unit_id: int | None = None,
    ):
        cur = self.conn.cursor()
        where_parts = []
        params = []
        if date_from:
            where_parts.append("date(j.date) >= ?")
            params.append(date_from)
        if date_to:
            where_parts.append("date(j.date) <= ?")
            params.append(date_to)
        if unit_id is not None:
            where_parts.append("j.unit_id = ?")
            params.append(unit_id)
        where_sql = " WHERE " + " AND ".join(where_parts) if where_parts else ""
        params.append(limit)
        cur.execute(
            f"""
            SELECT
                j.id AS id,
                j.date AS date,
                j.op_type AS op_type,
                j.doc_name AS doc_name,
                v.size_name AS size_name,
                v.full_code AS full_code,
                i.name AS item_name,
                i.type AS item_type,
                j.quantity AS quantity,
                j.factory_sn AS factory_sn,
                u.name AS unit_name
            FROM journal j
            JOIN variants v ON j.variant_id = v.id
            JOIN items i ON v.item_id = i.id
            LEFT JOIN units u ON j.unit_id = u.id
            {where_sql}
            ORDER BY j.date DESC, j.id DESC
            LIMIT ?
            """,
            tuple(params),
        )
        return cur.fetchall()

    def get_serials_for_variant(self, variant_id: int):
        """Возвращает все серийные номера на складе для данного варианта."""
        cur = self.conn.cursor()
        cur.execute(
            "SELECT factory_sn FROM stock_serial WHERE variant_id = ? ORDER BY factory_sn COLLATE NOCASE",
            (variant_id,),
        )
        return cur.fetchall()

    def get_serials_for_item(self, item_id: int):
        """Возвращает все S/N на складе по всем вариантам изделия (с размером и полным кодом)."""
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT ss.factory_sn, v.size_name, v.full_code
            FROM stock_serial ss
            JOIN variants v ON v.id = ss.variant_id
            WHERE v.item_id = ?
            ORDER BY v.size_name COLLATE NOCASE, ss.factory_sn COLLATE NOCASE
            """,
            (item_id,),
        )
        return cur.fetchall()

    def get_item_stock_details(self, item_id: int):
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT
                v.id AS variant_id,
                v.full_code,
                v.size_name,
                i.uom AS uom,
                COALESCE(
                    CASE
                        WHEN i.type = 'qty' THEN sq.quantity
                        ELSE COUNT(ss.id)
                    END,
                    0
                ) AS stock_value
            FROM variants v
            JOIN items i ON v.item_id = i.id
            LEFT JOIN stock_qty sq ON sq.variant_id = v.id
            LEFT JOIN stock_serial ss ON ss.variant_id = v.id
            WHERE v.item_id = ?
            GROUP BY v.id, v.full_code, v.size_name, i.uom, sq.quantity
            ORDER BY v.size_name COLLATE NOCASE
            """,
            (item_id,),
        )
        return cur.fetchall()


# --- Экспорт отчётов: Excel / PDF ---

def _export_journal_excel(db: DatabaseManager, path: str, date_from: str, date_to: str, unit_id: int | None) -> bool:
    try:
        import openpyxl
        from openpyxl.styles import Font, Alignment
    except ImportError:
        if logger:
            logger.warning("openpyxl not installed: pip install openpyxl")
        return False
    try:
        rows = db.get_journal_view(limit=10000, date_from=date_from, date_to=date_to, unit_id=unit_id)
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Журнал операций"
        headers = ["Дата", "Операция", "Документ", "Название", "Размер", "Кол-во", "Подразделение"]
        for c, h in enumerate(headers, 1):
            ws.cell(1, c, h)
            ws.cell(1, c).font = Font(bold=True)
        for r, row in enumerate(rows, 2):
            op_text = "Приход" if row["op_type"] == "IN" else "Выдача"
            qty = row["quantity"] if row["quantity"] is not None else (1 if row["factory_sn"] else 0)
            ws.cell(r, 1, row["date"])
            ws.cell(r, 2, op_text)
            ws.cell(r, 3, row["doc_name"] or "")
            ws.cell(r, 4, row["item_name"])
            ws.cell(r, 5, row["size_name"])
            ws.cell(r, 6, qty)
            ws.cell(r, 7, row["unit_name"] or "")
        wb.save(path)
        if logger:
            logger.info("Exported journal to Excel: %s", path)
        return True
    except Exception as e:
        if logger:
            logger.exception("Export journal Excel failed: %s", e)
        return False


def _register_pdf_font() -> str:
    """
    Регистрирует Arial из системных шрифтов Windows для поддержки кириллицы.
    Возвращает имя зарегистрированного шрифта.
    """
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    font_name = "ArialUnicode"
    try:
        pdfmetrics.getFont(font_name)
        return font_name
    except Exception:
        pass

    candidates = [
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/Arial.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            pdfmetrics.registerFont(TTFont(font_name, path))
            return font_name

    return "Helvetica"


def _export_journal_pdf(db: DatabaseManager, path: str, date_from: str, date_to: str, unit_id: int | None) -> bool:
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib.units import mm
    except ImportError:
        if logger:
            logger.warning("reportlab not installed: pip install reportlab")
        return False
    try:
        font = _register_pdf_font()
        rows = db.get_journal_view(limit=10000, date_from=date_from, date_to=date_to, unit_id=unit_id)

        doc = SimpleDocTemplate(
            path,
            pagesize=landscape(A4),
            leftMargin=10 * mm, rightMargin=10 * mm,
            topMargin=12 * mm, bottomMargin=12 * mm,
        )

        title_style = ParagraphStyle("title", fontName=font, fontSize=12, spaceAfter=6)
        header = Paragraph(
            f"Журнал операций ({date_from} — {date_to})",
            title_style,
        )

        col_headers = ["Дата", "Операция", "Документ", "Название", "Размер", "Кол-во", "Подразделение"]
        data = [col_headers]
        for row in rows:
            op_text = "Приход" if row["op_type"] == "IN" else "Выдача"
            qty = row["quantity"] if row["quantity"] is not None else (1 if row["factory_sn"] else 0)
            data.append([
                row["date"], op_text, row["doc_name"] or "", row["item_name"],
                row["size_name"], str(qty), row["unit_name"] or "",
            ])

        col_widths = [35*mm, 22*mm, 35*mm, 70*mm, 22*mm, 18*mm, 40*mm]
        t = Table(data, colWidths=col_widths, repeatRows=1)
        t.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), font),
            ("FONTSIZE", (0, 0), (-1, 0), 9),
            ("FONTSIZE", (0, 1), (-1, -1), 8),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f7aec")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), font),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f0f4ff")]),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#d0d5e8")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ]))

        doc.build([header, Spacer(1, 4*mm), t])
        if logger:
            logger.info("Exported journal to PDF: %s", path)
        return True
    except Exception as e:
        if logger:
            logger.exception("Export journal PDF failed: %s", e)
        return False


def _export_stock_excel(db: DatabaseManager, path: str) -> bool:
    try:
        import openpyxl
        from openpyxl.styles import Font
    except ImportError:
        if logger:
            logger.warning("openpyxl not installed: pip install openpyxl")
        return False
    try:
        rows = db.get_stock_view()
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Остатки"
        headers = ["Н/Н (базовый)", "Название", "Остаток", "Ед. изм."]
        for c, h in enumerate(headers, 1):
            ws.cell(1, c, h)
            ws.cell(1, c).font = Font(bold=True)
        for r, row in enumerate(rows, 2):
            ws.cell(r, 1, row["base_code"])
            ws.cell(r, 2, row["item_name"])
            ws.cell(r, 3, row["stock_value"])
            ws.cell(r, 4, row["uom"])
        wb.save(path)
        if logger:
            logger.info("Exported stock to Excel: %s", path)
        return True
    except Exception as e:
        if logger:
            logger.exception("Export stock Excel failed: %s", e)
        return False


def _export_stock_pdf(db: DatabaseManager, path: str) -> bool:
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib.units import mm
    except ImportError:
        if logger:
            logger.warning("reportlab not installed: pip install reportlab")
        return False
    try:
        font = _register_pdf_font()

        doc = SimpleDocTemplate(
            path,
            pagesize=A4,
            leftMargin=10 * mm, rightMargin=10 * mm,
            topMargin=12 * mm, bottomMargin=12 * mm,
        )

        title_style = ParagraphStyle("title", fontName=font, fontSize=12, spaceAfter=6)
        sub_style = ParagraphStyle("sub", fontName=font, fontSize=8, textColor=colors.HexColor("#555555"), spaceAfter=2)

        header = Paragraph("Остатки на складе", title_style)
        header_date = Paragraph(
            f"Сформировано: {datetime.now().strftime('%d.%m.%Y %H:%M')}",
            sub_style,
        )

        base_rows = db.get_stock_view()

        elements = [header, header_date, Spacer(1, 4 * mm)]

        COL_W = [35*mm, 70*mm, 30*mm, 20*mm]

        for row in base_rows:
            details = db.get_item_stock_details(row["item_id"])

            item_data = [[
                row["base_code"],
                row["item_name"],
                f"Итого: {row['stock_value']}",
                row["uom"],
            ]]
            item_table = Table(item_data, colWidths=COL_W)
            item_table.setStyle(TableStyle([
                ("FONTNAME", (0, 0), (-1, -1), font),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#1f7aec")),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#1764c0")),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ]))
            elements.append(item_table)

            if details:
                size_data = [["  Размер", "Н/Н (полный)", "Остаток", "Ед. изм."]]
                for d in details:
                    size_data.append([
                        f"  {d['size_name']}",
                        d["full_code"],
                        str(d["stock_value"]),
                        d["uom"],
                    ])
                size_table = Table(size_data, colWidths=COL_W)
                size_table.setStyle(TableStyle([
                    ("FONTNAME", (0, 0), (-1, -1), font),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8edf7")),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f7ff")]),
                    ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#d0d5e8")),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ]))
                elements.append(size_table)

            elements.append(Spacer(1, 3 * mm))

        doc.build(elements)
        if logger:
            logger.info("Exported stock to PDF: %s", path)
        return True
    except Exception as e:
        if logger:
            logger.exception("Export stock PDF failed: %s", e)
        return False
