"""Genera una CV sintética de grafito con el formato de exportación ASCII de NOVA.

Uso:  python examples/generar_ejemplo.py
Crea  examples/ejemplo_nova_cv.txt  (separador ';' y decimal ',', como NOVA en español).
Los datos son simulados y solo sirven para probar la aplicación.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np


def simulated_cv(
    e_start: float = 2.0,
    e_low: float = 0.01,
    e_high: float = 2.0,
    cycles: int = 3,
    rate: float = 1e-4,  # V/s
    step: float = 0.00244,  # V
    seed: int = 0,
):
    rng = np.random.default_rng(seed)
    legs = [np.arange(e_start, e_low, -step)]
    for c in range(cycles):
        legs.append(np.arange(e_low, e_high, step))
        if c < cycles - 1:
            legs.append(np.arange(e_high, e_low, -step))
    potential = np.concatenate(legs)
    time = np.arange(len(potential)) * step / rate
    direction = np.sign(np.gradient(potential))
    # ciclo de cada punto (empieza en 1 en cada barrido catódico)
    cycle = np.cumsum(np.r_[0, (np.diff(direction) < 0).astype(int)]) + 1

    current = np.zeros_like(potential)
    cathodic = direction < 0
    # doble capa
    current += 4e-6 * direction
    # SEI (solo primer barrido catódico)
    first = cathodic & (cycle == 1)
    current[first] -= 2.85e-4 * np.exp(-((potential[first] - 0.65) / 0.07) ** 2)
    # litiación: crece hacia 0 V
    current[cathodic] -= 2.82e-3 * np.exp(-(potential[cathodic] - e_low) / 0.07)
    # delitiación: pico anódico asimétrico en ~0,3 V
    an = ~cathodic
    x = potential[an]
    current[an] += 2.48e-3 * np.exp(-((x - 0.29) / 0.07) ** 2) * (x < 0.29) + \
        2.48e-3 * np.exp(-((x - 0.29) / 0.035) ** 2) * (x >= 0.29)
    # la litiación continúa al principio del barrido anódico
    current[an] -= 1.1e-3 * np.exp(-(x - e_low) / 0.03)
    current += rng.normal(0, 3e-7, size=len(current))
    measured = potential + rng.normal(0, 3e-4, size=len(potential))
    return potential, time, current, measured, cycle


def write_nova_ascii(path: Path) -> None:
    potential, time, current, measured, cycle = simulated_cv()

    def fmt(value: float) -> str:
        return repr(float(value)).replace(".", ",")

    lines = ["Potential applied (V);Time (s);WE(1).Current (A);Scan;Index;WE(1).Potential (V)"]
    for k, (e, t, i, em, c) in enumerate(zip(potential, time, current, measured, cycle), start=1):
        lines.append(";".join([fmt(e), fmt(t), fmt(i), str(int(c)), str(k), fmt(em)]))
    path.write_text("\r\n".join(lines) + "\r\n", encoding="utf-8")


if __name__ == "__main__":
    out = Path(__file__).with_name("ejemplo_nova_cv.txt")
    write_nova_ascii(out)
    print(f"Escrito {out}")
