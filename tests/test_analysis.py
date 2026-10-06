"""Tests del cálculo con CV sintéticas de carga conocida (pytest o unittest)."""
import unittest

import numpy as np

from cvcap.analysis import analyze, find_vertices, localize_cycles, localize_segments
from cvcap.i18n import CvcapError
from cvcap.io import CVData

RATE = 1e-3  # V/s
STEP = 1e-3  # V


def triangle(e_start=2.0, low=0.01, high=2.0, cycles=3, start_up=False):
    legs = []
    if start_up:
        legs.append(np.arange(e_start, high, STEP))
        legs.append(np.arange(high, low, -STEP))
    else:
        legs.append(np.arange(e_start, low, -STEP))
    for c in range(cycles):
        legs.append(np.arange(low, high, STEP))
        if c < cycles - 1:
            legs.append(np.arange(high, low, -STEP))
    legs.append(np.array([high]))
    e = np.concatenate(legs)
    t = np.arange(len(e)) * STEP / RATE
    return e, t


def constant_currents(e, i_cat=-1e-3, i_an=8e-4):
    direction = np.sign(np.gradient(e))
    return np.where(direction < 0, i_cat, i_an)


class TestVertices(unittest.TestCase):
    def test_three_cycles(self):
        e, _ = triangle()
        v = find_vertices(e)
        self.assertEqual(len(v) - 1, 6)
        self.assertAlmostEqual(e[v[1]], 0.01, places=2)
        self.assertAlmostEqual(e[v[2]], 2.0, places=2)

    def test_noise_does_not_create_vertices(self):
        e, _ = triangle()
        noisy = e + np.random.default_rng(1).normal(0, 0.002, size=len(e))
        self.assertEqual(len(find_vertices(noisy, 0.02)) - 1, 6)


class TestAnalysis(unittest.TestCase):
    def setUp(self):
        self.e, self.t = triangle()
        self.i = constant_currents(self.e)
        self.cv = CVData(potential_V=self.e, current_A=self.i, time_s=self.t)

    def test_capacity_and_ce(self):
        r = analyze(self.cv, mass_mg=2.0)
        self.assertEqual(len(r.cycles), 3)
        q_lit = 1e-3 * 1.99 / RATE
        cap_lit = q_lit / 3.6 / 0.002
        row = r.cycles.iloc[1]
        self.assertAlmostEqual(row["cap_lit"], cap_lit, delta=cap_lit * 0.002)
        self.assertAlmostEqual(row["ce"], 80.0, delta=0.2)
        self.assertAlmostEqual(r.cycles["ret"].iloc[2], 100.0, delta=0.2)
        self.assertEqual(r.summary["n_cycles"], 3)
        self.assertAlmostEqual(r.summary["ce1"], 80.0, delta=0.2)

    def test_point_cycle_labels(self):
        r = analyze(self.cv, mass_mg=2.0)
        self.assertEqual(set(np.unique(r.point_cycle)), {1, 2, 3})

    def test_both_methods_agree_without_mixed_signs(self):
        a = analyze(self.cv, mass_mg=2.0, method="signo")
        b = analyze(self.cv, mass_mg=2.0, method="direccion")
        np.testing.assert_allclose(a.cycles["cap_delit"], b.cycles["cap_delit"], rtol=1e-3)

    def test_sign_method_moves_lithiation_tail(self):
        i = self.i.copy()
        direction = np.sign(np.gradient(self.e))
        i[(direction > 0) & (self.e < 0.11)] = -1e-3
        cv = CVData(potential_V=self.e, current_A=i, time_s=self.t)
        sign = analyze(cv, mass_mg=2.0, method="signo").cycles.iloc[1]
        dirn = analyze(cv, mass_mg=2.0, method="direccion").cycles.iloc[1]
        q_tail = 1e-3 * 0.1 / RATE
        self.assertAlmostEqual(sign["cap_lit"] - dirn["cap_lit"], q_tail / 3.6 / 0.002, delta=1.5)
        self.assertGreater(sign["ce"], dirn["ce"])

    def test_without_time_uses_scan_rate(self):
        cv = CVData(potential_V=self.e, current_A=self.i)
        r = analyze(cv, mass_mg=2.0, scan_rate_V_s=RATE)
        ref = analyze(self.cv, mass_mg=2.0)
        np.testing.assert_allclose(r.cycles["cap_lit"], ref.cycles["cap_lit"], rtol=2e-3)

    def test_without_time_requires_rate(self):
        with self.assertRaises(CvcapError) as ctx:
            analyze(CVData(potential_V=self.e, current_A=self.i), mass_mg=2.0)
        self.assertEqual(ctx.exception.code, "err.no_time_rate")
        self.assertIn("scan rate", ctx.exception.localized("en"))

    def test_sign_flip(self):
        r = analyze(CVData(potential_V=self.e, current_A=-self.i, time_s=self.t), mass_mg=2.0)
        self.assertAlmostEqual(r.cycles["ce"].iloc[1], 80.0, delta=0.2)
        self.assertTrue(any(n.code == "note.flipped" for n in r.notes))

    def test_start_from_ocp_below_upper_vertex(self):
        e, t = triangle(e_start=0.8)
        r = analyze(CVData(potential_V=e, current_A=constant_currents(e), time_s=t), mass_mg=2.0)
        self.assertEqual(len(r.cycles), 3)
        self.assertEqual(r.cycle_notes[1][0].code, "cnote.partial_lit")
        self.assertIn("parcial", localize_cycles(r.cycles, r.cycle_notes, "es")["Notas"].iloc[0])
        self.assertIn("partial", localize_cycles(r.cycles, r.cycle_notes, "en")["Notes"].iloc[0])

    def test_start_above_upper_vertex_is_not_partial(self):
        e, t = triangle(e_start=2.87)
        r = analyze(CVData(potential_V=e, current_A=constant_currents(e), time_s=t), mass_mg=2.0)
        self.assertEqual(r.cycle_notes[1], [])

    def test_leading_anodic_sweep_excluded(self):
        e, t = triangle(e_start=1.5, start_up=True)
        r = analyze(CVData(potential_V=e, current_A=constant_currents(e), time_s=t), mass_mg=2.0)
        self.assertEqual(len(r.cycles), 3)
        self.assertTrue(any(n.code == "note.leading_anodic" for n in r.notes))
        self.assertEqual(int((r.point_cycle == 0).sum()) > 0, True)

    def test_window_limits_integration(self):
        r = analyze(self.cv, mass_mg=2.0, window=(0.01, 1.0))
        full = analyze(self.cv, mass_mg=2.0)
        ratio = r.cycles["cap_lit"].iloc[1] / full.cycles["cap_lit"].iloc[1]
        self.assertAlmostEqual(ratio, 0.99 / 1.99, delta=0.01)

    def test_no_mass_gives_absolute_values(self):
        r = analyze(self.cv, mass_mg=None)
        self.assertNotIn("cap_lit", r.cycles.columns)
        self.assertIn("mah_delit", r.cycles.columns)

    def test_localized_tables(self):
        r = analyze(self.cv, mass_mg=2.0)
        self.assertIn("Eficiencia coulómbica (%)", r.cycles_table("es").columns)
        self.assertIn("Coulombic efficiency (%)", r.cycles_table("en").columns)
        seg_en = localize_segments(r.segments, "en")
        self.assertIn("Cathodic (lithiation)", set(seg_en["Type"]))
        self.assertNotIn("start", seg_en.columns)
        self.assertIn("Retention last cycle vs cycle 2 (%)", r.summary_row("en"))


if __name__ == "__main__":
    unittest.main()
