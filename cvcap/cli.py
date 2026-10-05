"""Uso desde la línea de comandos.

Ejemplos::

    python -m cvcap datos_cv.txt --masa-activa 1.6
    python -m cvcap muestra1.txt muestra2.xlsx --masa-disco 6.2 --masa-cu 4.1 --salida resultados.xlsx
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional

import pandas as pd

from . import __version__
from .analysis import active_mass_mg, analyze, disc_area_cm2
from .io import NovaFormatError, read_nova
from .report import results_to_csv, results_to_excel, summary_table


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="cvcap",
        description="Capacidad, eficiencia coulómbica y retención a partir de CV exportadas de NOVA.",
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
    p.add_argument("--salida", type=Path, help="guardar resultados en .xlsx o .csv")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return p


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if args.masa_activa is not None:
        mass = args.masa_activa
    elif args.masa_disco is not None and args.masa_cu is not None:
        mass = active_mass_mg(args.masa_disco, args.masa_cu, args.fraccion)
    else:
        mass = None
    area = disc_area_cm2(args.diametro) if args.diametro else None

    pd.set_option("display.width", 200)
    pd.set_option("display.max_columns", 30)
    results = []
    for path in args.archivos:
        try:
            cv = read_nova(path)
            res = analyze(
                cv,
                mass_mg=mass,
                area_cm2=area,
                reference_cycle=args.ciclo_ref,
                hysteresis=args.histeresis / 1000.0,
                scan_rate_V_s=args.velocidad / 1000.0 if args.velocidad else None,
                window=tuple(args.ventana) if args.ventana else None,
                method=args.metodo,
                name=Path(path).name,
            )
        except (NovaFormatError, ValueError, OSError) as exc:
            print(f"[ERROR] {path}: {exc}", file=sys.stderr)
            continue
        results.append(res)
        print(f"\n=== {res.name} ===")
        for note in res.notes:
            print(f"  · {note}")
        print(res.cycles.round(4).to_string(index=False))
        if res.nova_check is not None:
            print("\nComprobación con Q+/Q− de NOVA:")
            print(res.nova_check.round(5).to_string(index=False))

    if not results:
        return 1
    if len(results) > 1:
        print("\n=== Resumen ===")
        print(summary_table(results).round(3).to_string(index=False))
    if args.salida:
        data = results_to_csv(results) if args.salida.suffix.lower() == ".csv" else results_to_excel(results)
        args.salida.write_bytes(data)
        print(f"\nResultados guardados en {args.salida}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
