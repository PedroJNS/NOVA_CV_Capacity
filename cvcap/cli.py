"""Uso desde la línea de comandos.

Ejemplos::

    python -m cvcap datos_cv.txt --masa-activa 1.6
    python -m cvcap muestra1.txt muestra2.xlsx --masa-disco 6.2 --masa-cu 4.1 --salida resultados.xlsx
    python -m cvcap datos_cv.txt --masa-activa 2.64 --origin cv_origin.xlsx --idioma en
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional

import pandas as pd

from . import __version__
from .analysis import active_mass_mg, analyze, disc_area_cm2
from .i18n import CvcapError
from .peaks import default_windows, window_peaks
from .io import read_nova
from .report import item_from_result, origin_workbook, results_to_csv, results_to_excel, summary_table


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="cvcap",
        description="Capacidad, eficiencia coulómbica, retención y picos a partir de CV exportadas de NOVA.",
    )
    p.add_argument("archivos", nargs="+", help="archivos .txt/.csv/.dat/.xlsx/.xls exportados de NOVA")
    masa = p.add_argument_group("masa del electrodo")
    masa.add_argument("--masa-activa", type=float, help="masa activa en mg")
    masa.add_argument("--masa-disco", type=float, help="masa del disco (electrodo + Cu) en mg")
    masa.add_argument("--masa-cu", type=float, help="masa de un disco de Cu limpio en mg")
    masa.add_argument("--fraccion", type=float, default=0.8, help="fracción de material activo (def. 0,8)")
    p.add_argument("--diametro", type=float, help="diámetro del disco en mm (para mAh/cm²)")
    p.add_argument("--ciclo-ref", type=int, default=2, help="ciclo de referencia para la retención (def. 2)")
    p.add_argument("--metodo", choices=["signo", "direccion"], default="signo",
                   help="reparto de la carga: por signo de corriente (def.) o por dirección de barrido")
    p.add_argument("--histeresis", type=float, default=20.0, help="umbral de vértice en mV (def. 20)")
    p.add_argument("--velocidad", type=float, help="velocidad de barrido en mV/s (solo si no hay tiempo)")
    p.add_argument("--ventana", type=float, nargs=2, metavar=("EMIN", "EMAX"),
                   help="integrar solo entre EMIN y EMAX (V)")
    p.add_argument("--idioma", "--lang", choices=["es", "en"], default="es", help="idioma de las tablas (es/en)")
    p.add_argument("--salida", type=Path, help="guardar resultados en .xlsx o .csv")
    p.add_argument("--origin", type=Path, help="guardar un Excel listo para OriginLab (.xlsx)")
    p.add_argument("--unidad-corriente", choices=["mA", "uA", "A", "A/g"], default="mA",
                   help="unidad de corriente en el Excel para Origin (def. mA)")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return p


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    lang = args.idioma
    if args.masa_activa is not None:
        mass = args.masa_activa
    elif args.masa_disco is not None and args.masa_cu is not None:
        mass = active_mass_mg(args.masa_disco, args.masa_cu, args.fraccion)
    else:
        mass = None
    area = disc_area_cm2(args.diametro) if args.diametro else None

    pd.set_option("display.width", 220)
    pd.set_option("display.max_columns", 30)
    results, items = [], []
    windows = default_windows(lang)
    for path in args.archivos:
        try:
            cv = read_nova(path)
            res = analyze(
                cv, mass_mg=mass, area_cm2=area, reference_cycle=args.ciclo_ref,
                hysteresis=args.histeresis / 1000.0,
                scan_rate_V_s=args.velocidad / 1000.0 if args.velocidad else None,
                window=tuple(args.ventana) if args.ventana else None, method=args.metodo, name=Path(path).name,
            )
        except CvcapError as exc:
            print(f"[ERROR] {path}: {exc.localized(lang)}", file=sys.stderr)
            continue
        except OSError as exc:
            print(f"[ERROR] {path}: {exc}", file=sys.stderr)
            continue
        peaks = window_peaks(res, windows)
        results.append(res)
        items.append(item_from_result(res, peaks=peaks))
        print(f"\n=== {res.name} ===")
        for note in res.notes_text(lang):
            print(f"  · {note}")
        print(res.cycles_table(lang).round(4).to_string(index=False))
        if not peaks.empty:
            print()
            print(peaks.assign(i_peak_mA=peaks["i_peak"] * 1e3).drop(columns="i_peak").round(4).to_string(index=False))
        nova = res.nova_table(lang)
        if nova is not None:
            print()
            print(nova.round(5).to_string(index=False))

    if not results:
        return 1
    if len(results) > 1:
        print()
        print(summary_table(results, lang).round(3).to_string(index=False))
    if args.salida:
        data = results_to_csv(results, lang) if args.salida.suffix.lower() == ".csv" else results_to_excel(results, lang)
        args.salida.write_bytes(data)
        print(f"\n-> {args.salida}")
    if args.origin:
        args.origin.write_bytes(origin_workbook(items, lang, args.unidad_corriente))
        print(f"-> {args.origin}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
