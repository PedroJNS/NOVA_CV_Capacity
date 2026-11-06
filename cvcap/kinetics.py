"""Cinética a partir de varias CV medidas a distinta velocidad de barrido.

Tres análisis complementarios, todos sobre un mismo ciclo de cada archivo:

* **Exponente b** (ley de potencias ``i_p = a·v^b``): regresión de ``log|i_p|`` frente a ``log v``.
  ``b ≈ 0,5`` indica control difusivo (inserción en el sólido), ``b ≈ 1`` comportamiento capacitivo o
  superficial y los valores intermedios un proceso mixto (mismos umbrales que la «Calculadora CV»).
* **Ajuste lineal a √v** (Randles–Ševčík): pendiente de ``|i_p|`` frente a ``v^½`` y, si se conocen el área
  y la concentración, un coeficiente de difusión aparente.
* **Separación capacitiva/difusiva de Dunn**: a cada potencial se ajusta ``i(E, v) = k1·v + k2·v^½`` y se
  obtiene la fracción de carga capacitiva de cada velocidad.

Las corrientes están en A y las velocidades en mV/s salvo que se indique otra cosa.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from .analysis import AnalysisResult
from .i18n import CvcapError, t

B_DIFFUSIVE_MAX = 0.65  # b por debajo: difusivo
B_CAPACITIVE_MIN = 0.85  # b por encima: capacitivo
RANDLES_SEVCIK_25C = 2.69e5  # C·mol⁻¹·V⁻½ a 25 °C (A en cm², C en mol/cm³, v en V/s, D en cm²/s)

B_COLUMNS = ["name", "kind", "n", "b", "a", "r2", "regime"]
SQRT_COLUMNS = ["name", "kind", "n", "slope", "intercept", "r2"]


def classify_b(b: float) -> str:
    """Clave del régimen: ``diffusive``, ``mixed`` o ``capacitive``."""
    if b is None or not np.isfinite(b):
        return ""
    if b < B_DIFFUSIVE_MAX:
        return "diffusive"
    if b > B_CAPACITIVE_MIN:
        return "capacitive"
    return "mixed"


def _linear_fit(x: np.ndarray, y: np.ndarray) -> Optional[Tuple[float, float, float]]:
    """Pendiente, ordenada y R² de ``y = m·x + c``; ``None`` si no hay al menos dos valores de x distintos."""
    x, y = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    ok = np.isfinite(x) & np.isfinite(y)
    x, y = x[ok], y[ok]
    if len(x) < 2 or np.ptp(x) == 0:
        return None
    slope, intercept = np.polyfit(x, y, 1)
    resid = y - (slope * x + intercept)
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    r2 = 1.0 - float(np.sum(resid ** 2)) / ss_tot if ss_tot > 0 else 1.0
    return float(slope), float(intercept), r2


# --------------------------------------------------------------------------
# Corrientes de pico por velocidad
# --------------------------------------------------------------------------
def peak_currents_by_rate(entries: Sequence[Tuple[Optional[float], pd.DataFrame]], cycle: int) -> pd.DataFrame:
    """Reúne los picos del ciclo ``cycle`` de cada archivo.

    ``entries`` = ``[(velocidad mV/s, tabla de picos de cvcap.peaks), ...]``. Se descartan los picos
    marcados como «en el borde» (no son picos verdaderos) y los archivos sin velocidad válida.
    """
    rows = []
    for rate, peaks in entries:
        if peaks is None or peaks.empty or not rate or rate <= 0:
            continue
        sub = peaks[peaks["cycle"] == cycle]
        if "edge" in sub:
            sub = sub[~sub["edge"].astype(bool)]
        for r in sub.itertuples(index=False):
            rows.append({"name": r.name, "kind": r.kind, "rate": float(rate),
                         "e_peak": float(r.e_peak), "i_peak": float(r.i_peak)})
    return pd.DataFrame(rows, columns=["name", "kind", "rate", "e_peak", "i_peak"])


def b_table(currents: pd.DataFrame) -> pd.DataFrame:
    """Exponente b, factor a, R² y régimen de cada pico (necesita ≥ 2 velocidades distintas)."""
    rows = []
    if currents.empty:
        return pd.DataFrame(columns=B_COLUMNS)
    for (name, kind), g in currents.groupby(["name", "kind"], sort=False):
        g = g[(g["rate"] > 0) & (g["i_peak"] != 0)]
        fit = _linear_fit(np.log10(g["rate"]), np.log10(g["i_peak"].abs()))
        if fit is None:
            continue
        b, log_a, r2 = fit
        rows.append({"name": name, "kind": kind, "n": int(len(g)), "b": b, "a": 10 ** log_a, "r2": r2,
                     "regime": classify_b(b)})
    return pd.DataFrame(rows, columns=B_COLUMNS)


def sqrt_rate_table(currents: pd.DataFrame) -> pd.DataFrame:
    """Pendiente de ``|i_p|`` (A) frente a ``√v`` (con v en V/s): A/(V/s)^½."""
    rows = []
    if currents.empty:
        return pd.DataFrame(columns=SQRT_COLUMNS)
    for (name, kind), g in currents.groupby(["name", "kind"], sort=False):
        g = g[g["rate"] > 0]
        fit = _linear_fit(np.sqrt(g["rate"] / 1000.0), g["i_peak"].abs())
        if fit is None:
            continue
        slope, intercept, r2 = fit
        rows.append({"name": name, "kind": kind, "n": int(len(g)), "slope": slope, "intercept": intercept,
                     "r2": r2})
    return pd.DataFrame(rows, columns=SQRT_COLUMNS)


def randles_sevcik_D(slope_A_per_sqrt_Vs: float, n_electrons: float, area_cm2: float,
                     concentration_mol_cm3: float) -> float:
    """Coeficiente de difusión aparente (cm²/s) desde la pendiente de ``i_p`` frente a ``v^½`` (25 °C).

    ``i_p = 2,69·10⁵ · n^{3/2} · A · C · D^{1/2} · v^{1/2}`` (proceso reversible, difusión semiinfinita).
    En materiales de inserción es solo una estimación de orden de magnitud: ``C`` es la concentración de
    Li en el sólido y ``A`` el área real de contacto, ambas difíciles de fijar.
    """
    if not (n_electrons and area_cm2 and concentration_mol_cm3) or min(n_electrons, area_cm2,
                                                                         concentration_mol_cm3) <= 0:
        raise CvcapError("err.rs_inputs")
    return float((abs(slope_A_per_sqrt_Vs) / (RANDLES_SEVCIK_25C * n_electrons ** 1.5 * area_cm2
                                              * concentration_mol_cm3)) ** 2)


# --------------------------------------------------------------------------
# Separación capacitiva / difusiva (Dunn)
# --------------------------------------------------------------------------
@dataclass
class DunnResult:
    potential: np.ndarray  # V, cuadrícula común creciente
    rates: List[float]  # mV/s
    i_total: np.ndarray  # (n_velocidades, n_potenciales) en A
    i_cap: np.ndarray  # k1·v
    k1: np.ndarray  # A/(mV/s)
    k2: np.ndarray  # A/(mV/s)^½
    fractions: pd.DataFrame  # rate, cap_pct, diff_pct


def sweep_of(result: AnalysisResult, cycle: int, kind: str):
    """Potencial y corriente (A) del barrido ``kind`` del ciclo ``cycle``, o ``None``."""
    seg = result.segments
    mask = (seg["kind"] == kind) & (seg["cycle"].astype("float") == float(cycle))
    row = seg[mask]
    if row.empty:
        return None
    a, b = int(row["start"].iloc[0]), int(row["stop"].iloc[0])
    return result.cv.potential_V[a:b + 1], result.current_A[a:b + 1]


def _trapz(y: np.ndarray, x: np.ndarray) -> float:
    return float(np.trapezoid(y, x)) if hasattr(np, "trapezoid") else float(np.trapz(y, x))


def dunn_separation(sweeps: Sequence[Tuple[float, np.ndarray, np.ndarray]], n_points: int = 200,
                    edge_trim: float = 0.03) -> DunnResult:
    """Ajusta ``i = k1·v + k2·v^½`` a cada potencial común de varios barridos (≥ 2 velocidades).

    ``sweeps`` = ``[(velocidad mV/s, E, I), ...]`` con barridos de un mismo sentido. La fracción capacitiva
    de cada velocidad es ``∫|k1·v|dE / ∫|i|dE`` en el intervalo de potencial común (se descarta una fracción
    ``edge_trim`` en cada extremo, donde la corriente cambia de signo por el vértice).
    """
    prepared = []
    for rate, e, i in sweeps:
        if not rate or rate <= 0:
            continue
        e, i = np.asarray(e, dtype=float), np.asarray(i, dtype=float)
        order = np.argsort(e, kind="stable")
        prepared.append((float(rate), e[order], i[order]))
    rates = sorted({r for r, _, _ in prepared})
    if len(rates) < 2:
        raise CvcapError("err.dunn_rates")
    lo = max(e.min() for _, e, _ in prepared)
    hi = min(e.max() for _, e, _ in prepared)
    if hi - lo <= 0:
        raise CvcapError("err.dunn_range")
    span = hi - lo
    grid = np.linspace(lo + edge_trim * span, hi - edge_trim * span, n_points)
    prepared.sort(key=lambda p: p[0])
    v = np.array([p[0] for p in prepared])
    current = np.vstack([np.interp(grid, e, i) for _, e, i in prepared])
    x = np.sqrt(v)
    # i/√v = k1·√v + k2  → regresión lineal a cada potencial (mínimos cuadrados vectorizados)
    y = current / x[:, None]
    x_mean, y_mean = x.mean(), y.mean(axis=0)
    sxx = np.sum((x - x_mean) ** 2)
    k1 = np.sum((x - x_mean)[:, None] * (y - y_mean), axis=0) / sxx
    k2 = y_mean - k1 * x_mean
    i_cap = k1[None, :] * v[:, None]
    rows = []
    for idx, rate in enumerate(v):
        total = _trapz(np.abs(current[idx]), grid)
        cap = _trapz(np.abs(i_cap[idx]), grid)
        pct = cap / total * 100.0 if total else float("nan")
        rows.append({"rate": float(rate), "cap_pct": pct, "diff_pct": 100.0 - pct})
    return DunnResult(potential=grid, rates=[float(r) for r in v], i_total=current, i_cap=i_cap, k1=k1, k2=k2,
                      fractions=pd.DataFrame(rows))


def dunn_from_results(entries: Sequence[Tuple[Optional[float], AnalysisResult]], cycle: int, kind: str,
                      **kwargs) -> DunnResult:
    """Atajo: toma el barrido ``kind`` del ciclo ``cycle`` de cada análisis y llama a :func:`dunn_separation`."""
    sweeps = []
    for rate, result in entries:
        found = sweep_of(result, cycle, kind)
        if found is not None and rate:
            sweeps.append((rate, found[0], found[1]))
    return dunn_separation(sweeps, **kwargs)


def localize_b_table(table: pd.DataFrame, lang: str = "es") -> pd.DataFrame:
    df = table.copy()
    df["kind"] = df["kind"].map(lambda k: t(f"kind_short.{k}", lang))
    if "regime" in df:
        df["regime"] = df["regime"].map(lambda r: t(f"regime.{r}", lang) if r else "")
    names = {"name": t("pk.name", lang), "kind": t("pk.kind", lang)}
    return df.rename(columns={c: names.get(c) or t(f"kin.{c}", lang) for c in df.columns})


def localize_sqrt_table(table: pd.DataFrame, lang: str = "es") -> pd.DataFrame:
    return localize_b_table(table, lang)


def regime_summary(b_df: pd.DataFrame) -> Dict[str, int]:
    """Número de picos de cada régimen (para resúmenes rápidos)."""
    return b_df["regime"].value_counts().to_dict() if not b_df.empty else {}


__all__ = [
    "B_DIFFUSIVE_MAX", "B_CAPACITIVE_MIN", "DunnResult", "b_table", "classify_b", "localize_b_table", "localize_sqrt_table", "dunn_from_results",
    "dunn_separation", "peak_currents_by_rate", "randles_sevcik_D", "regime_summary", "sqrt_rate_table",
    "sweep_of",
]
