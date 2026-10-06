"""Cálculo de capacidad, eficiencia coulómbica y retención a partir de una CV.

Las tablas se generan con claves internas neutras (``cap_delit``, ``ce``…) y se
traducen al mostrarlas o exportarlas (:func:`localize_cycles`, etc.), de modo
que el mismo resultado sirve en español y en inglés.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from .i18n import CvcapError, Note, fmt_num, t
from .io import CVData

CATHODIC = "cathodic"
ANODIC = "anodic"

# Columnas internas de la tabla de ciclos, en orden de presentación
CYCLE_COLUMNS = [
    "cycle", "q_lit", "q_delit", "cap_lit", "cap_delit", "mah_lit", "mah_delit",
    "areal_delit", "ce", "irr", "ret",
]
SEGMENT_COLUMNS = [
    "segment", "kind", "cycle", "e_start", "e_end", "points", "duration", "rate",
    "q_net", "q_pos", "q_neg", "partial",
]
SUMMARY_KEYS = [
    "file", "method", "mass_mg", "n_cycles", "scan_rate", "ce1", "ce_mean",
    "cap_lit1", "cap_delit1", "irr1", "cap_delit_last", "ret_last",
]


def _trapz(y: np.ndarray, x: np.ndarray) -> float:
    if len(y) < 2:
        return 0.0
    if hasattr(np, "trapezoid"):
        return float(np.trapezoid(y, x))
    return float(np.trapz(y, x))  # pragma: no cover - numpy < 2


# --------------------------------------------------------------------------
# Segmentación
# --------------------------------------------------------------------------
def find_vertices(potential: np.ndarray, hysteresis: float = 0.02) -> List[int]:
    """Índices de inicio, vértices y final del barrido (algoritmo zigzag con histéresis)."""
    e = np.asarray(potential, dtype=float)
    n = len(e)
    if n < 2:
        return [0, max(n - 1, 0)]
    vertices = [0]
    direction = 0
    i_min = i_max = 0
    ext = 0
    for i in range(1, n):
        value = e[i]
        if direction == 0:
            if value > e[i_max]:
                i_max = i
            if value < e[i_min]:
                i_min = i
            if e[i_max] - e[i_min] >= hysteresis:
                if i_max > i_min:
                    direction, ext, first = 1, i_max, i_min
                else:
                    direction, ext, first = -1, i_min, i_max
                if first != 0 and abs(e[first] - e[0]) >= hysteresis:
                    vertices.append(first)
        elif direction == 1:
            if value >= e[ext]:
                ext = i
            elif e[ext] - value >= hysteresis:
                vertices.append(ext)
                direction, ext = -1, i
        else:
            if value <= e[ext]:
                ext = i
            elif value - e[ext] >= hysteresis:
                vertices.append(ext)
                direction, ext = 1, i
    if vertices[-1] != n - 1:
        vertices.append(n - 1)
    return vertices


@dataclass
class Segment:
    number: int
    kind: str  # CATHODIC o ANODIC
    start: int
    stop: int  # índice final incluido
    e_start: float
    e_end: float
    charge_C: float  # carga neta
    q_pos_C: float  # carga de la corriente positiva
    q_neg_C: float  # carga de la corriente negativa (negativa)
    duration_s: Optional[float]
    scan_rate_mV_s: Optional[float]
    partial: bool = False
    cycle: Optional[int] = None

    def flip_sign(self) -> None:
        self.charge_C = -self.charge_C
        self.q_pos_C, self.q_neg_C = -self.q_neg_C, -self.q_pos_C


def _segment_charges(cv, a, b, sign, current, scan_rate_V_s, window):
    e = cv.potential_V[a:b + 1]
    i = current[a:b + 1]
    if window is not None:
        lo, hi = min(window), max(window)
        i = np.where((e >= lo) & (e <= hi), i, 0.0)
    pos, neg = np.clip(i, 0, None), np.clip(i, None, 0)
    if cv.time_s is not None:
        tt = cv.time_s[a:b + 1]
        return _trapz(i, tt), _trapz(pos, tt), _trapz(neg, tt)
    if not scan_rate_V_s:
        raise CvcapError("err.no_time_rate")
    k = sign * scan_rate_V_s  # dt = dE / (dE/dt), con dE/dt = ±v
    return _trapz(i, e) / k, _trapz(pos, e) / k, _trapz(neg, e) / k


def split_segments(cv, current, hysteresis=0.02, scan_rate_V_s=None, window=None,
                   partial_threshold=0.9) -> List[Segment]:
    vertices = find_vertices(cv.potential_V, hysteresis)
    segments: List[Segment] = []
    for k in range(len(vertices) - 1):
        a, b = vertices[k], vertices[k + 1]
        if b - a < 2:
            continue
        e0, e1 = float(cv.potential_V[a]), float(cv.potential_V[b])
        sign = 1 if e1 > e0 else -1
        duration = rate = None
        if cv.time_s is not None:
            duration = float(cv.time_s[b] - cv.time_s[a])
            rate = abs(e1 - e0) / duration * 1e3 if duration > 0 else None
        elif scan_rate_V_s:
            rate = scan_rate_V_s * 1e3
        net, q_pos, q_neg = _segment_charges(cv, a, b, sign, current, scan_rate_V_s, window)
        segments.append(Segment(len(segments) + 1, ANODIC if sign > 0 else CATHODIC, a, b, e0, e1,
                                net, q_pos, q_neg, duration, rate))
    if segments:
        spans = np.array([abs(s.e_end - s.e_start) for s in segments])
        reference = float(np.median(spans))
        for seg, span in zip(segments, spans):
            seg.partial = bool(span < partial_threshold * reference)
    return segments


# --------------------------------------------------------------------------
# Resultado
# --------------------------------------------------------------------------
@dataclass
class AnalysisResult:
    name: str
    mass_mg: Optional[float]
    area_cm2: Optional[float]
    method: str
    reference_cycle: int
    cycles: pd.DataFrame  # columnas internas (CYCLE_COLUMNS)
    cycle_notes: Dict[int, List[Note]]
    segments: pd.DataFrame  # columnas internas (SEGMENT_COLUMNS)
    summary: Dict[str, object]  # claves internas (SUMMARY_KEYS)
    notes: List[Note]
    point_cycle: np.ndarray  # nº de ciclo de cada punto (0 = fuera de ciclo)
    cv: CVData
    current_A: np.ndarray  # corriente usada (signo corregido si hizo falta)
    nova_check: Optional[Dict[str, Tuple[float, float]]] = None
    params: Dict[str, object] = field(default_factory=dict)

    # Atajos de presentación
    def cycles_table(self, lang: str = "es") -> pd.DataFrame:
        return localize_cycles(self.cycles, self.cycle_notes, lang)

    def segments_table(self, lang: str = "es") -> pd.DataFrame:
        return localize_segments(self.segments, lang)

    def summary_row(self, lang: str = "es") -> Dict[str, object]:
        return localize_summary(self.summary, lang)

    def nova_table(self, lang: str = "es") -> Optional[pd.DataFrame]:
        return localize_nova_check(self.nova_check, lang)

    def notes_text(self, lang: str = "es") -> List[str]:
        return [n.text(lang) for n in self.notes]


def _nova_charge_check(cv: CVData, current: np.ndarray, flipped: bool):
    if cv.q_plus_C is None or cv.q_minus_C is None or cv.scan is None or cv.time_s is None:
        return None
    frame = pd.DataFrame({"scan": cv.scan, "qp": cv.q_plus_C, "qm": cv.q_minus_C})
    per_scan = frame.groupby("scan").agg(qp=("qp", "last"), qm=("qm", "last"))
    nova_pos, nova_neg = float(per_scan["qp"].sum()), float(per_scan["qm"].sum())
    if flipped:
        nova_pos, nova_neg = -nova_neg, -nova_pos
    ours_pos = _trapz(np.clip(current, 0, None), cv.time_s)
    ours_neg = _trapz(np.clip(current, None, 0), cv.time_s)
    return {"pos": (nova_pos, ours_pos), "neg": (nova_neg, ours_neg)}


def analyze(
    cv: CVData,
    mass_mg: Optional[float],
    area_cm2: Optional[float] = None,
    reference_cycle: int = 2,
    hysteresis: float = 0.02,
    scan_rate_V_s: Optional[float] = None,
    window: Optional[Tuple[float, float]] = None,
    auto_sign: bool = True,
    name: Optional[str] = None,
    method: str = "signo",
) -> AnalysisResult:
    """Analiza una CV y devuelve capacidades por ciclo.

    method: ``"signo"`` (litiación = corriente negativa del ciclo, delitiación =
    corriente positiva; recomendado para grafito) o ``"direccion"`` (carga neta
    de cada barrido).
    """
    if method not in ("signo", "direccion"):
        raise CvcapError("err.method")
    notes: List[Note] = list(cv.notes)
    current = np.asarray(cv.current_A, dtype=float).copy()
    segments = split_segments(cv, current, hysteresis, scan_rate_V_s, window)
    if not segments:
        raise CvcapError("err.no_sweeps")

    flipped = False
    if auto_sign:
        q_cat = sum(s.charge_C for s in segments if s.kind == CATHODIC)
        q_an = sum(s.charge_C for s in segments if s.kind == ANODIC)
        if q_cat > 0 and q_an < 0:
            current = -current
            for s in segments:
                s.flip_sign()
            flipped = True
            notes.append(Note("note.flipped"))

    pairs: List[Tuple[Segment, Optional[Segment]]] = []
    k = 0
    while k < len(segments):
        seg = segments[k]
        if seg.kind == ANODIC:
            if not pairs:
                notes.append(Note("note.leading_anodic", e0=seg.e_start, e1=seg.e_end))
            k += 1
            continue
        partner = segments[k + 1] if k + 1 < len(segments) and segments[k + 1].kind == ANODIC else None
        pairs.append((seg, partner))
        k += 2 if partner else 1
    if not pairs:
        raise CvcapError("err.no_cathodic")

    mass_g = mass_mg / 1000.0 if mass_mg and mass_mg > 0 else None
    if mass_g is None:
        notes.append(Note("note.no_mass"))

    rows, cycle_notes = [], {}
    for n, (cat, an) in enumerate(pairs, start=1):
        cat.cycle = n
        if an is not None:
            an.cycle = n
        if method == "signo":
            q_lit = -(cat.q_neg_C + (an.q_neg_C if an is not None else 0.0))
            q_delit = cat.q_pos_C + an.q_pos_C if an is not None else np.nan
        else:
            q_lit = -cat.charge_C
            q_delit = an.charge_C if an is not None else np.nan
        cnotes = []
        if cat.partial:
            cnotes.append(Note("cnote.partial_lit", e0=cat.e_start, e1=cat.e_end))
        if an is None:
            cnotes.append(Note("cnote.no_anodic"))
        elif an.partial:
            cnotes.append(Note("cnote.partial_delit", e0=an.e_start, e1=an.e_end))
        cycle_notes[n] = cnotes
        row = {
            "cycle": n,
            "q_lit": q_lit,
            "q_delit": q_delit,
            "mah_lit": q_lit / 3.6,
            "mah_delit": q_delit / 3.6,
            "ce": q_delit / q_lit * 100 if q_lit else np.nan,
        }
        if mass_g:
            row["cap_lit"] = q_lit / 3.6 / mass_g
            row["cap_delit"] = q_delit / 3.6 / mass_g
            row["irr"] = row["cap_lit"] - row["cap_delit"]
        if area_cm2:
            row["areal_delit"] = q_delit / 3.6 / area_cm2
        rows.append(row)

    cycles = pd.DataFrame(rows)
    base = "cap_delit" if mass_g else "mah_delit"
    ref = reference_cycle if 1 <= reference_cycle <= len(cycles) else 1
    if ref != reference_cycle:
        notes.append(Note("note.ref_fallback", n=len(cycles), ref=ref))
    ref_value = cycles.loc[cycles["cycle"] == ref, base].iloc[0]
    cycles["ret"] = cycles[base] / ref_value * 100 if ref_value else np.nan
    cycles = cycles[[c for c in CYCLE_COLUMNS if c in cycles.columns]]

    segments_df = pd.DataFrame([
        {
            "segment": s.number, "kind": s.kind, "cycle": s.cycle, "e_start": s.e_start,
            "e_end": s.e_end, "points": s.stop - s.start + 1, "duration": s.duration_s,
            "rate": s.scan_rate_mV_s, "q_net": s.charge_C, "q_pos": s.q_pos_C,
            "q_neg": s.q_neg_C, "partial": s.partial, "start": s.start, "stop": s.stop,
        }
        for s in segments
    ])

    point_cycle = np.zeros(len(cv), dtype=np.int32)
    for s in segments:
        if s.cycle is not None:
            point_cycle[s.start:s.stop + 1] = s.cycle

    rates = [s.scan_rate_mV_s for s in segments if s.scan_rate_mV_s]
    complete = cycles[cycles["q_delit"].notna()]
    later = complete[complete["cycle"] >= 2]
    summary: Dict[str, object] = {
        "file": name or cv.source,
        "method": method,
        "mass_mg": mass_mg if mass_g else None,
        "n_cycles": int(len(cycles)),
        "scan_rate": float(np.median(rates)) if rates else None,
        "ce1": float(cycles["ce"].iloc[0]),
        "ce_mean": float(later["ce"].mean()) if not later.empty else None,
        "ref_cycle": ref,
    }
    if mass_g:
        summary["cap_lit1"] = float(cycles["cap_lit"].iloc[0])
        summary["cap_delit1"] = float(cycles["cap_delit"].iloc[0])
        summary["irr1"] = float(cycles["irr"].iloc[0])
        if not complete.empty:
            summary["cap_delit_last"] = float(complete["cap_delit"].iloc[-1])
    if not complete.empty:
        summary["ret_last"] = float(complete["ret"].iloc[-1])
    if window is not None:
        notes.append(Note("note.window", lo=min(window), hi=max(window)))

    return AnalysisResult(
        name=name or cv.source,
        mass_mg=mass_mg if mass_g else None,
        area_cm2=area_cm2,
        method=method,
        reference_cycle=ref,
        cycles=cycles,
        cycle_notes=cycle_notes,
        segments=segments_df,
        summary=summary,
        notes=notes,
        point_cycle=point_cycle,
        cv=cv,
        current_A=current,
        nova_check=_nova_charge_check(cv, current, flipped),
        params={
            "hysteresis_V": hysteresis, "scan_rate_V_s": scan_rate_V_s,
            "window": list(window) if window else None, "auto_sign": auto_sign,
            "reference_cycle": reference_cycle,
        },
    )


# --------------------------------------------------------------------------
# Traducción de tablas
# --------------------------------------------------------------------------
def localize_cycles(cycles: pd.DataFrame, cycle_notes: Dict[int, List[Note]], lang: str = "es") -> pd.DataFrame:
    df = cycles.copy()
    df["notes"] = [
        "; ".join(n.text(lang) for n in cycle_notes.get(int(c), [])) for c in df["cycle"]
    ]
    df["cycle"] = df["cycle"].astype(int)
    return df.rename(columns={c: t(f"col.{c}", lang) for c in df.columns})


def localize_segments(segments: pd.DataFrame, lang: str = "es") -> pd.DataFrame:
    df = segments.drop(columns=[c for c in ("start", "stop") if c in segments.columns])
    df["kind"] = df["kind"].map(lambda k: t(f"kind.{k}", lang))
    df["cycle"] = df["cycle"].map(lambda c: "—" if c is None or pd.isna(c) else int(c))
    df["partial"] = df["partial"].map(lambda p: t("yes" if p else "no", lang))
    return df.rename(columns={c: t(f"seg.{c}", lang) for c in df.columns})


def localize_summary(summary: Dict[str, object], lang: str = "es") -> Dict[str, object]:
    out: Dict[str, object] = {}
    ref = summary.get("ref_cycle", 2)
    for key in SUMMARY_KEYS:
        if key not in summary:
            continue
        value = summary[key]
        if key == "method":
            value = t(f"method.{value}", lang)
        out[t(f"sum.{key}", lang, ref=ref)] = value
    return out


def localize_nova_check(check, lang: str = "es") -> Optional[pd.DataFrame]:
    if not check:
        return None
    rows = []
    for key in ("pos", "neg"):
        nova, ours = check[key]
        diff = (ours - nova) / abs(nova) * 100 if nova else np.nan
        rows.append({t("nova.quantity", lang): t(f"nova.{key}", lang), t("nova.nova", lang): nova,
                     t("nova.ours", lang): ours, t("nova.diff", lang): diff})
    return pd.DataFrame(rows)


def cycle_label(n: int, lang: str = "es") -> str:
    return t("cycle_n", lang, n=n) if n else t("no_cycle", lang)


def active_mass_mg(disc_mg: float, collector_mg: float, active_fraction: float = 0.8) -> float:
    """Masa activa = (masa del disco − masa del colector) × fracción de material activo."""
    return (disc_mg - collector_mg) * active_fraction


def disc_area_cm2(diameter_mm: float) -> float:
    return float(np.pi * (diameter_mm / 20.0) ** 2)


__all__ = [
    "AnalysisResult", "analyze", "find_vertices", "localize_cycles", "localize_segments",
    "localize_summary", "localize_nova_check", "cycle_label", "active_mass_mg", "disc_area_cm2",
    "fmt_num",
]
