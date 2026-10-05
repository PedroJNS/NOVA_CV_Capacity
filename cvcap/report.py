"""Tablas resumen y exportación a Excel / CSV."""
from __future__ import annotations

import io
import re
from typing import Iterable, List

import pandas as pd

from .analysis import AnalysisResult


def summary_table(results: Iterable[AnalysisResult]) -> pd.DataFrame:
    """Una fila por archivo con los indicadores principales."""
    return pd.DataFrame([r.summary for r in results])


def cycles_long_table(results: Iterable[AnalysisResult]) -> pd.DataFrame:
    """Todos los ciclos de todos los archivos en una sola tabla."""
    frames = []
    for r in results:
        df = r.cycles.copy()
        df.insert(0, "Archivo", r.name)
        frames.append(df)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def _sheet_name(base: str, used: set) -> str:
    name = re.sub(r"[\[\]\:\*\?\/\\]", "_", base)[:31] or "Hoja"
    candidate, k = name, 1
    while candidate in used:
        suffix = f"_{k}"
        candidate = name[: 31 - len(suffix)] + suffix
        k += 1
    used.add(candidate)
    return candidate


def results_to_excel(results: List[AnalysisResult]) -> bytes:
    """Libro Excel con un resumen, todos los ciclos y el detalle por archivo."""
    buffer = io.BytesIO()
    used: set = set()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        summary_table(results).to_excel(writer, sheet_name=_sheet_name("Resumen", used), index=False)
        cycles_long_table(results).to_excel(writer, sheet_name=_sheet_name("Ciclos", used), index=False)
        for r in results:
            stem = re.sub(r"\.[A-Za-z0-9]+$", "", r.name)
            r.segments.to_excel(writer, sheet_name=_sheet_name(f"{stem[:20]}_segm", used), index=False)
            if r.notes:
                pd.DataFrame({"Notas": r.notes}).to_excel(
                    writer, sheet_name=_sheet_name(f"{stem[:20]}_notas", used), index=False
                )
    return buffer.getvalue()


def results_to_csv(results: List[AnalysisResult]) -> bytes:
    """CSV (separador ';', decimal ',') con todos los ciclos, listo para Excel en español."""
    table = cycles_long_table(results)
    return table.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig")
