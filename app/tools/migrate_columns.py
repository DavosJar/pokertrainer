"""
Anade columnas faltantes a la tabla 'scenarios' sin borrar filas.

SQLite no tiene 'ALTER TABLE ... ADD COLUMN IF NOT EXISTS', asi que se compara
la tabla actual con la que define el modelo y se anade lo que falte. Es
idempotente: se puede ejecutar las veces que haga falta.

Uso:  python -m app.tools.migrate_columns
"""

import os
import sqlite3
import sys

from app.database import DB_PATH, VALID_ENVS

# (columna, tipo SQLite) para cada campo anadido despues del primer release.
EXPECTED_COLUMNS = [
    ("stack_min", "FLOAT"),
    ("stack_max", "FLOAT"),
    ("stack_step", "FLOAT"),
    ("by_stack", "JSON"),
]


def migrate(db_path: str) -> bool:
    """True si hubo cambios, False si la tabla ya estaba al dia."""
    if not os.path.exists(db_path):
        print(f"  {os.path.basename(db_path)}: no existe todavia, se creara sola")
        return False

    conn = sqlite3.connect(db_path)
    try:
        conn.row_factory = sqlite3.Row

        actual = {row["name"] for row in conn.execute("PRAGMA table_info(scenarios)")}
        if not actual:
            print(f"  {os.path.basename(db_path)}: sin tabla 'scenarios', se creara sola")
            return False

        faltantes = [(c, t) for c, t in EXPECTED_COLUMNS if c not in actual]
        if not faltantes:
            print(f"  {os.path.basename(db_path)}: esquema al dia")
            return False

        for column, sql_type in faltantes:
            conn.execute(f"ALTER TABLE scenarios ADD COLUMN {column} {sql_type}")
            print(f"  {os.path.basename(db_path)}: + scenarios.{column} {sql_type}")

        conn.commit()
        return True
    finally:
        conn.close()


def main() -> int:
    print(f"Migrando {DB_PATH} (APP_ENV={os.getenv('APP_ENV') or 'prod'})")
    migrate(DB_PATH)
    print("Listo.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
