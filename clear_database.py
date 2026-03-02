"""
Полная очистка базы данных: номенклатура, остатки, операции.
Таблицы units и categories не трогаем.
"""
import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "warehouse.db")

def main():
    if not os.path.exists(DB_PATH):
        print("Файл базы не найден:", DB_PATH)
        return
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    cur = conn.cursor()
    # Порядок: сначала зависимые таблицы
    for table in ("journal", "stock_serial", "stock_qty", "variants", "items", "audit_log"):
        cur.execute(f"DELETE FROM {table}")
        n = cur.rowcount
        print(f"  {table}: удалено {n} записей")
    conn.commit()
    conn.close()
    print("База очищена: номенклатор, остатки, операции.")

if __name__ == "__main__":
    main()
