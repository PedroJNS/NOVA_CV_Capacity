"""Utilidades electroquímicas: capacidad teórica, electrones por fórmula, C-rate y ciclado galvanostático.

Incorpora las partes generales de la «Calculadora CV» (hojas *Calculadora* y *Galvanostatico*):

* capacidad teórica ``n·F / (3,6·M)`` y porcentaje alcanzado en cada ciclo;
* electrones (o Li) intercambiados por unidad formular, p. ej. *x* en LixC6 para el grafito;
* corrección por el aporte de un aditivo (blanco del carbón conductor);
* corriente a programar para un C-rate dado;
* tabla de ciclado galvanostático (capacidad, eficiencia coulómbica y retención).

Todas las funciones son puras (numpy/pandas) y no dependen de la interfaz.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

import numpy as np
import pandas as pd

from .i18n import CvcapError, t

FARADAY = 96485.33212  # C/mol
MAH_PER_MOL_E = FARADAY / 3.6  # 26 801,48 mAh por mol de electrones


@dataclass(frozen=True)
class ReferenceMaterial:
    """Material de referencia: masa molar (g/mol) y electrones por unidad formular."""

    key: str
    molar_mass: float
    n_electrons: float


# Valores por defecto de la lista desplegable de la app
REFERENCE_MATERIALS: Dict[str, ReferenceMaterial] = {
    "graphite": ReferenceMaterial("graphite", 72.066, 1.0),  # C6 + Li → LiC6 (372 mAh/g)
    "ptcda": ReferenceMaterial("ptcda", 392.32, 2.0),  # 2 e⁻ → 136,6 mAh/g; 4 e⁻ → 273,3 mAh/g
    "custom": ReferenceMaterial("custom", 100.0, 1.0),
}


def theoretical_capacity(n_electrons: float, molar_mass: float) -> float:
    """Capacidad teórica en mAh/g para ``n_electrons`` por unidad formular de masa ``molar_mass`` (g/mol)."""
    if not molar_mass or molar_mass <= 0:
        raise CvcapError("err.molar_mass")
    return float(n_electrons) * MAH_PER_MOL_E / float(molar_mass)


def electrons_per_formula(charge_C, mass_mg, molar_mass: float):
    """Electrones por unidad formular = Q / (F · n_mol). Admite escalares o arrays."""
    if not mass_mg or mass_mg <= 0 or not molar_mass or molar_mass <= 0:
        raise CvcapError("err.mass_molar")
    moles = (mass_mg / 1000.0) / molar_mass
    return np.asarray(charge_C, dtype=float) / FARADAY / moles


def c_rate_current_mA(mass_mg: float, reference_capacity_mAh_g: float, c_rate: float) -> float:
    """Corriente (mA) para un C-rate: ``I = C-rate · Q_ref(mAh/g) · m(g)``. 1C = vaciar Q_ref en 1 h."""
    if not mass_mg or mass_mg <= 0:
        raise CvcapError("err.mass_needed")
    return float(c_rate) * float(reference_capacity_mAh_g) * mass_mg / 1000.0


def c_rate_from_current(current_mA: float, mass_mg: float, reference_capacity_mAh_g: float) -> float:
    """Operación inversa de :func:`c_rate_current_mA`."""
    full = c_rate_current_mA(mass_mg, reference_capacity_mAh_g, 1.0)
    return float(current_mA) / full if full else float("nan")


def current_density_mA_g(current_mA: float, mass_mg: float) -> float:
    if not mass_mg or mass_mg <= 0:
        raise CvcapError("err.mass_needed")
    return float(current_mA) / (mass_mg / 1000.0)


# --------------------------------------------------------------------------
# Referencia teórica sobre la tabla de ciclos de una CV
# --------------------------------------------------------------------------
THEORY_COLUMNS = ["cycle", "cap_lit", "cap_delit", "x_lit", "x_delit", "pct_lit", "pct_delit"]


def theory_table(
    cycles: pd.DataFrame,
    mass_mg: float,
    molar_mass: float,
    n_electrons: float,
    additive_mass_mg: float = 0.0,
    additive_capacity_mAh_g: float = 0.0,
) -> pd.DataFrame:
    """Capacidad corregida, electrones (Li) por unidad formular y % de la teórica en cada ciclo.

    ``cycles`` es la tabla de :func:`cvcap.analysis.analyze` (columnas ``q_lit`` y ``q_delit`` en C).
    La corrección por el blanco resta ``additive_capacity · m_aditivo`` (mAh) de las dos cargas antes de
    dividir por la masa activa; con ``additive_mass_mg = 0`` no cambia nada.
    """
    if not mass_mg or mass_mg <= 0:
        raise CvcapError("err.mass_needed")
    blank_C = max(additive_mass_mg or 0.0, 0.0) / 1000.0 * (additive_capacity_mAh_g or 0.0) * 3.6
    theo = theoretical_capacity(n_electrons, molar_mass)
    out = pd.DataFrame({"cycle": cycles["cycle"].astype(int)})
    for tag in ("lit", "delit"):
        q = cycles[f"q_{tag}"].to_numpy(dtype=float) - blank_C
        out[f"cap_{tag}"] = q / 3.6 / (mass_mg / 1000.0)
        out[f"x_{tag}"] = electrons_per_formula(q, mass_mg, molar_mass)
        out[f"pct_{tag}"] = out[f"cap_{tag}"] / theo * 100.0
    return out[THEORY_COLUMNS]


# --------------------------------------------------------------------------
# Ciclado galvanostático
# --------------------------------------------------------------------------
GCD_INPUT_COLUMNS = ["cycle", "q_lit_mAh", "q_delit_mAh", "t_lit_h", "t_delit_h"]
GCD_RESULT_COLUMNS = ["cycle", "cap_lit", "cap_delit", "ce", "ret"]


def gcd_table(
    data: pd.DataFrame,
    mass_mg: float,
    current_mA: Optional[float] = None,
    reference_cycle: int = 1,
) -> pd.DataFrame:
    """Capacidad específica, eficiencia coulómbica (delit./lit.) y retención de una tabla de ciclado.

    Para cada semiciclo se usa la capacidad (mAh) si está rellena y, si no, el tiempo (h) × ``current_mA``.
    La retención se refiere a la capacidad de delitiación del ciclo ``reference_cycle`` (o del primero
    disponible si ese no existe).
    """
    if not mass_mg or mass_mg <= 0:
        raise CvcapError("err.mass_needed")
    df = data.copy()
    for col in GCD_INPUT_COLUMNS:
        if col not in df.columns:
            df[col] = np.nan
    df = df[GCD_INPUT_COLUMNS].apply(pd.to_numeric, errors="coerce")
    df = df[df["cycle"].notna()].sort_values("cycle")

    def charge_mAh(q: pd.Series, hours: pd.Series) -> pd.Series:
        from_time = hours * current_mA if current_mA else pd.Series(np.nan, index=hours.index)
        return q.where(q.notna(), from_time)

    q_lit = charge_mAh(df["q_lit_mAh"], df["t_lit_h"])
    q_delit = charge_mAh(df["q_delit_mAh"], df["t_delit_h"])
    mass_g = mass_mg / 1000.0
    out = pd.DataFrame({"cycle": df["cycle"].astype(int)})
    out["cap_lit"] = q_lit / mass_g
    out["cap_delit"] = q_delit / mass_g
    out["ce"] = q_delit / q_lit * 100.0
    valid = out[out["cap_delit"].notna()]
    ret = np.full(len(out), np.nan)
    if not valid.empty:
        ref = valid[valid["cycle"] == reference_cycle]
        base = (ref if not ref.empty else valid.iloc[[0]])["cap_delit"].iloc[0]
        if base:
            ret = out["cap_delit"].to_numpy() / base * 100.0
    out["ret"] = ret
    out = out.dropna(subset=["cap_lit", "cap_delit"], how="all")
    return out[GCD_RESULT_COLUMNS].reset_index(drop=True)


def localize_theory(table: pd.DataFrame, lang: str = "es") -> pd.DataFrame:
    return table.rename(columns={c: t(f"th.{c}", lang) for c in table.columns})


def localize_gcd(table: pd.DataFrame, lang: str = "es") -> pd.DataFrame:
    return table.rename(columns={c: t(f"col.{c}", lang) for c in table.columns})


__all__ = [
    "localize_theory", "localize_gcd",
    "FARADAY", "MAH_PER_MOL_E", "REFERENCE_MATERIALS", "ReferenceMaterial", "THEORY_COLUMNS",
    "GCD_INPUT_COLUMNS", "GCD_RESULT_COLUMNS", "theoretical_capacity", "electrons_per_formula",
    "c_rate_current_mA", "c_rate_from_current", "current_density_mA_g", "theory_table", "gcd_table",
]
