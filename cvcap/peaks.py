"""Localización de picos en cada ciclo de la CV.

Dos modos complementarios:

* **Ventanas con nombre** (recomendado para comparar ciclos): para cada ventana
  (nombre, barrido catódico/anódico, E mín, E máx) se busca en cada ciclo el
  extremo de corriente dentro de la ventana — el mínimo en el barrido catódico y
  el máximo en el anódico. Si el extremo cae en el borde de la ventana se marca
  como ``edge`` (no es un pico verdadero: amplíe o desplace la ventana).
* **Detección automática** con :func:`scipy.signal.find_peaks` sobre la corriente
  suavizada, con una prominencia mínima relativa a la corriente máxima.

La corriente se suaviza con un filtro de Savitzky-Golay antes de buscar los picos.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable, List, Optional

import numpy as np
import pandas as pd

try:  # SciPy es opcional: sin él se usa una media móvil y no hay detección automática
    from scipy.signal import find_peaks, savgol_filter
except ImportError:  # pragma: no cover
    find_peaks = savgol_filter = None

from .analysis import ANODIC, CATHODIC, AnalysisResult

PEAK_COLUMNS = ["cycle", "name", "kind", "e_peak", "i_peak", "edge"]


@dataclass
class PeakWindow:
    name: str
    kind: str  # "cathodic" o "anodic"
    e_min: float
    e_max: float

    def to_dict(self):
        return asdict(self)


def default_windows(lang: str = "es") -> List[PeakWindow]:
    """Ventanas típicas para un ánodo de grafito frente a Li⁺/Li."""
    from .i18n import t

    return [
        PeakWindow(t("peak.sei", lang), CATHODIC, 0.40, 1.00),
        PeakWindow(t("peak.lithiation", lang), CATHODIC, 0.03, 0.25),
        PeakWindow(t("peak.delithiation", lang), ANODIC, 0.10, 0.50),
    ]


def windows_from_records(records: Iterable[dict]) -> List[PeakWindow]:
    out = []
    for r in records:
        try:
            name = str(r.get("name", "")).strip()
            kind = r.get("kind")
            lo, hi = float(r.get("e_min")), float(r.get("e_max"))
        except (TypeError, ValueError):
            continue
        if not name or kind not in (CATHODIC, ANODIC) or not np.isfinite(lo) or not np.isfinite(hi):
            continue
        out.append(PeakWindow(name, kind, min(lo, hi), max(lo, hi)))
    return out


def smooth(current: np.ndarray, points: int = 7) -> np.ndarray:
    current = np.asarray(current, dtype=float)
    if points < 3 or len(current) < points + 2:
        return current.copy()
    points = points if points % 2 else points + 1
    if savgol_filter is not None:
        return savgol_filter(current, points, 2)
    kernel = np.ones(points) / points  # pragma: no cover
    return np.convolve(current, kernel, mode="same")  # pragma: no cover


def _segments_of(result: AnalysisResult):
    seg = result.segments
    for row in seg.itertuples(index=False):
        if row.cycle is None or pd.isna(row.cycle):
            continue
        yield int(row.cycle), row.kind, int(row.start), int(row.stop)


def window_peaks(result: AnalysisResult, windows: List[PeakWindow], smooth_points: int = 7) -> pd.DataFrame:
    """Extremo de corriente de cada ventana en cada ciclo."""
    e_all = result.cv.potential_V
    rows = []
    for cycle, kind, a, b in _segments_of(result):
        e = e_all[a:b + 1]
        i = smooth(result.current_A[a:b + 1], smooth_points)
        for w in windows:
            if w.kind != kind:
                continue
            idx = np.flatnonzero((e >= w.e_min) & (e <= w.e_max))
            if len(idx) < 3:
                continue
            local = idx[np.argmin(i[idx])] if kind == CATHODIC else idx[np.argmax(i[idx])]
            margin = max(1, int(0.02 * len(idx)))
            edge = bool(local <= idx[0] + margin - 1 or local >= idx[-1] - margin + 1)
            rows.append({"cycle": cycle, "name": w.name, "kind": kind,
                         "e_peak": float(e[local]), "i_peak": float(i[local]), "edge": edge})
    return pd.DataFrame(rows, columns=PEAK_COLUMNS)


def auto_peaks(result: AnalysisResult, prominence: float = 0.05, smooth_points: int = 9,
               end_margin: float = 0.03) -> pd.DataFrame:
    """Picos detectados automáticamente en cada barrido.

    prominence: prominencia mínima como fracción de la corriente máxima en valor absoluto.
    end_margin: fracción del barrido junto a los vértices que se ignora.
    """
    if find_peaks is None:  # pragma: no cover
        return pd.DataFrame(columns=PEAK_COLUMNS)
    e_all = result.cv.potential_V
    scale = float(np.nanmax(np.abs(result.current_A))) or 1.0
    rows = []
    for cycle, kind, a, b in _segments_of(result):
        e = e_all[a:b + 1]
        i = smooth(result.current_A[a:b + 1], smooth_points)
        signal = -i if kind == CATHODIC else i
        found, _props = find_peaks(signal, prominence=prominence * scale)
        n = len(e)
        found = [p for p in found if end_margin * n <= p <= (1 - end_margin) * n]
        found = sorted(found, key=lambda p: e[p])
        prefix = "C" if kind == CATHODIC else "A"
        for k, p in enumerate(found, start=1):
            rows.append({"cycle": cycle, "name": f"{prefix}{k}", "kind": kind,
                         "e_peak": float(e[p]), "i_peak": float(i[p]), "edge": False})
    return pd.DataFrame(rows, columns=PEAK_COLUMNS)


def add_reference_shifts(peaks: pd.DataFrame, reference_cycle: int) -> pd.DataFrame:
    """Añade el desplazamiento de potencial (mV) y el cambio de corriente (%) respecto al ciclo de referencia."""
    df = peaks.copy()
    df["de_ref"] = np.nan
    df["di_ref"] = np.nan
    for name, group in df.groupby("name"):
        ref = group[group["cycle"] == reference_cycle]
        if ref.empty:
            continue
        e0, i0 = ref["e_peak"].iloc[0], ref["i_peak"].iloc[0]
        mask = df["name"] == name
        df.loc[mask, "de_ref"] = (df.loc[mask, "e_peak"] - e0) * 1000
        if i0:
            df.loc[mask, "di_ref"] = (df.loc[mask, "i_peak"] - i0) / abs(i0) * 100
    return df


def peak_separation(peaks: pd.DataFrame, anodic_name: str, cathodic_name: str) -> pd.DataFrame:
    """ΔEp = E(pico anódico) − E(pico catódico) por ciclo, en mV."""
    a = peaks[peaks["name"] == anodic_name][["cycle", "e_peak"]].rename(columns={"e_peak": "e_a"})
    c = peaks[peaks["name"] == cathodic_name][["cycle", "e_peak"]].rename(columns={"e_peak": "e_c"})
    merged = a.merge(c, on="cycle", how="inner").sort_values("cycle")
    merged["dep"] = (merged["e_a"] - merged["e_c"]) * 1000
    return merged.reset_index(drop=True)
