"""Tests de la referencia teórica, el ciclado galvanostático, la cinética y los parámetros redox.

Los valores de referencia proceden de la «Calculadora CV» (hoja Excel de PTCDA) y de su manual.
"""
import unittest

import numpy as np
import pandas as pd

from cvcap import electrochem as el
from cvcap import kinetics as kin
from cvcap import peaks as pk
from cvcap.analysis import ANODIC, CATHODIC, analyze
from cvcap.i18n import TEXTS, CvcapError, t

from test_features import graphite_like_cv


class TestElectrochem(unittest.TestCase):
    def test_theoretical_capacity(self):
        self.assertAlmostEqual(el.theoretical_capacity(2, 392.32), 136.63, places=1)  # PTCDA, 2 e⁻
        self.assertAlmostEqual(el.theoretical_capacity(4, 392.32), 273.26, places=1)  # PTCDA, 4 e⁻
        self.assertAlmostEqual(el.theoretical_capacity(1, 72.066), 371.9, delta=0.2)  # LiC6
        with self.assertRaises(CvcapError):
            el.theoretical_capacity(1, 0)

    def test_electrons_per_formula_matches_excel(self):
        # Excel: 0,29350 mAh en 1,08 mg de PTCDA → 3,978 e⁻/molécula
        q_C = 0.293495104387844 * 3.6
        self.assertAlmostEqual(float(el.electrons_per_formula(q_C, 1.08, 392.32)), 3.978, delta=0.002)

    def test_c_rate_current(self):
        ref = el.theoretical_capacity(2, 392.32)
        self.assertAlmostEqual(el.c_rate_current_mA(2.4, ref, 0.1), 0.0328, places=4)  # «unos 0,033 mA»
        self.assertAlmostEqual(el.c_rate_from_current(0.0328, 2.4, ref), 0.1, delta=0.001)
        self.assertAlmostEqual(el.current_density_mA_g(0.5, 2.0), 250.0)
        with self.assertRaises(CvcapError):
            el.c_rate_current_mA(0, ref, 1)

    def test_theory_table_with_and_without_blank(self):
        res = analyze(graphite_like_cv(cycles=2), mass_mg=2.0, method="direccion")
        plain = el.theory_table(res.cycles, 2.0, 72.066, 1.0)
        np.testing.assert_allclose(plain["cap_delit"], res.cycles["cap_delit"])
        self.assertTrue((plain["pct_delit"] > 0).all())
        x = plain["x_delit"].iloc[0]
        self.assertAlmostEqual(x, plain["pct_delit"].iloc[0] / 100.0, places=6)  # n_ref = 1 → x = fracción
        # Blanco: 0,2 mg de aditivo a 50 mAh/g restan 0,01 mAh de las dos cargas
        blank = el.theory_table(res.cycles, 2.0, 72.066, 1.0, additive_mass_mg=0.2, additive_capacity_mAh_g=50)
        np.testing.assert_allclose(blank["cap_delit"], plain["cap_delit"] - 0.01 / 0.002, rtol=1e-9)
        np.testing.assert_allclose(blank["cap_lit"], plain["cap_lit"] - 0.01 / 0.002, rtol=1e-9)

    def test_gcd_table(self):
        data = pd.DataFrame({
            "cycle": [1, 2, 3],
            "q_lit_mAh": [0.30, 0.28, np.nan],
            "q_delit_mAh": [0.27, 0.27, np.nan],
            "t_lit_h": [np.nan, np.nan, 8.0],
            "t_delit_h": [np.nan, np.nan, 7.5],
        })
        out = el.gcd_table(data, mass_mg=1.08, current_mA=0.03, reference_cycle=1)
        self.assertAlmostEqual(out["cap_delit"].iloc[0], 250.0)  # 0,27 mAh / 1,08 mg
        self.assertAlmostEqual(out["ce"].iloc[0], 90.0)
        self.assertAlmostEqual(out["ret"].iloc[0], 100.0)
        # ciclo 3 desde el tiempo: 8 h · 0,03 mA = 0,24 mAh
        self.assertAlmostEqual(out["cap_lit"].iloc[2], 0.24 / 0.00108, places=6)
        self.assertAlmostEqual(out["ret"].iloc[2], 7.5 * 0.03 / 0.27 * 100, places=6)

    def test_gcd_capacity_wins_over_time_and_missing_rows_dropped(self):
        data = pd.DataFrame({"cycle": [1, 2], "q_lit_mAh": [0.3, np.nan], "q_delit_mAh": [0.3, np.nan],
                             "t_lit_h": [99, np.nan], "t_delit_h": [99, np.nan]})
        out = el.gcd_table(data, 1.0, current_mA=0.01)
        self.assertEqual(len(out), 1)
        self.assertAlmostEqual(out["cap_lit"].iloc[0], 300.0)

    def test_gcd_reference_cycle_falls_back(self):
        data = pd.DataFrame({"cycle": [2, 3], "q_lit_mAh": [1.0, 1.0], "q_delit_mAh": [1.0, 0.5]})
        out = el.gcd_table(data, 1.0, reference_cycle=1)
        self.assertAlmostEqual(out["ret"].iloc[1], 50.0)


class TestKinetics(unittest.TestCase):
    @staticmethod
    def _peaks(rate_to_i, name="P", kind=CATHODIC, cycle=2, edge=False):
        entries = []
        for rate, i in rate_to_i.items():
            entries.append((rate, pd.DataFrame([{"cycle": cycle, "name": name, "kind": kind, "e_peak": 0.1,
                                                 "i_peak": i, "edge": edge}])))
        return entries

    def test_b_exponent_regimes(self):
        rates = [0.1, 0.2, 0.5, 1.0]
        for b_true, regime in [(0.5, "diffusive"), (0.75, "mixed"), (1.0, "capacitive")]:
            entries = self._peaks({v: -2e-4 * v ** b_true for v in rates})
            table = kin.b_table(kin.peak_currents_by_rate(entries, cycle=2))
            self.assertAlmostEqual(table["b"].iloc[0], b_true, places=6)
            self.assertAlmostEqual(table["r2"].iloc[0], 1.0, places=9)
            self.assertAlmostEqual(table["a"].iloc[0], 2e-4, places=9)
            self.assertEqual(table["regime"].iloc[0], regime)

    def test_b_needs_two_rates_and_skips_edge_peaks(self):
        one = kin.b_table(kin.peak_currents_by_rate(self._peaks({0.1: -1e-4}), 2))
        self.assertTrue(one.empty)
        edge = kin.peak_currents_by_rate(self._peaks({0.1: -1e-4, 0.2: -2e-4}, edge=True), 2)
        self.assertTrue(edge.empty)
        wrong_cycle = kin.peak_currents_by_rate(self._peaks({0.1: -1e-4, 0.2: -2e-4}), 5)
        self.assertTrue(wrong_cycle.empty)

    def test_sqrt_fit_and_randles_sevcik_roundtrip(self):
        d_true, n, area, conc = 3e-10, 1.0, 1.131, 0.0226
        slope_true = kin.RANDLES_SEVCIK_25C * n ** 1.5 * area * conc * np.sqrt(d_true)
        rates = [0.1, 0.2, 0.5, 1.0]  # mV/s
        entries = self._peaks({v: -slope_true * np.sqrt(v / 1000.0) for v in rates}, name="D", kind=ANODIC)
        table = kin.sqrt_rate_table(kin.peak_currents_by_rate(entries, 2))
        self.assertAlmostEqual(table["slope"].iloc[0], slope_true, delta=1e-9 * slope_true + 1e-15)
        self.assertAlmostEqual(table["r2"].iloc[0], 1.0, places=9)
        d = kin.randles_sevcik_D(table["slope"].iloc[0], n, area, conc)
        self.assertAlmostEqual(d / d_true, 1.0, places=6)
        with self.assertRaises(CvcapError):
            kin.randles_sevcik_D(1e-3, 1, 0, 0.02)

    def test_dunn_recovers_known_k1_k2(self):
        e = np.linspace(2.0, 0.01, 800)  # barrido catódico
        k1 = 1e-4 * (1 + 0.5 * np.sin(3 * e))  # A/(mV/s)
        k2 = 2e-4 * np.exp(-((e - 0.5) / 0.2) ** 2)  # A/(mV/s)^½
        sweeps = [(v, e, -(k1 * v + k2 * np.sqrt(v))) for v in (0.1, 0.2, 0.5, 1.0)]
        # (la corriente catódica es negativa: k1 y k2 salen con signo negativo)
        out = kin.dunn_separation(sweeps)
        self.assertEqual(out.rates, [0.1, 0.2, 0.5, 1.0])
        k1_grid = np.interp(out.potential, e[::-1], k1[::-1])
        k2_grid = np.interp(out.potential, e[::-1], k2[::-1])
        np.testing.assert_allclose(-out.k1, k1_grid, rtol=1e-9, atol=1e-15)
        np.testing.assert_allclose(-out.k2, k2_grid, rtol=1e-6, atol=1e-12)
        # La fracción capacitiva crece al bajar √v: aumenta con v (k1·v / (k1·v + k2·√v))
        pct = out.fractions["cap_pct"].to_numpy()
        self.assertTrue(np.all(np.diff(pct) > 0))
        np.testing.assert_allclose(out.fractions["cap_pct"] + out.fractions["diff_pct"], 100.0)
        np.testing.assert_allclose(out.i_cap + 0, out.k1[None, :] * np.array(out.rates)[:, None])

    def test_dunn_errors(self):
        e = np.linspace(2, 0, 50)
        with self.assertRaises(CvcapError):
            kin.dunn_separation([(0.1, e, -e)])
        with self.assertRaises(CvcapError):
            kin.dunn_separation([(0.1, e, -e), (0.2, e + 10, -e)])

    def test_sweep_of_and_dunn_from_results(self):
        # Dos «medidas» a distinta velocidad con una parte capacitiva y otra difusiva en el barrido catódico
        results, rates = [], [0.5, 1.0, 2.0]
        for v in rates:
            res = analyze(graphite_like_cv(cycles=2, rate=v * 1e-3), mass_mg=2.0, scan_rate_V_s=v * 1e-3)
            results.append((v, res))
        found = kin.sweep_of(results[0][1], 2, CATHODIC)
        self.assertIsNotNone(found)
        self.assertIsNone(kin.sweep_of(results[0][1], 99, CATHODIC))
        out = kin.dunn_from_results(results, cycle=2, kind=CATHODIC)
        self.assertEqual(len(out.fractions), 3)


class TestRedoxAndWindowCharges(unittest.TestCase):
    def setUp(self):
        self.res = analyze(graphite_like_cv(cycles=3), mass_mg=2.0, method="direccion")
        self.windows = [pk.PeakWindow("Lit", CATHODIC, 0.01, 0.5), pk.PeakWindow("Delit", ANODIC, 0.1, 0.5)]
        self.peaks = pk.window_peaks(self.res, self.windows)

    def test_redox_parameters(self):
        # el pico SEI (0,65 V) solo existe en el ciclo 1: es el único par sin extremos en el borde
        windows = [pk.PeakWindow("SEI", CATHODIC, 0.4, 1.0), pk.PeakWindow("Delit", ANODIC, 0.1, 0.5)]
        out = pk.redox_parameters(pk.window_peaks(self.res, windows), "Delit", "SEI")
        self.assertEqual(list(out.columns), pk.REDOX_COLUMNS)
        self.assertEqual(out["cycle"].tolist(), [1])
        row = out.iloc[0]
        self.assertAlmostEqual(row["e_c"], 0.65, delta=0.01)
        self.assertAlmostEqual(row["dep"], (row["e_a"] - row["e_c"]) * 1000)
        self.assertAlmostEqual(row["e_half"], (row["e_a"] + row["e_c"]) / 2)
        self.assertAlmostEqual(row["ratio"], abs(row["i_a"] / row["i_c"]))

    def test_redox_ignores_edge_peaks(self):
        # el extremo catódico cae en el borde de la ventana (corriente exponencial creciente hacia 0,01 V)
        self.assertTrue(self.peaks[self.peaks["name"] == "Lit"]["edge"].all())
        self.assertTrue(pk.redox_parameters(self.peaks, "Delit", "Lit").empty)

    def test_window_charges_full_window_equals_cycle_charge(self):
        full = [pk.PeakWindow("todo_c", CATHODIC, 0.0, 2.1), pk.PeakWindow("todo_a", ANODIC, 0.0, 2.1)]
        out = pk.window_charges(self.res, full)
        cyc = self.res.cycles.set_index("cycle")
        for _, r in out[out["kind"] == CATHODIC].iterrows():
            self.assertAlmostEqual(r["q_C"], cyc.loc[r["cycle"], "q_lit"], places=9)
            self.assertAlmostEqual(r["pct"], 100.0, places=6)
            self.assertAlmostEqual(r["mah_g"], cyc.loc[r["cycle"], "cap_lit"], places=6)

    def test_window_charges_by_sign_never_exceeds_100(self):
        # CV con corriente negativa al inicio del barrido anódico: la carga neta anódica queda muy por debajo
        # de la positiva y con el método «direccion» el % podía pasar del 100 %.
        cv = graphite_like_cv(cycles=3)
        direction = np.sign(np.gradient(cv.potential_V))
        low = (direction > 0) & (cv.potential_V < 0.15)
        cv.current_A[low] -= 6e-4
        res = analyze(cv, mass_mg=2.0, method="signo")
        wins = [pk.PeakWindow("a", ANODIC, 0.0, 0.3), pk.PeakWindow("b", ANODIC, 0.3, 2.1),
                pk.PeakWindow("c", CATHODIC, 0.0, 2.1)]
        out = pk.window_charges(res, wins)
        self.assertTrue((out["pct"] <= 100.0 + 1e-6).all())
        full = pk.window_charges(res, [pk.PeakWindow("todo", ANODIC, 0.0, 2.1)])
        np.testing.assert_allclose(full["pct"], 100.0)
        # la carga anódica de la ventana completa es la de delitiación (corriente positiva) del ciclo
        delit = res.cycles.set_index("cycle")["q_delit"]
        for _, r in full.iterrows():
            self.assertLessEqual(r["q_C"], delit.loc[r["cycle"]] + 1e-12)

    def test_window_charges_split_adds_up(self):
        parts = [pk.PeakWindow("a", ANODIC, 0.0, 0.3), pk.PeakWindow("b", ANODIC, 0.3, 2.1)]
        out = pk.window_charges(self.res, parts)
        by_cycle = out.groupby("cycle")["pct"].sum()
        np.testing.assert_allclose(by_cycle, 100.0, atol=0.2)  # el punto de corte se reparte entre ambas


class TestTranslations(unittest.TestCase):
    def test_new_keys_in_both_languages(self):
        for key in ("th.pct_delit", "kin.b_title", "regime.mixed", "gcd.title", "rx.title", "qw.pct",
                    "err.dunn_rates", "tab.theory", "nav.gcd"):
            self.assertIn(key, TEXTS["es"])
            self.assertIn(key, TEXTS["en"])
            self.assertNotEqual(t(key, "es"), key)

    def test_localizers(self):
        table = kin.b_table(kin.peak_currents_by_rate(
            TestKinetics._peaks({0.1: -1e-4, 0.5: -3e-4}), 2))
        es = kin.localize_b_table(table, "es")
        self.assertIn("Régimen", es.columns)
        en = kin.localize_b_table(table, "en")
        self.assertIn("Regime", en.columns)
        th = el.theory_table(analyze(graphite_like_cv(cycles=1), mass_mg=2.0).cycles, 2.0, 72.066, 1.0)
        self.assertIn("Cycle", el.localize_theory(th, "en").columns)


if __name__ == "__main__":
    unittest.main()
