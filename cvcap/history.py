"""Historial de análisis: registro de cada medida procesada (CV o galvanostática).

Se guarda en la misma base SQLite que las muestras (``CVCAP_DB_PATH`` o ``data/cvcap.sqlite``),
en una tabla propia ``history`` que no interfiere con ``samples``.
Cada entrada guarda el momento del análisis, el archivo, el modo, la masa, un resumen en JSON
y la tabla de ciclos en JSON, para poder consultarla o compararla más tarde.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from io import StringIO
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from .db import default_db_path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    name TEXT,
    mode TEXT,
    mass_mg REAL,
    summary TEXT,
    cycles TEXT
);
"""


def _json_default(obj):
    if isinstance(obj, (pd.Timestamp, datetime)):
        return obj.isoformat()
    if hasattr(obj, "item"):
        return obj.item()
    return str(obj)


class History:
    """Historial de análisis en SQLite."""

    def __init__(self, path: Optional[Path] = None):
        self.path = Path(path) if path else default_db_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path)) as con, con:
            con.executescript(_SCHEMA)

    def log(self, name: str, mode: str, mass_mg: Optional[float], summary: Dict[str, Any],
            cycles: Optional[pd.DataFrame] = None) -> int:
        """Añade una entrada y devuelve su identificador."""
        cycles_json = cycles.to_json(orient="records") if cycles is not None and not cycles.empty else "[]"
        with closing(sqlite3.connect(self.path)) as con, con:
            cur = con.execute(
                "INSERT INTO history (created_at, name, mode, mass_mg, summary, cycles) VALUES (?, ?, ?, ?, ?, ?)",
                (datetime.now().isoformat(timespec="seconds"), name, mode,
                 float(mass_mg) if mass_mg is not None else None,
                 json.dumps(summary, default=_json_default, ensure_ascii=False), cycles_json),
            )
            return int(cur.lastrowid)

    def list(self, limit: int = 50) -> pd.DataFrame:
        """Últimas entradas (más recientes primero), con el resumen expandido en columnas."""
        with closing(sqlite3.connect(self.path)) as con:
            rows = con.execute(
                "SELECT id, created_at, name, mode, mass_mg, summary FROM history ORDER BY id DESC LIMIT ?",
                (int(limit),),
            ).fetchall()
        records = []
        for rid, created, name, mode, mass, summary in rows:
            info = json.loads(summary) if summary else {}
            records.append({"id": rid, "created_at": created, "name": name, "mode": mode, "mass_mg": mass, **info})
        return pd.DataFrame(records)

    def cycles(self, entry_id: int) -> pd.DataFrame:
        """Tabla de ciclos guardada en una entrada."""
        with closing(sqlite3.connect(self.path)) as con:
            row = con.execute("SELECT cycles FROM history WHERE id = ?", (int(entry_id),)).fetchone()
        if not row:
            return pd.DataFrame()
        return pd.read_json(StringIO(row[0]), orient="records") if row[0] and row[0] != "[]" else pd.DataFrame()

    def delete(self, entry_id: int) -> None:
        with closing(sqlite3.connect(self.path)) as con, con:
            con.execute("DELETE FROM history WHERE id = ?", (int(entry_id),))


__all__ = ["History"]
