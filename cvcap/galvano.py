"""Análisis de medidas galvanostáticas (cronopotenciometría / carga-descarga) exportadas de NOVA.

Formato esperado (exportación ASCII de NOVA, p. ej. «Chrono charge discharge galvanostatic»)::

    Time (s);WE(1).Potential (V);Corrected time (s);Index;WE(1).Current (A);Current range;Cutoffs

Opcionalmente puede traer ``WE(1).Charge (C)`` (carga acumulada que calcula NOVA).

Convención: corriente negativa = litiación (catódica en un ánodo de grafito); positiva = delitiación.

Cada paso se identifica por el signo de la corriente, ignorando tramos de reposo (|I| pequeña).
La capacidad se obtiene integrando I·dt por paso y se normaliza con la masa activa
(mAh/g = |Q| / 3,6 / masa en g).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np
import pandas as pd

from . import io as cvio
from .i18n import CvcapError, Note

_trapezoid = getattr(np, "trapezoid", None) or np.trapz

#: Umbral relativo para separar reposo de corriente: |I| < FRAC · mediana(|I|) se considera reposo.
REST_FRACTION = 0.3

STEP_COLUMNS = ["step", "type", "t_start_s", "duration_s", "I_mean_uA", "Q_C", "cap_mAh_g", "E_start_V", "E_end_V"]
CYCLE_COLUMNS = ["cycle", "cap_lit", "cap_delit", "ce", "ret"]


@dataclass
class GalvanoData:
    """Serie temporal de una medida galvanostática, en unidades SI."""

    time_s: np.ndarray
    potential_V: np.ndarray
    current_A: np.ndarray
    charge_C: Optional[np.ndarray] = None
    source: str = ""
    notes: List[Note] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.time_s)


@dataclass
class GalvanoResult:
    """Resultado del análisis de una medida galvanostática."""

    name: str
    mass_mg: float
    steps: pd.DataFrame
    cycles: pd.DataFrame
    notes: List[Note] = field(default_factory=list)

    def summary(self) -> dict:
        lit = self.steps[self.steps["type"] == "lit"]
        dlt = self.steps[self.steps["type"] == "delit"]
        return {
            "name": self.name,
            "mass_mg": self.mass_mg,
            "n_steps": int(len(self.steps)),
            "n_cycles": int(len(self.cycles)),
            "first_lit_mAh_g": float(lit["cap_mAh_g"].iloc[0]) if len(lit) else None,
            "first_delit_mAh_g": float(dlt["cap_mAh_g"].iloc[0]) if len(dlt) else None,
            "first_ce_pct": float(self.cycles["ce"].iloc[0]) if len(self.cycles) and pd.notna(self.cycles["ce"].iloc[0]) else None,
        }


# --------------------------------------------------------------------------
# Lectura
# --------------------------------------------------------------------------
def _find(df: pd.DataFrame, *candidates: str) -> Optional[str]:
    """Columna cuyo nombre (sin unidades, en minúsculas) empieza por alguno de los candidatos."""
    parsed = {col: cvio.split_name_unit(col)[0] for col in df.columns}
    for cand in candidates:
        for col, base in parsed.items():
            if base == cand:
                return col
    for cand in candidates:
        for col, base in parsed.items():
            if base.startswith(cand):
                return col
    return None


def load_galvano(source, filename: Optional[str] = None) -> GalvanoData:
    """Lee un archivo galvanostático exportado de NOVA."""
    df = cvio.load_table(source, filename)
    name = filename or getattr(source, "name", "") or ""
    col_t = _find(df, "corrected time", "time", "tiempo")
    col_e = _find(df, "we(1).potential", "potential", "potencial")
    col_i = _find(df, "we(1).current", "current", "corriente")
    col_q = _find(df, "we(1).charge", "charge", "carga")
    if col_t is None or col_e is None or col_i is None:
        raise CvcapError("err.missing_columns", roles="time/potential/current", available=", ".join(map(str, df.columns)))

    notes: List[Note] = []
    t_factor, _ = cvio.unit_factor("time", col_t)
    e_factor, _ = cvio.unit_factor("potential", col_e)
    i_factor, _ = cvio.unit_factor("current", col_i)
    t = pd.to_numeric(df[col_t], errors="coerce").to_numpy(float) * t_factor
    e = pd.to_numeric(df[col_e], errors="coerce").to_numpy(float) * e_factor
    i = pd.to_numeric(df[col_i], errors="coerce").to_numpy(float) * i_factor
    q = None
    if col_q is not None:
        q_factor, _ = cvio.unit_factor("q_plus", col_q)
        q = pd.to_numeric(df[col_q], errors="coerce").to_numpy(float) * q_factor

    ok = np.isfinite(t) & np.isfinite(e) & np.isfinite(i)
    if q is not None:
        ok &= np.isfinite(q)
    t, e, i = t[ok], e[ok], i[ok]
    q = q[ok] if q is not None else None
    if len(t) < 10:
        raise CvcapError("err.too_few")
    if not np.all(np.diff(t) >= 0):
        order = np.argsort(t, kind="mergesort")
        t, e, i = t[order], e[order], i[order]
        q = q[order] if q is not None else None
        notes.append(Note("note.sorted_by_time"))
    return GalvanoData(time_s=t, potential_V=e, current_A=i, charge_C=q, source=name, notes=notes)


# --------------------------------------------------------------------------
# Pasos
# --------------------------------------------------------------------------
def _label_samples(current: np.ndarray) -> np.ndarray:
    """Etiqueta cada muestra como 'lit' (I<0), 'delit' (I>0) o 'rest' (|I| pequeña)."""
    mags = np.abs(current[current != 0])
    thr = REST_FRACTION * float(np.median(mags)) if mags.size else 0.0
    labels = np.where(current < -thr, "lit", np.where(current > thr, "delit", "rest"))
    return labels


def split_steps(data: GalvanoData, mass_mg: float) -> pd.DataFrame:
    """Tabla de pasos (litiación/delitiación/reposo) con duración, corriente, carga y capacidad."""
    if not mass_mg or mass_mg <= 0:
        raise CvcapError("err.mass_needed")
    mass_g = mass_mg / 1000.0
    labels = _label_samples(data.current_A)
    t, e, i = data.time_s, data.potential_V, data.current_A
    q_col = data.charge_C

    # Tramos contiguos con la misma etiqueta
    change = np.r_[True, labels[1:] != labels[:-1]]
    starts = np.flatnonzero(change)
    ends = np.r_[starts[1:], len(labels)] - 1

    rows = []
    step_no = 0
    for a, b in zip(starts, ends):
        kind = str(labels[a])
        if kind == "rest" or b <= a:
            continue
        step_no += 1
        seg_t = t[a:b + 1]
        seg_i = i[a:b + 1]
        # Carga por integración trapezoidal (valor absoluto, mAh = C/3,6)
        q_int = abs(float(_trapezoid(seg_i, seg_t)))
        if q_col is not None:
            q_nova = abs(float(q_col[b] - q_col[a]))
            q_used = q_nova if q_nova > 0 else q_int
        else:
            q_nova = np.nan
            q_used = q_int
        rows.append({
            "step": step_no,
            "type": kind,
            "t_start_s": float(seg_t[0]),
            "duration_s": float(seg_t[-1] - seg_t[0]),
            "I_mean_uA": float(np.mean(seg_i)) * 1e6,
            "Q_C": q_used,
            "cap_mAh_g": q_used / 3.6 / mass_g,
            "E_start_V": float(e[a]),
            "E_end_V": float(e[b]),
        })
    return pd.DataFrame(rows, columns=STEP_COLUMNS)


def cycles_table(steps: pd.DataFrame, reference_cycle: int = 1) -> pd.DataFrame:
    """Ciclos = cada delitiación con la litiación inmediatamente anterior.

    CE = capacidad de delitiación / capacidad de litiación previa (%).
    Retención = capacidad de delitiación respecto al ciclo de referencia (%).
    """
    rows = []
    prev_lit = None
    for _, s in steps.iterrows():
        if s["type"] == "lit":
            prev_lit = s["cap_mAh_g"]
        elif s["type"] == "delit":
            rows.append({"cycle": len(rows) + 1, "cap_lit": prev_lit if prev_lit is not None else np.nan,
                         "cap_delit": s["cap_mAh_g"]})
            prev_lit = None
    out = pd.DataFrame(rows, columns=["cycle", "cap_lit", "cap_delit"])
    if out.empty:
        return pd.DataFrame(columns=CYCLE_COLUMNS)
    out["ce"] = out["cap_delit"] / out["cap_lit"] * 100.0
    ref = out[out["cycle"] == reference_cycle]
    base = float((ref if not ref.empty else out.iloc[[0]])["cap_delit"].iloc[0])
    out["ret"] = out["cap_delit"] / base * 100.0 if base else np.nan
    return out[CYCLE_COLUMNS].reset_index(drop=True)


def analyze_galvano(data: GalvanoData, mass_mg: float, reference_cycle: int = 1, name: Optional[str] = None) -> GalvanoResult:
    """Análisis completo: pasos, ciclos, eficiencia y retención."""
    steps = split_steps(data, mass_mg)
    cycles = cycles_table(steps, reference_cycle)
    notes = list(data.notes)
    if steps.empty:
        notes.append(Note("note.no_steps"))
    return GalvanoResult(name=name or data.source, mass_mg=float(mass_mg), steps=steps, cycles=cycles, notes=notes)


__all__ = ["GalvanoData", "GalvanoResult", "load_galvano", "split_steps", "cycles_table", "analyze_galvano",
           "STEP_COLUMNS", "CYCLE_COLUMNS", "REST_FRACTION"]
