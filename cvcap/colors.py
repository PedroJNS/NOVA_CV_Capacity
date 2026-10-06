"""Paletas de color.

* Rampas de un solo tono (claro → oscuro) para diferenciar ciclos de una misma CV.
  Son escalas ordinales: el tono más claro tiene contraste ≥ 2:1 sobre fondo
  blanco y la luminosidad decrece de forma monótona (validadas con el script de
  la guía de visualización).
* Paleta categórica de orden fijo para comparar muestras distintas.
"""
from __future__ import annotations

from typing import Dict, List, Sequence

RAMPS: Dict[str, Sequence[str]] = {
    "blues": ("#86b6ef", "#5598e7", "#2a78d6", "#1c5cab", "#0d366b"),
    "reds": ("#f0877f", "#e34948", "#c0272d", "#8f1d21", "#5c0f12"),
    "greens": ("#6fbf73", "#3fa34d", "#1f7a33", "#145a24", "#0b3a16"),
    "purples": ("#a99be0", "#7d6bd0", "#5a46b8", "#3f2f8f", "#271b62"),
    "oranges": ("#f29a52", "#eb6834", "#c4501f", "#943a14", "#62250b"),
    "greys": ("#a3a3a3", "#7a7a7a", "#555555", "#333333", "#111111"),
}

#: Paleta categórica (orden fijo; nunca se recicla: más de 8 muestras -> repetir con marcador distinto)
CATEGORICAL: List[str] = [
    "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948",
]

NO_CYCLE_COLOR = "#9e9e9e"


def _hex_to_rgb(color: str):
    color = color.lstrip("#")
    return tuple(int(color[i:i + 2], 16) for i in (0, 2, 4))


def _rgb_to_hex(rgb) -> str:
    return "#" + "".join(f"{max(0, min(255, round(c))):02x}" for c in rgb)


def _sample(stops: Sequence[str], position: float) -> str:
    """Color en la posición [0, 1] de la rampa (interpolación lineal entre paradas)."""
    position = min(max(position, 0.0), 1.0)
    scaled = position * (len(stops) - 1)
    k = min(int(scaled), len(stops) - 2)
    frac = scaled - k
    a, b = _hex_to_rgb(stops[k]), _hex_to_rgb(stops[k + 1])
    return _rgb_to_hex([a[j] + (b[j] - a[j]) * frac for j in range(3)])


def cycle_shades(ramp: str, n: int, darkest_first: bool = False) -> List[str]:
    """``n`` tonos de la rampa, del más claro (ciclo 1) al más oscuro (último ciclo).

    Con ``darkest_first=True`` el orden se invierte (útil para resaltar el ciclo 1).
    """
    stops = RAMPS.get(ramp, RAMPS["blues"])
    if n <= 0:
        return []
    if n == 1:
        return [stops[len(stops) // 2 + 1]]
    shades = [_sample(stops, k / (n - 1)) for k in range(n)]
    return shades[::-1] if darkest_first else shades


def categorical(index: int) -> str:
    return CATEGORICAL[index % len(CATEGORICAL)]
