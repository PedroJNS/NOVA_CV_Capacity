"""Base de datos de muestras (SQLite, sin dependencias externas).

Cada muestra guarda:
* identificador único (automático ``S-0001``, ``S-0002``… o uno propio),
* metadatos (nombre, material, lote, fecha de medida, archivo de origen),
* condiciones de preparación (composición, mezcla, recubrimiento, espesor,
  prensado, secado, separador, electrolito, volumen, celda) y notas libres,
* resultados (resumen, ciclos, segmentos, picos) y los parámetros del cálculo,
* la curva E–I comprimida, para volver a dibujarla o exportarla sin el archivo original.

La ruta se elige con la variable de entorno ``CVCAP_DB_PATH`` (por defecto
``data/cvcap.sqlite`` junto a la aplicación).
"""
from __future__ import annotations

import io
import json
import os
import re
import sqlite3
import tempfile
from contextlib import closing, contextmanager
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from .i18n import CvcapError, Note

SCHEMA_VERSION = 1

#: Campos de preparación (clave interna -> tipo). Las etiquetas están en i18n: prep.<clave>
PREP_FIELDS: Dict[str, str] = {
    "composition": "text",
    "mixing": "text",
    "coating": "text",
    "thickness_um": "number",
    "pressing": "text",
    "drying": "text",
    "separator": "text",
    "electrolyte": "text",
    "electrolyte_ul": "number",
    "cell": "text",
}
MATERIALS = ("commercial", "spent", "recycled", "other")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS samples (
    id TEXT PRIMARY KEY,
    name TEXT,
    material TEXT,
    batch TEXT,
    measured_on TEXT,
    source_file TEXT,
    mass_mg REAL,
    area_cm2 REAL,
    method TEXT,
    prep TEXT,
    notes TEXT,
    summary TEXT,
    cycles TEXT,
    cycle_notes TEXT,
    segments TEXT,
    peaks TEXT,
    peak_windows TEXT,
    params TEXT,
    curve BLOB,
    created_at TEXT,
    updated_at TEXT
);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
"""
_COLUMNS = [
    "id", "name", "material", "batch", "measured_on", "source_file", "mass_mg", "area_cm2", "method",
    "prep", "notes", "summary", "cycles", "cycle_notes", "segments", "peaks", "peak_windows", "params",
    "curve", "created_at", "updated_at",
]
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _.\-/]{0,63}$")


def default_db_path() -> Path:
    env = os.environ.get("CVCAP_DB_PATH")
    if env:
        return Path(env)
    return Path(__file__).resolve().parent.parent / "data" / "cvcap.sqlite"


# --------------------------------------------------------------------------
# Registro
# --------------------------------------------------------------------------
@dataclass
class SampleRecord:
    id: str
    name: str = ""
    material: str = "other"
    batch: str = ""
    measured_on: str = ""
    source_file: str = ""
    mass_mg: Optional[float] = None
    area_cm2: Optional[float] = None
    method: str = "signo"
    prep: Dict[str, object] = field(default_factory=dict)
    notes: str = ""
    summary: Dict[str, object] = field(default_factory=dict)
    cycles: pd.DataFrame = field(default_factory=pd.DataFrame)
    cycle_notes: Dict[int, List[Note]] = field(default_factory=dict)
    segments: pd.DataFrame = field(default_factory=pd.DataFrame)
    peaks: pd.DataFrame = field(default_factory=pd.DataFrame)
    peak_windows: List[dict] = field(default_factory=list)
    params: Dict[str, object] = field(default_factory=dict)
    curve: Dict[str, np.ndarray] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""


def record_from_result(result, sample_id: str, meta: Optional[dict] = None, peaks: Optional[pd.DataFrame] = None,
                       peak_windows: Optional[List[dict]] = None) -> SampleRecord:
    """Crea un registro a partir de un :class:`cvcap.analysis.AnalysisResult`."""
    meta = dict(meta or {})
    curve = {
        "potential_V": result.cv.potential_V,
        "current_A": result.current_A,
        "point_cycle": result.point_cycle,
    }
    if result.cv.time_s is not None:
        curve["time_s"] = result.cv.time_s
    return SampleRecord(
        id=sample_id.strip(),
        name=meta.get("name", "") or "",
        material=meta.get("material", "other") or "other",
        batch=meta.get("batch", "") or "",
        measured_on=str(meta.get("measured_on", "") or ""),
        source_file=result.name,
        mass_mg=result.mass_mg,
        area_cm2=result.area_cm2,
        method=result.method,
        prep={k: v for k, v in (meta.get("prep") or {}).items() if v not in (None, "")},
        notes=meta.get("notes", "") or "",
        summary=dict(result.summary),
        cycles=result.cycles.copy(),
        cycle_notes={k: list(v) for k, v in result.cycle_notes.items()},
        segments=result.segments.copy(),
        peaks=peaks.copy() if peaks is not None else pd.DataFrame(),
        peak_windows=list(peak_windows or []),
        params=dict(result.params),
        curve=curve,
    )


# --------------------------------------------------------------------------
# Serialización
# --------------------------------------------------------------------------
def _json_default(obj):
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return None if np.isnan(obj) else float(obj)
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    raise TypeError(f"No serializable: {type(obj)}")


def _dumps(obj) -> str:
    return json.dumps(obj, default=_json_default, ensure_ascii=False)


def _df_to_json(df: pd.DataFrame) -> str:
    if df is None or df.empty:
        return "[]"
    clean = df.astype(object).where(pd.notna(df), None)
    return _dumps(clean.to_dict(orient="records"))


def _df_from_json(text: Optional[str]) -> pd.DataFrame:
    if not text:
        return pd.DataFrame()
    return pd.DataFrame(json.loads(text))


def _notes_to_json(cycle_notes: Dict[int, List[Note]]) -> str:
    return _dumps({str(k): [[n.code, n.params] for n in v] for k, v in cycle_notes.items()})


def _notes_from_json(text: Optional[str]) -> Dict[int, List[Note]]:
    if not text:
        return {}
    raw = json.loads(text)
    return {int(k): [Note(code, **params) for code, params in v] for k, v in raw.items()}


def _curve_to_blob(curve: Dict[str, np.ndarray]) -> Optional[bytes]:
    if not curve:
        return None
    arrays = {}
    for key, values in curve.items():
        values = np.asarray(values)
        if key in ("potential_V", "current_A"):
            values = values.astype(np.float32)
        elif key == "point_cycle":
            values = values.astype(np.int16)
        arrays[key] = values
    buf = io.BytesIO()
    np.savez_compressed(buf, **arrays)
    return buf.getvalue()


def _curve_from_blob(blob: Optional[bytes]) -> Dict[str, np.ndarray]:
    if not blob:
        return {}
    with np.load(io.BytesIO(blob)) as data:
        out = {k: data[k] for k in data.files}
    for key in ("potential_V", "current_A"):
        if key in out:
            out[key] = out[key].astype(float)
    if "point_cycle" in out:
        out["point_cycle"] = out["point_cycle"].astype(np.int32)
    return out


def _row_from_record(rec: SampleRecord) -> Tuple:
    return (
        rec.id, rec.name, rec.material, rec.batch, rec.measured_on, rec.source_file,
        rec.mass_mg, rec.area_cm2, rec.method, _dumps(rec.prep), rec.notes, _dumps(rec.summary),
        _df_to_json(rec.cycles), _notes_to_json(rec.cycle_notes), _df_to_json(rec.segments),
        _df_to_json(rec.peaks), _dumps(rec.peak_windows), _dumps(rec.params),
        _curve_to_blob(rec.curve), rec.created_at, rec.updated_at,
    )


def _record_from_row(row: sqlite3.Row) -> SampleRecord:
    return SampleRecord(
        id=row["id"], name=row["name"] or "", material=row["material"] or "other", batch=row["batch"] or "",
        measured_on=row["measured_on"] or "", source_file=row["source_file"] or "",
        mass_mg=row["mass_mg"], area_cm2=row["area_cm2"], method=row["method"] or "signo",
        prep=json.loads(row["prep"] or "{}"), notes=row["notes"] or "",
        summary=json.loads(row["summary"] or "{}"), cycles=_df_from_json(row["cycles"]),
        cycle_notes=_notes_from_json(row["cycle_notes"]), segments=_df_from_json(row["segments"]),
        peaks=_df_from_json(row["peaks"]), peak_windows=json.loads(row["peak_windows"] or "[]"),
        params=json.loads(row["params"] or "{}"), curve=_curve_from_blob(row["curve"]),
        created_at=row["created_at"] or "", updated_at=row["updated_at"] or "",
    )


# --------------------------------------------------------------------------
# Base de datos
# --------------------------------------------------------------------------
class Database:
    def __init__(self, path=None):
        self.path = Path(path) if path else default_db_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as con:
            con.executescript(_SCHEMA)
            con.execute("INSERT OR IGNORE INTO meta(key, value) VALUES ('schema_version', ?)", (str(SCHEMA_VERSION),))

    @contextmanager
    def _connect(self):
        """Conexión que confirma al terminar (o deshace si hay error) y siempre se cierra."""
        con = sqlite3.connect(self.path, timeout=10)
        con.row_factory = sqlite3.Row
        try:
            yield con
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()

    # ---- identificadores
    @staticmethod
    def validate_id(sample_id: str) -> str:
        sample_id = (sample_id or "").strip()
        if not _ID_RE.match(sample_id):
            raise CvcapError("err.db_bad_id")
        return sample_id

    def exists(self, sample_id: str) -> bool:
        with self._connect() as con:
            return con.execute("SELECT 1 FROM samples WHERE id = ?", (sample_id.strip(),)).fetchone() is not None

    def next_id(self, prefix: str = "S", offset: int = 0) -> str:
        with self._connect() as con:
            ids = [r[0] for r in con.execute("SELECT id FROM samples WHERE id LIKE ?", (f"{prefix}-%",))]
        numbers = [int(m.group(1)) for i in ids if (m := re.fullmatch(rf"{re.escape(prefix)}-(\d+)", i))]
        return f"{prefix}-{(max(numbers) if numbers else 0) + 1 + offset:04d}"

    # ---- escritura
    def save(self, rec: SampleRecord, overwrite: bool = False) -> None:
        rec.id = self.validate_id(rec.id)
        now = datetime.now().isoformat(timespec="seconds")
        with self._connect() as con:
            old = con.execute("SELECT created_at FROM samples WHERE id = ?", (rec.id,)).fetchone()
            if old is not None and not overwrite:
                raise CvcapError("err.db_exists", id=rec.id)
            rec.created_at = (old["created_at"] if old is not None else None) or rec.created_at or now
            rec.updated_at = now
            placeholders = ",".join("?" * len(_COLUMNS))
            con.execute(f"INSERT OR REPLACE INTO samples ({','.join(_COLUMNS)}) VALUES ({placeholders})",
                        _row_from_record(rec))

    def update_metadata(self, sample_id: str, **fields) -> None:
        allowed = {"name", "material", "batch", "measured_on", "notes", "prep"}
        updates = {k: v for k, v in fields.items() if k in allowed}
        if not updates:
            return
        if "prep" in updates:
            updates["prep"] = _dumps({k: v for k, v in (updates["prep"] or {}).items() if v not in (None, "")})
        updates["updated_at"] = datetime.now().isoformat(timespec="seconds")
        sets = ", ".join(f"{k} = ?" for k in updates)
        with self._connect() as con:
            cur = con.execute(f"UPDATE samples SET {sets} WHERE id = ?", (*updates.values(), sample_id))
            if cur.rowcount == 0:
                raise CvcapError("err.db_not_found", id=sample_id)

    def delete(self, sample_id: str) -> None:
        with self._connect() as con:
            con.execute("DELETE FROM samples WHERE id = ?", (sample_id,))

    # ---- lectura
    def get(self, sample_id: str) -> SampleRecord:
        with self._connect() as con:
            row = con.execute("SELECT * FROM samples WHERE id = ?", (sample_id,)).fetchone()
        if row is None:
            raise CvcapError("err.db_not_found", id=sample_id)
        return _record_from_row(row)

    def list_samples(self) -> pd.DataFrame:
        """Catálogo con claves internas (una fila por muestra, sin curvas)."""
        query = ("SELECT id, name, material, batch, measured_on, source_file, mass_mg, method, notes, prep, "
                 "summary, updated_at FROM samples ORDER BY id")
        with self._connect() as con:
            rows = con.execute(query).fetchall()
        records = []
        for r in rows:
            s = json.loads(r["summary"] or "{}")
            records.append({
                "id": r["id"], "name": r["name"], "material": r["material"], "batch": r["batch"],
                "measured_on": r["measured_on"], "source_file": r["source_file"], "mass_mg": r["mass_mg"],
                "method": r["method"], "n_cycles": s.get("n_cycles"), "ce1": s.get("ce1"),
                "ce_mean": s.get("ce_mean"), "cap_delit1": s.get("cap_delit1"),
                "cap_delit_last": s.get("cap_delit_last"), "ret_last": s.get("ret_last"),
                "notes": r["notes"], "prep": json.loads(r["prep"] or "{}"), "updated_at": r["updated_at"],
            })
        columns = ["id", "name", "material", "batch", "measured_on", "source_file", "mass_mg", "method",
                   "n_cycles", "ce1", "ce_mean", "cap_delit1", "cap_delit_last", "ret_last", "notes", "prep",
                   "updated_at"]
        return pd.DataFrame(records, columns=columns)

    def count(self) -> int:
        with self._connect() as con:
            return int(con.execute("SELECT COUNT(*) FROM samples").fetchone()[0])

    # ---- copia de seguridad
    def export_bytes(self) -> bytes:
        """Copia consistente de la base de datos como bytes (.sqlite)."""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "backup.sqlite"
            with self._connect() as src, closing(sqlite3.connect(target)) as dst:
                src.backup(dst)
            return target.read_bytes()

    def import_bytes(self, data: bytes, overwrite: bool = False) -> Tuple[int, int]:
        """Importa muestras de otra base de datos de cvcap. Devuelve (importadas, omitidas)."""
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "import.sqlite"
            source.write_bytes(data)
            try:
                with closing(sqlite3.connect(source)) as con:
                    con.row_factory = sqlite3.Row
                    tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                    if "samples" not in tables:
                        raise CvcapError("err.db_invalid")
                    rows = con.execute("SELECT * FROM samples").fetchall()
            except sqlite3.DatabaseError as exc:
                raise CvcapError("err.db_invalid") from exc
        added = skipped = 0
        for row in rows:
            rec = _record_from_row(row)
            if self.exists(rec.id) and not overwrite:
                skipped += 1
                continue
            self.save(rec, overwrite=True)
            added += 1
        return added, skipped
