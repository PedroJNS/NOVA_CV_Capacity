"""Cálculo de capacidad, eficiencia coulómbica y retención a partir de una CV.

Método
------
1. Los datos se ordenan en el tiempo (lo hace :func:`cvcap.io.to_cvdata`).
2. Se localizan los vértices del barrido con un algoritmo de "zigzag" con
   histéresis (por defecto 20 mV), robusto frente al ruido del potencial medido.
3. Cada tramo entre vértices es un semiciclo:
   * catódico (potencial bajando)  -> litiación del grafito (+ formación de SEI)
   * anódico  (potencial subiendo) -> delitiación
4. La carga se integra en el tiempo (regla del trapecio): Q = ∫ I dt.
   Si el archivo no trae tiempo se usa Q = ∫ I dE / v.
5. Un ciclo = un semiciclo catódico seguido de uno anódico. Un barrido anódico
   inicial (antes del primer catódico) no forma ciclo.
6. Reparto de la carga del ciclo (parámetro ``method``):
   * ``"signo"`` (por defecto, recomendado para materiales de intercalación):
     litiación = toda la corriente negativa del ciclo y delitiación = toda la
     positiva. Tiene en cuenta que el grafito sigue litiándose al principio del
     barrido anódico (corriente aún negativa entre 0,01 y ~0,13 V). Equivale a
     las columnas Q+ / Q− que calcula NOVA.
   * ``"direccion"``: carga neta de cada barrido (catódico = litiación,
     anódico = delitiación).
7. Capacidad específica (mAh/g) = |Q| (C) / 3,6 / masa activa (g).
   Eficiencia coulómbica (%)    = Q_delitiación / |Q_litiación| · 100.
   Retención (%)                = C_delit,n / C_delit,ref · 100.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from .io import CVData

CATHODIC = "Catódico (litiación)"
ANODIC = "Anódico (delitiación)"

# Nombres de columnas de las tablas de resultados
COL_CYCLE = "Ciclo"
COL_Q_LIT = "Q litiación (C)"
COL_Q_DELIT = "Q delitiación (C)"
COL_CAP_LIT = "Capacidad litiación (mAh/g)"
COL_CAP_DELIT = "Capacidad delitiación (mAh/g)"
COL_MAH_LIT = "Capacidad litiación (mAh)"
COL_MAH_DELIT = "Capacidad delitiación (mAh)"
COL_AREAL_DELIT = "Capacidad delitiación (mAh/cm²)"
COL_CE = "Eficiencia coulómbica (%)"
COL_IRR = "Capacidad irreversible (mAh/g)"
COL_RET = "Retención (%)"
COL_NOTES = "Notas"


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
    """Índices de inicio, vértices y final del barrido.

    Un vértice se confirma cuando el potencial se aleja del extremo actual más
    de ``hysteresis`` voltios en sentido contrario.
    """
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
    charge_C: float  # carga neta del barrido
    q_pos_C: float  # carga de la corriente positiva
    q_neg_C: float  # carga de la corriente negativa (valor negativo)
    duration_s: Optional[float]
    scan_rate_mV_s: Optional[float]
    partial: bool = False
    cycle: Optional[int] = None

    def flip_sign(self) -> None:
        self.charge_C = -self.charge_C
        self.q_pos_C, self.q_neg_C = -self.q_neg_C, -self.q_pos_C


def _segment_charges(
    cv: CVData,
    a: int,
    b: int,
    sign: int,
    current: np.ndarray,
    scan_rate_V_s: Optional[float],
    window: Optional[Tuple[float, float]],
) -> Tuple[float, float, float]:
    """Carga neta, positiva y negativa del tramo [a, b]."""
    e = cv.potential_V[a:b + 1]
    i = current[a:b + 1]
    if window is not None:
        lo, hi = min(window), max(window)
        i = np.where((e >= lo) & (e <= hi), i, 0.0)
    pos, neg = np.clip(i, 0, None), np.clip(i, None, 0)
    if cv.time_s is not None:
        t = cv.time_s[a:b + 1]
        return _trapz(i, t), _trapz(pos, t), _trapz(neg, t)
    if not scan_rate_V_s:
        raise ValueError("El archivo no tiene columna de tiempo: indique la velocidad de barrido.")
    # dt = dE / (dE/dt) con dE/dt = ±v
    k = sign * scan_rate_V_s
    return _trapz(i, e) / k, _trapz(pos, e) / k, _trapz(neg, e) / k


def split_segments(
    cv: CVData,
    current: np.ndarray,
    hysteresis: float = 0.02,
    scan_rate_V_s: Optional[float] = None,
    window: Optional[Tuple[float, float]] = None,
    partial_threshold: float = 0.9,
) -> List[Segment]:
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
        segments.append(
            Segment(
                number=len(segments) + 1,
                kind=ANODIC if sign > 0 else CATHODIC,
                start=a,
                stop=b,
                e_start=e0,
                e_end=e1,
                charge_C=net,
                q_pos_C=q_pos,
                q_neg_C=q_neg,
                duration_s=duration,
                scan_rate_mV_s=rate,
            )
        )
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
    cycles: pd.DataFrame
    segments: pd.DataFrame
    summary: Dict[str, object]
    notes: List[str]
    point_cycle: np.ndarray  # etiqueta de ciclo de cada punto (para gráficas)
    cv: CVData
    current_A: np.ndarray  # corriente usada (con el signo corregido si hizo falta)
    nova_check: Optional[pd.DataFrame] = None


def _nova_charge_check(cv: CVData, current: np.ndarray, flipped: bool) -> Optional[pd.DataFrame]:
    """Compara la carga total integrada con las columnas Q+/Q− de NOVA (por scan)."""
    if cv.q_plus_C is None or cv.q_minus_C is None or cv.scan is None or cv.time_s is None:
        return None
    frame = pd.DataFrame({"scan": cv.scan, "qp": cv.q_plus_C, "qm": cv.q_minus_C})
    per_scan = frame.groupby("scan").agg(qp=("qp", "last"), qm=("qm", "last"))
    nova_pos, nova_neg = float(per_scan["qp"].sum()), float(per_scan["qm"].sum())
    if flipped:
        nova_pos, nova_neg = -nova_neg, -nova_pos
    t = cv.time_s
    ours_pos = _trapz(np.clip(current, 0, None), t)
    ours_neg = _trapz(np.clip(current, None, 0), t)

    def diff(a, b):
        return (a - b) / abs(b) * 100 if b else np.nan

    return pd.DataFrame(
        {
            "Magnitud": ["Carga positiva total (C)", "Carga negativa total (C)"],
            "NOVA (Q+ / Q−)": [nova_pos, nova_neg],
            "Este programa": [ours_pos, ours_neg],
            "Diferencia (%)": [diff(ours_pos, nova_pos), diff(ours_neg, nova_neg)],
        }
    )


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

    Parameters
    ----------
    cv : datos leídos con :func:`cvcap.io.read_nova` / :func:`cvcap.io.to_cvdata`.
    mass_mg : masa activa del electrodo en mg (``None`` = solo cargas y mAh).
    area_cm2 : área del electrodo para dar capacidad areal (opcional).
    reference_cycle : ciclo de referencia para la retención (por defecto 2).
    hysteresis : umbral en V para confirmar un vértice del barrido.
    scan_rate_V_s : velocidad de barrido; solo se usa si no hay columna de tiempo.
    window : (E_min, E_max) para integrar solo dentro de esa ventana de potencial.
    auto_sign : invierte el signo de la corriente si la litiación sale positiva.
    method : ``"signo"`` (por defecto) o ``"direccion"``; ver la cabecera del módulo.
    """
    if method not in ("signo", "direccion"):
        raise ValueError("method debe ser 'signo' o 'direccion'.")
    notes = list(cv.notes)
    current = np.asarray(cv.current_A, dtype=float).copy()
    segments = split_segments(cv, current, hysteresis, scan_rate_V_s, window)
    if not segments:
        raise ValueError("No se ha podido identificar ningún barrido en los datos.")

    flipped = False
    if auto_sign:
        q_cat = sum(s.charge_C for s in segments if s.kind == CATHODIC)
        q_an = sum(s.charge_C for s in segments if s.kind == ANODIC)
        if q_cat > 0 and q_an < 0:
            current = -current
            for s in segments:
                s.flip_sign()
            flipped = True
            notes.append(
                "La corriente tenía el convenio de signo contrario (litiación positiva): se ha invertido."
            )

    # Emparejado: catódico seguido de anódico = un ciclo
    cycles: List[Tuple[Segment, Optional[Segment]]] = []
    k = 0
    while k < len(segments):
        seg = segments[k]
        if seg.kind == ANODIC:
            if not cycles:
                notes.append(
                    f"El primer barrido es anódico ({seg.e_start:.2f} → {seg.e_end:.2f} V): "
                    "no se incluye en ningún ciclo."
                )
            k += 1
            continue
        partner = segments[k + 1] if k + 1 < len(segments) and segments[k + 1].kind == ANODIC else None
        cycles.append((seg, partner))
        k += 2 if partner else 1

    mass_g = mass_mg / 1000.0 if mass_mg and mass_mg > 0 else None
    if mass_g is None:
        notes.append("Sin masa activa: solo se calculan cargas (C) y capacidades absolutas (mAh).")

    rows = []
    for n, (cat, an) in enumerate(cycles, start=1):
        cat.cycle = n
        if an is not None:
            an.cycle = n
        if method == "signo":
            q_lit = -(cat.q_neg_C + (an.q_neg_C if an is not None else 0.0))
            q_delit = cat.q_pos_C + an.q_pos_C if an is not None else np.nan
        else:
            q_lit = -cat.charge_C  # positiva
            q_delit = an.charge_C if an is not None else np.nan
        row_notes = []
        if cat.partial:
            row_notes.append(f"litiación parcial ({cat.e_start:.2f} → {cat.e_end:.2f} V)")
        if an is None:
            row_notes.append("sin barrido anódico")
        elif an.partial:
            row_notes.append(f"delitiación parcial ({an.e_start:.2f} → {an.e_end:.2f} V)")
        row = {
            COL_CYCLE: n,
            COL_Q_LIT: q_lit,
            COL_Q_DELIT: q_delit,
            COL_MAH_LIT: q_lit / 3.6,
            COL_MAH_DELIT: q_delit / 3.6,
            COL_CE: q_delit / q_lit * 100 if q_lit else np.nan,
        }
        if mass_g:
            row[COL_CAP_LIT] = q_lit / 3.6 / mass_g
            row[COL_CAP_DELIT] = q_delit / 3.6 / mass_g
            row[COL_IRR] = row[COL_CAP_LIT] - row[COL_CAP_DELIT]
        if area_cm2:
            row[COL_AREAL_DELIT] = q_delit / 3.6 / area_cm2
        row[COL_NOTES] = "; ".join(row_notes)
        rows.append(row)

    cycles_df = pd.DataFrame(rows)
    if cycles_df.empty:
        raise ValueError("No se encontró ningún barrido catódico (litiación) en los datos.")

    base_col = COL_CAP_DELIT if mass_g else COL_MAH_DELIT
    ref = reference_cycle if reference_cycle <= len(cycles_df) else 1
    if ref != reference_cycle:
        notes.append(f"Solo hay {len(cycles_df)} ciclo(s): la retención se refiere al ciclo {ref}.")
    ref_value = cycles_df.loc[cycles_df[COL_CYCLE] == ref, base_col].iloc[0]
    cycles_df[COL_RET] = cycles_df[base_col] / ref_value * 100 if ref_value else np.nan

    ordered = [COL_CYCLE, COL_Q_LIT, COL_Q_DELIT, COL_CAP_LIT, COL_CAP_DELIT, COL_MAH_LIT,
               COL_MAH_DELIT, COL_AREAL_DELIT, COL_CE, COL_IRR, COL_RET, COL_NOTES]
    cycles_df = cycles_df[[c for c in ordered if c in cycles_df.columns]]

    segments_df = pd.DataFrame(
        [
            {
                "Segmento": s.number,
                "Tipo": s.kind,
                "Ciclo": s.cycle if s.cycle is not None else "—",
                "E inicio (V)": s.e_start,
                "E final (V)": s.e_end,
                "Puntos": s.stop - s.start + 1,
                "Duración (s)": s.duration_s,
                "Velocidad (mV/s)": s.scan_rate_mV_s,
                "Carga neta (C)": s.charge_C,
                "Q+ (C)": s.q_pos_C,
                "Q− (C)": s.q_neg_C,
                "Parcial": "sí" if s.partial else "no",
            }
            for s in segments
        ]
    )

    labels = np.full(len(cv), "Sin ciclo", dtype=object)
    for s in segments:
        if s.cycle is not None:
            labels[s.start:s.stop + 1] = f"Ciclo {s.cycle}"

    rates = [s.scan_rate_mV_s for s in segments if s.scan_rate_mV_s]
    complete = cycles_df[cycles_df[COL_Q_DELIT].notna()]
    summary: Dict[str, object] = {
        "Archivo": name or cv.source,
        "Método": "por signo de corriente" if method == "signo" else "por dirección de barrido",
        "Masa activa (mg)": mass_mg,
        "Nº ciclos": int(len(cycles_df)),
        "Velocidad de barrido (mV/s)": float(np.median(rates)) if rates else None,
        "EC ciclo 1 (%)": float(cycles_df[COL_CE].iloc[0]),
    }
    later = complete[complete[COL_CYCLE] >= 2]
    summary["EC media ciclos ≥2 (%)"] = float(later[COL_CE].mean()) if not later.empty else None
    if mass_g:
        summary["Cap. litiación ciclo 1 (mAh/g)"] = float(cycles_df[COL_CAP_LIT].iloc[0])
        summary["Cap. delitiación ciclo 1 (mAh/g)"] = float(cycles_df[COL_CAP_DELIT].iloc[0])
        summary["Cap. irreversible ciclo 1 (mAh/g)"] = float(cycles_df[COL_IRR].iloc[0])
        if not complete.empty:
            summary["Cap. delitiación último ciclo (mAh/g)"] = float(complete[COL_CAP_DELIT].iloc[-1])
    if not complete.empty:
        summary[f"Retención último ciclo vs ciclo {ref} (%)"] = float(complete[COL_RET].iloc[-1])

    if window is not None:
        notes.append(f"Integración limitada a {min(window):.3f}–{max(window):.3f} V.")

    return AnalysisResult(
        name=name or cv.source,
        mass_mg=mass_mg,
        area_cm2=area_cm2,
        cycles=cycles_df,
        segments=segments_df,
        summary=summary,
        notes=notes,
        point_cycle=labels,
        cv=cv,
        current_A=current,
        nova_check=_nova_charge_check(cv, current, flipped),
    )


def active_mass_mg(disc_mg: float, collector_mg: float, active_fraction: float = 0.8) -> float:
    """Masa activa = (masa del disco − masa del colector) × fracción de material activo."""
    return (disc_mg - collector_mg) * active_fraction


def disc_area_cm2(diameter_mm: float) -> float:
    return float(np.pi * (diameter_mm / 20.0) ** 2)
