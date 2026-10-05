"""Lectura de archivos exportados desde NOVA (Metrohm Autolab).

Formatos admitidos
------------------
* Texto/ASCII: .txt, .csv, .dat, .tsv, .asc
  - separador ``;``, tabulador, ``,`` o espacios (se detecta solo)
  - decimal con coma o con punto (se detecta solo)
  - codificación UTF-8, UTF-8 con BOM, UTF-16 o Windows-1252
  - cabecera con nombres de columna en cualquier línea (se ignoran
    las líneas de metadatos previas)
* Excel: .xlsx, .xlsm, .xls (se elige la hoja que contenga potencial y corriente)

El formato nativo de NOVA (.nox) es binario y propietario: hay que exportar
los datos desde NOVA como ASCII o Excel.

Las columnas se reconocen por su nombre (p. ej. ``Potential applied (V)``,
``WE(1).Current (A)``, ``Time (s)``, ``Scan``, ``Index``) y las unidades
entre paréntesis se convierten a SI (V, A, s).
"""
from __future__ import annotations

import codecs
import io
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Union

import numpy as np
import pandas as pd

TEXT_EXTENSIONS = {".txt", ".csv", ".dat", ".tsv", ".asc", ".ascii"}
EXCEL_EXTENSIONS = {".xlsx", ".xlsm", ".xls"}
SUPPORTED_EXTENSIONS = TEXT_EXTENSIONS | EXCEL_EXTENSIONS

#: Papeles que puede tener una columna y etiqueta legible.
ROLE_LABELS = {
    "potential": "Potencial",
    "current": "Corriente",
    "time": "Tiempo",
    "scan": "Scan",
    "index": "Índice",
    "q_plus": "Q+ (NOVA)",
    "q_minus": "Q− (NOVA)",
}

# Nombres candidatos (normalizados, sin unidades) por orden de preferencia.
_ROLE_PATTERNS: Dict[str, List[str]] = {
    "potential": [
        "potential applied", "we(1).potential", "potential", "potencial aplicado",
        "potencial", "ewe", "voltage", "voltaje", "e",
    ],
    "current": ["we(1).current", "current", "corriente", "i"],
    "time": ["time", "tiempo", "corrected time", "t"],
    "scan": ["scan", "ciclo", "cycle"],
    "index": ["index", "indice", "índice"],
    "q_plus": ["q+"],
    "q_minus": ["q-", "q−"],
}
_ROLE_EXCLUDE: Dict[str, List[str]] = {
    "current": ["range", "density", "densidad", "rango"],
    "potential": ["range", "rango"],
}

_UNIT_FACTORS: Dict[str, Dict[str, float]] = {
    "potential": {"v": 1.0, "mv": 1e-3, "uv": 1e-6},
    "current": {"a": 1.0, "ma": 1e-3, "ua": 1e-6, "na": 1e-9, "pa": 1e-12},
    "time": {"s": 1.0, "ms": 1e-3, "min": 60.0, "h": 3600.0},
    "q_plus": {"c": 1.0, "mc": 1e-3, "uc": 1e-6},
    "q_minus": {"c": 1.0, "mc": 1e-3, "uc": 1e-6},
}


class NovaFormatError(ValueError):
    """El archivo no se puede interpretar como datos de una CV."""


@dataclass
class CVData:
    """Datos de una voltametría cíclica en unidades SI y en orden temporal."""

    potential_V: np.ndarray
    current_A: np.ndarray
    time_s: Optional[np.ndarray] = None
    scan: Optional[np.ndarray] = None
    q_plus_C: Optional[np.ndarray] = None
    q_minus_C: Optional[np.ndarray] = None
    source: str = ""
    columns: Dict[str, str] = field(default_factory=dict)
    notes: List[str] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.potential_V)


# --------------------------------------------------------------------------
# Utilidades de nombres y unidades
# --------------------------------------------------------------------------
def _clean(text: str) -> str:
    text = str(text).strip().lower()
    return text.replace("µ", "u").replace("μ", "u").replace("−", "-")


def split_name_unit(name: str) -> tuple:
    """Separa ``'WE(1).Current (mA)'`` en ``('we(1).current', 'ma')``."""
    clean = _clean(name)
    match = re.match(r"^(.*?)\s*[\(\[]\s*([^\)\]]*?)\s*[\)\]]\s*$", clean)
    if match and match.group(1) and not match.group(1).endswith("we"):
        # Evita confundir "we(1)" con una unidad: solo se acepta si queda texto delante
        base, unit = match.group(1).strip(), match.group(2).strip()
        if base and not re.fullmatch(r"\d+", unit):
            return base, unit
    match = re.match(r"^([^/]+?)\s*/\s*([a-z]{1,3})$", clean)
    if match:
        return match.group(1).strip(), match.group(2).strip()
    return clean, ""


def detect_columns(df: pd.DataFrame) -> Dict[str, str]:
    """Asigna a cada papel (potencial, corriente, tiempo…) una columna de ``df``."""
    parsed = {col: split_name_unit(col) for col in df.columns}
    numeric = {col: pd.api.types.is_numeric_dtype(df[col]) for col in df.columns}
    mapping: Dict[str, str] = {}
    used = set()
    for role, patterns in _ROLE_PATTERNS.items():
        excluded = _ROLE_EXCLUDE.get(role, [])
        chosen = None
        for exact in (True, False):
            for pattern in patterns:
                if not exact and len(pattern) <= 2:
                    continue  # letras sueltas ("e", "i", "t") solo por coincidencia exacta
                for col, (base, _unit) in parsed.items():
                    if col in used or not numeric[col]:
                        continue
                    if any(word in base for word in excluded):
                        continue
                    if (exact and base == pattern) or (not exact and base.startswith(pattern)):
                        chosen = col
                        break
                if chosen:
                    break
            if chosen:
                break
        if chosen:
            mapping[role] = chosen
            used.add(chosen)
    return mapping


def unit_factor(role: str, column_name: str) -> tuple:
    """Factor para pasar la columna a SI y la unidad leída ('' si no hay)."""
    _base, unit = split_name_unit(column_name)
    factors = _UNIT_FACTORS.get(role)
    if not factors or not unit:
        return 1.0, unit
    return factors.get(unit.replace(" ", ""), 1.0), unit


# --------------------------------------------------------------------------
# Lectura de bytes y decodificación
# --------------------------------------------------------------------------
def _read_source(source) -> tuple:
    """Devuelve (bytes, nombre_de_archivo) desde ruta, bytes o archivo abierto."""
    name = ""
    if isinstance(source, (str, Path)):
        path = Path(source)
        return path.read_bytes(), path.name
    if isinstance(source, (bytes, bytearray)):
        return bytes(source), name
    if hasattr(source, "getvalue"):
        data = source.getvalue()
    elif hasattr(source, "read"):
        data = source.read()
        try:
            source.seek(0)
        except Exception:  # pragma: no cover - no todos los objetos lo permiten
            pass
    else:
        raise TypeError("Fuente no reconocida: use una ruta, bytes o un archivo abierto.")
    name = getattr(source, "name", "") or ""
    if isinstance(data, str):
        data = data.encode("utf-8")
    return bytes(data), str(name)


def _decode(data: bytes) -> str:
    if data.startswith(codecs.BOM_UTF16_LE) or data.startswith(codecs.BOM_UTF16_BE):
        return data.decode("utf-16")
    head = data[:2000]
    if head and head.count(b"\x00") > len(head) // 4:
        # UTF-16 sin BOM: los ceros están en las posiciones impares (LE) o pares (BE)
        odd_zeros = head[1::2].count(b"\x00")
        return data.decode("utf-16-le" if odd_zeros > len(head) // 4 else "utf-16-be")
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("latin-1", errors="replace")  # pragma: no cover


# --------------------------------------------------------------------------
# Texto
# --------------------------------------------------------------------------
_NUM_RE = re.compile(r"^[+-]?(\d+([.,]\d*)?|[.,]\d+)([eE][+-]?\d+)?$")


def _is_number(text: str) -> bool:
    return bool(_NUM_RE.match(text.strip()))


def _detect_delimiter(lines: List[str]) -> Optional[str]:
    sample = lines[-50:] if len(lines) > 50 else lines
    for delim in (";", "\t", ","):
        counts = [line.count(delim) for line in sample]
        if counts and np.median(counts) >= 1:
            return delim
    return None  # espacios


def _split(line: str, delim: Optional[str]) -> List[str]:
    parts = line.split(delim) if delim else line.split()
    return [p.strip().strip('"').strip("'") for p in parts]


def _numeric_fraction(fields: List[str]) -> float:
    fields = [f for f in fields if f != ""]
    if not fields:
        return 0.0
    return sum(_is_number(f) for f in fields) / len(fields)


def _find_header(lines: List[str], delim: Optional[str]) -> tuple:
    """Índice de la línea de cabecera y de la primera línea de datos."""
    nonempty = [i for i, line in enumerate(lines) if line.strip()]
    for pos, i in enumerate(nonempty[:300]):
        fields = _split(lines[i], delim)
        if len(fields) < 2:
            continue
        if _numeric_fraction(fields) >= 0.5:
            return None, i  # datos sin cabecera
        has_text = any(re.search(r"[A-Za-zµμΩ]", f) for f in fields)
        if has_text and pos + 1 < len(nonempty):
            nxt = _split(lines[nonempty[pos + 1]], delim)
            if len(nxt) >= 2 and _numeric_fraction(nxt) >= 0.5:
                return i, nonempty[pos + 1]
    raise NovaFormatError(
        "No se encontraron columnas numéricas. Exporte los datos desde NOVA como ASCII o Excel."
    )


def _unique_names(names: List[str]) -> List[str]:
    seen: Dict[str, int] = {}
    out = []
    for k, name in enumerate(names):
        name = name.strip() or f"col_{k + 1}"
        if name in seen:
            seen[name] += 1
            name = f"{name}_{seen[name]}"
        else:
            seen[name] = 0
        out.append(name)
    return out


def _to_numeric(series: pd.Series, decimal: str) -> pd.Series:
    if pd.api.types.is_numeric_dtype(series):
        return series
    text = series.astype(str).str.strip()
    if decimal == ",":
        text = text.str.replace(",", ".", regex=False)
    return pd.to_numeric(text, errors="coerce")


def _finalize(df: pd.DataFrame, decimal: str = ".") -> pd.DataFrame:
    """Convierte a numérico lo convertible y elimina columnas/filas vacías."""
    out = {}
    for col in df.columns:
        converted = _to_numeric(df[col], decimal)
        if converted.notna().mean() >= 0.5:
            out[col] = converted
        elif df[col].notna().any() and df[col].astype(str).str.strip().ne("").any():
            out[col] = df[col]  # columna de texto (p. ej. "Current range")
    result = pd.DataFrame(out)
    numeric_cols = [c for c in result.columns if pd.api.types.is_numeric_dtype(result[c])]
    if not numeric_cols:
        raise NovaFormatError("El archivo no contiene columnas numéricas.")
    result = result.dropna(subset=numeric_cols, how="all").reset_index(drop=True)
    return result


def _parse_text(text: str) -> pd.DataFrame:
    lines = [line.rstrip("\r") for line in text.splitlines()]
    nonempty = [line for line in lines if line.strip()]
    if not nonempty:
        raise NovaFormatError("El archivo está vacío.")
    delim = _detect_delimiter(nonempty)
    header_idx, data_idx = _find_header(lines, delim)

    data_lines = [line for line in lines[data_idx:] if line.strip()]
    rows = [_split(line, delim) for line in data_lines]
    if header_idx is not None:
        header = _split(lines[header_idx], delim)
    else:
        header = []
    ncols = max(len(header), max(len(r) for r in rows))
    header = _unique_names(header + [""] * (ncols - len(header)))
    rows = [r + [""] * (ncols - len(r)) if len(r) < ncols else r[:ncols] for r in rows]

    decimal = "."
    if delim != ",":
        sample = data_lines[:500]
        if any(re.search(r"\d,\d", line) for line in sample):
            decimal = ","
    df = pd.DataFrame(rows, columns=header).replace("", np.nan)
    return _finalize(df, decimal)


# --------------------------------------------------------------------------
# Excel
# --------------------------------------------------------------------------
def _frame_from_grid(raw: pd.DataFrame) -> Optional[pd.DataFrame]:
    raw = raw.dropna(how="all").dropna(axis=1, how="all").reset_index(drop=True)
    if raw.empty:
        return None
    as_text = raw.astype(str).where(raw.notna(), "")
    header_row = None
    for i in range(min(50, len(raw) - 1)):
        row = [v for v in as_text.iloc[i].tolist() if v != ""]
        nxt = [v for v in as_text.iloc[i + 1].tolist() if v != ""]
        if len(row) >= 2 and _numeric_fraction(row) < 0.5 and _numeric_fraction(nxt) >= 0.5:
            header_row = i
            break
        if len(row) >= 2 and _numeric_fraction(row) >= 0.5:
            break  # sin cabecera
    if header_row is None:
        df = raw.copy()
        df.columns = [f"col_{k + 1}" for k in range(df.shape[1])]
    else:
        names = _unique_names([str(v) if v != "" else "" for v in as_text.iloc[header_row].tolist()])
        df = raw.iloc[header_row + 1:].copy()
        df.columns = names
    decimal = "," if df.astype(str).apply(lambda s: s.str.contains(r"\d,\d", regex=True)).any().any() else "."
    try:
        return _finalize(df.reset_index(drop=True), decimal)
    except NovaFormatError:
        return None


def _parse_excel(data: bytes) -> pd.DataFrame:
    try:
        sheets = pd.read_excel(io.BytesIO(data), sheet_name=None, header=None)
    except ImportError as exc:  # pragma: no cover - depende del entorno
        raise NovaFormatError(
            "Falta la librería para leer este Excel (instale 'openpyxl' para .xlsx o 'xlrd' para .xls)."
        ) from exc
    fallback = None
    for _name, raw in sheets.items():
        df = _frame_from_grid(raw)
        if df is None:
            continue
        mapping = detect_columns(df)
        if "potential" in mapping and "current" in mapping:
            return df
        if fallback is None:
            fallback = df
    if fallback is None:
        raise NovaFormatError("Ninguna hoja del Excel contiene datos numéricos.")
    return fallback


# --------------------------------------------------------------------------
# API pública
# --------------------------------------------------------------------------
def load_table(source, filename: Optional[str] = None) -> pd.DataFrame:
    """Lee un archivo exportado de NOVA y devuelve la tabla con sus columnas originales."""
    data, detected_name = _read_source(source)
    name = filename or detected_name
    suffix = Path(name).suffix.lower() if name else ""
    if suffix == ".nox":
        raise NovaFormatError(
            "Los archivos .nox son el formato interno de NOVA. Exporte los datos como ASCII (.txt) o Excel."
        )
    is_zip = data[:4] == b"PK\x03\x04"
    is_ole = data[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
    if is_zip or is_ole or suffix in EXCEL_EXTENSIONS:
        return _parse_excel(data)
    return _parse_text(_decode(data))


def to_cvdata(
    df: pd.DataFrame,
    mapping: Optional[Dict[str, str]] = None,
    source: str = "",
) -> CVData:
    """Convierte la tabla en :class:`CVData` (unidades SI y orden temporal)."""
    mapping = dict(mapping) if mapping else detect_columns(df)
    missing = [ROLE_LABELS[r] for r in ("potential", "current") if r not in mapping]
    if missing:
        raise NovaFormatError(
            "No se encontró la columna de " + " ni de ".join(missing).lower()
            + ". Columnas disponibles: " + ", ".join(map(str, df.columns))
        )
    notes: List[str] = []
    work = pd.DataFrame(index=df.index)
    for role, col in mapping.items():
        if col not in df.columns:
            raise NovaFormatError(f"La columna '{col}' no existe en el archivo.")
        values = pd.to_numeric(df[col], errors="coerce").astype(float)
        factor, unit = unit_factor(role, col)
        if unit and role in _UNIT_FACTORS and unit.replace(" ", "") not in _UNIT_FACTORS[role]:
            notes.append(f"Unidad '{unit}' de la columna '{col}' no reconocida: se asume SI.")
        work[role] = values * factor

    required = ["potential", "current"] + (["time"] if "time" in work else [])
    before = len(work)
    work = work.dropna(subset=required)
    if len(work) < before:
        notes.append(f"Se descartaron {before - len(work)} filas sin datos.")
    if len(work) < 10:
        raise NovaFormatError("Hay muy pocos puntos para analizar una CV.")

    order_key = "time" if "time" in work else ("index" if "index" in work else None)
    if order_key is not None and not work[order_key].is_monotonic_increasing:
        work = work.sort_values(order_key, kind="mergesort")
        notes.append(
            f"Las filas no estaban en orden temporal; se reordenaron por {ROLE_LABELS[order_key].lower()}."
        )
    if order_key is None:
        notes.append("Sin columna de tiempo ni de índice: se usa el orden de las filas del archivo.")
    work = work.reset_index(drop=True)

    def col(role):
        return work[role].to_numpy() if role in work else None

    return CVData(
        potential_V=col("potential"),
        current_A=col("current"),
        time_s=col("time"),
        scan=col("scan"),
        q_plus_C=col("q_plus"),
        q_minus_C=col("q_minus"),
        source=source,
        columns=mapping,
        notes=notes,
    )


def read_nova(source, filename: Optional[str] = None, mapping: Optional[Dict[str, str]] = None) -> CVData:
    """Atajo: lee el archivo y devuelve directamente :class:`CVData`."""
    data, detected = _read_source(source)
    name = filename or detected or ""
    df = load_table(data, name)
    return to_cvdata(df, mapping, source=name)
