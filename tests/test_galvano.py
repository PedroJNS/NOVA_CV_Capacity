"""Tests de la lectura y análisis de medidas galvanostáticas, y del historial."""
import tempfile
import unittest
from pathlib import Path

import numpy as np

from cvcap import galvano as gv
from cvcap.history import History

MASS = 2.08  # mg
I_SET = 77.4e-6  # A (C/10 para 2,08 mg de grafito)


def _nova_chrono_text(segments, step_s=1.0, decimal=","):
    """Genera un archivo de exportación NOVA (ASCII, ';', decimal con coma) a partir de tramos (I_A, duración_s, E_inicio, E_fin)."""
    lines = ["Time (s);WE(1).Potential (V);Corrected time (s);Index;WE(1).Current (A);Current range;Cutoffs"]
    t = 0.0
    idx = 1
    e = 0.1
    for current, dur, e0, e1 in segments:
        n = int(dur / step_s)
        for k in range(n):
            frac = k / max(n - 1, 1)
            v = e0 + (e1 - e0) * frac
            lines.append(";".join([
                f"{1000 + t:.6f}".replace(".", decimal), f"{v:.6f}".replace(".", decimal),
                f"{t:.6f}".replace(".", decimal), str(idx), f"{current:.6e}".replace(".", decimal), "100 µA", ""]))
            t += step_s
            idx += 1
    return "\n".join(lines) + "\n"


class GalvanoTests(unittest.TestCase):
    def setUp(self):
        self.segments = [
            (-I_SET, 1675, 0.093, 0.010),  # litiación inicial
            (+I_SET, 4986, 0.097, 2.003),  # delitiación
            (-I_SET, 5791, 1.552, 0.010),  # litiación tras 2 V
        ]
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "chrono.txt"
        self.path.write_text(_nova_chrono_text(self.segments), encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_load_reads_nova_export(self):
        data = gv.load_galvano(self.path)
        self.assertGreater(len(data), 1000)
        self.assertAlmostEqual(float(np.median(np.abs(data.current_A))), I_SET, places=7)
        self.assertTrue(np.all(np.diff(data.time_s) >= 0))

    def test_steps_capacities_match_expected_charges(self):
        data = gv.load_galvano(self.path)
        steps = gv.split_steps(data, MASS)
        types = list(steps["type"])
        self.assertEqual(types, ["lit", "delit", "lit"])
        # Q = I * t; capacidad = Q / 3,6 / masa(g)
        expected = [I_SET * d / 3.6 / (MASS / 1000) for d in (1675, 4986, 5791)]
        for got, exp in zip(steps["cap_mAh_g"], expected):
            self.assertAlmostEqual(got, exp, delta=0.5)  # 0,5 mAh/g de tolerancia por el muestreo

    def test_cycles_efficiency_and_retention(self):
        data = gv.load_galvano(self.path)
        result = gv.analyze_galvano(data, mass_mg=MASS, name="B4_6")
        self.assertEqual(len(result.cycles), 1)  # una delitiación = un ciclo, con la litiación previa
        row = result.cycles.iloc[0]
        self.assertAlmostEqual(row["ce"], row["cap_delit"] / row["cap_lit"] * 100, places=6)
        self.assertAlmostEqual(row["ret"], 100.0, places=6)  # único ciclo: retención = 100 %

    def test_summary_is_serialisable(self):
        result = gv.analyze_galvano(gv.load_galvano(self.path), mass_mg=MASS, name="B4_6")
        summary = result.summary()
        self.assertEqual(summary["n_steps"], 3)
        self.assertIsInstance(summary["first_delit_mAh_g"], float)

    def test_zero_mass_is_rejected(self):
        from cvcap.i18n import CvcapError
        with self.assertRaises(CvcapError):
            gv.split_steps(gv.load_galvano(self.path), 0)

    def test_nova_charge_column_is_used_when_present(self):
        text = _nova_chrono_text(self.segments[:1]).replace(
            "Current range;Cutoffs", "Current range;Cutoffs;WE(1).Charge (C)")
        lines = text.splitlines()
        out = [lines[0]]
        for k, ln in enumerate(lines[1:]):
            q = -(k + 1) * I_SET * 1.0
            out.append(ln + f";{f'{q:.6e}'.replace('.', ',')}")
        path = Path(self.tmp.name) / "con_carga.txt"
        path.write_text("\n".join(out) + "\n", encoding="utf-8")
        data = gv.load_galvano(path)
        self.assertIsNotNone(data.charge_C)
        steps = gv.split_steps(data, MASS)
        self.assertAlmostEqual(steps["Q_C"].iloc[0], abs(data.charge_C[-1] - data.charge_C[0]), places=9)


class HistoryTests(unittest.TestCase):
    def test_log_list_cycles_delete_roundtrip(self):
        import pandas as pd
        with tempfile.TemporaryDirectory() as d:
            hist = History(Path(d) / "h.sqlite")
            cycles = pd.DataFrame({"cycle": [1], "cap_lit": [60.0], "cap_delit": [52.0], "ce": [86.7], "ret": [100.0]})
            rid = hist.log("B4_6.txt", "GCD", 2.08, {"first_delit_mAh_g": 51.6, "n_cycles": 1}, cycles)
            table = hist.list()
            self.assertEqual(len(table), 1)
            self.assertEqual(table.iloc[0]["name"], "B4_6.txt")
            self.assertAlmostEqual(table.iloc[0]["first_delit_mAh_g"], 51.6)
            back = hist.cycles(rid)
            self.assertAlmostEqual(back.iloc[0]["cap_delit"], 52.0)
            hist.delete(rid)
            self.assertTrue(hist.list().empty)


if __name__ == "__main__":
    unittest.main()
