"""cvcap: capacidad de electrodos a partir de voltametrías cíclicas exportadas de NOVA."""

__version__ = "1.0.0"

from .analysis import AnalysisResult, active_mass_mg, analyze, disc_area_cm2  # noqa: E402
from .io import CVData, NovaFormatError, load_table, read_nova, to_cvdata  # noqa: E402

__all__ = [
    "AnalysisResult",
    "CVData",
    "NovaFormatError",
    "active_mass_mg",
    "analyze",
    "disc_area_cm2",
    "load_table",
    "read_nova",
    "to_cvdata",
]
