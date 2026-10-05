"""Tests del cálculo con CV sintéticas de carga conocida (ejecutar con pytest o unittest)."""
import unittest

import numpy as np

from cvcap.analysis import COL_CAP_DELIT, COL_CAP_LIT, COL_CE, COL_RET, analyze, find_vertices
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
        self.assertEqual(len(v) - 1, 6)  # 6 semiciclos
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

    def expected(self, current, span=1.99):
        duration = span / RATE
        return abs(current) * duration  # C

    def test_capacity_and_ce(self):
        r = analyze(self.cv, mass_mg=2.0)
        self.assertEqual(len(r.cycles), 3)
        q_lit, q_delit = self.expected(1e-3), self.expected(8e-4)
        cap_lit = q_lit / 3.6 / 0.002
        row = r.cycles.iloc[1]
        self.assertAlmostEqual(row[COL_CAP_LIT], cap_lit, delta=cap_lit * 0.002)
        self.assertAlmostEqual(row[COL_CE], 80.0, delta=0.2)
        self.assertAlmostEqual(r.cycles[COL_RET].iloc[2], 100.0, delta=0.2)

    def test_both_methods_agree_without_mixed_signs(self):
        a = analyze(self.cv, mass_mg=2.0, method="signo")
        b = analyze(self.cv, mass_mg=2.0, method="direccion")
        np.testing.assert_allclose(a.cycles[COL_CAP_DELIT], b.cycles[COL_CAP_DELIT], rtol=1e-3)

    def test_sign_method_moves_lithiation_tail(self):
        # corriente negativa al principio del barrido anódico (litiación que continúa)
        i = self.i.copy()
        direction = np.sign(np.gradient(self.e))
        tail = (direction > 0) & (self.e < 0.11)
        i[tail] = -1e-3
        cv = CVData(potential_V=self.e, current_A=i, time_s=self.t)
        sign = analyze(cv, mass_mg=2.0, method="signo").cycles.iloc[1]
        dirn = analyze(cv, mass_mg=2.0, method="direccion").cycles.iloc[1]
        q_tail = 1e-3 * 0.1 / RATE
        self.assertAlmostEqual(sign[COL_CAP_LIT] - dirn[COL_CAP_LIT], q_tail / 3.6 / 0.002, delta=1.5)
        self.assertGreater(sign[COL_CE], dirn[COL_CE])

    def test_without_time_uses_scan_rate(self):
        cv = CVData(potential_V=self.e, current_A=self.i)
        r = analyze(cv, mass_mg=2.0, scan_rate_V_s=RATE)
        ref = analyze(self.cv, mass_mg=2.0)
        np.testing.assert_allclose(r.cycles[COL_CAP_LIT], ref.cycles[COL_CAP_LIT], rtol=2e-3)

    def test_without_time_requires_rate(self):
        cv = CVData(potential_V=self.e, current_A=self.i)
        with self.assertRaises(ValueError):
            analyze(cv, mass_mg=2.0)

    def test_sign_flip(self):
        cv = CVData(potential_V=self.e, current_A=-self.i, time_s=self.t)
        r = analyze(cv, mass_mg=2.0)
        self.assertAlmostEqual(r.cycles[COL_CE].iloc[1], 80.0, delta=0.2)
        self.assertTrue(any("signo" in n for n in r.notes))

    def test_start_from_ocp_below_upper_vertex(self):
        e, t = triangle(e_start=0.8)
        cv = CVData(potential_V=e, current_A=constant_currents(e), time_s=t)
        r = analyze(cv, mass_mg=2.0)
        self.assertEqual(len(r.cycles), 3)
        self.assertIn("parcial", r.cycles["Notas"].iloc[0])

    def test_start_above_upper_vertex_is_not_partial(self):
        e, t = triangle(e_start=2.87)
        cv = CVData(potential_V=e, current_A=constant_currents(e), time_s=t)
        r = analyze(cv, mass_mg=2.0)
        self.assertEqual(r.cycles["Notas"].iloc[0], "")

    def test_leading_anodic_sweep_excluded(self):
        e, t = triangle(e_start=1.5, start_up=True)
        cv = CVData(potential_V=e, current_A=constant_currents(e), time_s=t)
        r = analyze(cv, mass_mg=2.0)
        self.assertEqual(len(r.cycles), 3)
        self.assertTrue(any("primer barrido es anódico" in n for n in r.notes))

    def test_window_limits_integration(self):
        r = analyze(self.cv, mass_mg=2.0, window=(0.01, 1.0))
        full = analyze(self.cv, mass_mg=2.0)
        ratio = r.cycles[COL_CAP_LIT].iloc[1] / full.cycles[COL_CAP_LIT].iloc[1]
        self.assertAlmostEqual(ratio, 0.99 / 1.99, delta=0.01)

    def test_no_mass_gives_absolute_values(self):
        r = analyze(self.cv, mass_mg=None)
        self.assertNotIn(COL_CAP_LIT, r.cycles.columns)
        self.assertIn("Capacidad delitiación (mAh)", r.cycles.columns)


if __name__ == "__main__":
    unittest.main()
