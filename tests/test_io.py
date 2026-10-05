"""Tests de lectura de los distintos formatos de exportación de NOVA."""
import io
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from cvcap.io import NovaFormatError, detect_columns, load_table, read_nova, split_name_unit

E = np.array([2.0, 1.5, 1.0, 0.5, 0.01, 0.5, 1.0, 1.5, 2.0, 1.5, 1.0, 0.5])
T = np.arange(len(E)) * 10.0
I = np.array([-1e-6, -2e-6, -1e-5, -1e-4, -5e-4, 3e-4, 1e-5, 1e-6, 1e-6, -1e-6, -1e-5, -1e-4])


def nova_text(sep=";", decimal=",", header=None, current_unit="A", factor=1.0, extra_meta=False):
    header = header or ["Potential applied (V)", "Time (s)", f"WE(1).Current ({current_unit})", "Scan", "Index"]
    lines = []
    if extra_meta:
        lines += ["Procedure: CV staircase", "Instrument: AUT52907", ""]
    lines.append(sep.join(header))
    for k, (e, t, i) in enumerate(zip(E, T, I * factor), start=1):
        vals = [repr(float(e)), repr(float(t)), repr(float(i)), "1", str(k)]
        if decimal == ",":
            vals = [v.replace(".", ",") for v in vals]
        lines.append(sep.join(vals))
    return "\r\n".join(lines) + "\r\n"


class TestNames(unittest.TestCase):
    def test_split(self):
        self.assertEqual(split_name_unit("WE(1).Current (mA)"), ("we(1).current", "ma"))
        self.assertEqual(split_name_unit("WE(1).Potential"), ("we(1).potential", ""))
        self.assertEqual(split_name_unit("Potential applied (V)"), ("potential applied", "v"))
        self.assertEqual(split_name_unit("I/µA"), ("i", "ua"))


class TestText(unittest.TestCase):
    def check(self, cv, factor=1.0):
        np.testing.assert_allclose(cv.potential_V, E)
        np.testing.assert_allclose(cv.current_A, I, rtol=1e-12)
        np.testing.assert_allclose(cv.time_s, T)

    def test_semicolon_decimal_comma(self):
        self.check(read_nova(nova_text().encode(), "cv.txt"))

    def test_tab_decimal_point(self):
        self.check(read_nova(nova_text(sep="\t", decimal=".").encode(), "cv.txt"))

    def test_tab_decimal_comma(self):
        self.check(read_nova(nova_text(sep="\t", decimal=",").encode(), "cv.dat"))

    def test_csv_comma(self):
        self.check(read_nova(nova_text(sep=",", decimal=".").encode(), "cv.csv"))

    def test_spaces(self):
        text = nova_text(sep=" ", decimal=".", header=["E/V", "t/s", "I/A", "Scan", "Index"])
        self.check(read_nova(text.encode(), "cv.txt"))

    def test_utf16(self):
        self.check(read_nova(nova_text().encode("utf-16"), "cv.txt"))

    def test_metadata_lines_before_header(self):
        self.check(read_nova(nova_text(extra_meta=True).encode(), "cv.txt"))

    def test_milliamps(self):
        self.check(read_nova(nova_text(current_unit="mA", factor=1e3).encode(), "cv.txt"))

    def test_trailing_separator_and_text_column(self):
        lines = nova_text().splitlines()
        lines[0] += ";Current range;"
        lines[1:] = [ln + ";1 mA;" for ln in lines[1:]]
        cv = read_nova("\n".join(lines).encode(), "cv.txt")
        self.check(cv)

    def test_unsorted_rows_are_sorted_by_time(self):
        lines = nova_text().splitlines()
        body = lines[1:]
        body = body[::-1]  # orden inverso, como cuando NOVA ordena por otra columna
        cv = read_nova("\n".join([lines[0]] + body).encode(), "cv.txt")
        self.check(cv)
        self.assertTrue(any("reordenaron" in n for n in cv.notes))

    def test_file_object_and_path(self):
        data = nova_text().encode()
        self.check(read_nova(io.BytesIO(data), "cv.txt"))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cv.txt"
            path.write_bytes(data)
            self.check(read_nova(path))

    def test_nox_rejected(self):
        with self.assertRaises(NovaFormatError):
            load_table(b"\x00\x01binario", "medida.nox")

    def test_missing_current(self):
        text = "Potential applied (V);Time (s)\n" + "\n".join(f"{e};{t}" for e, t in zip(E, T))
        with self.assertRaises(NovaFormatError):
            read_nova(text.encode(), "cv.txt")


class TestExcel(unittest.TestCase):
    def test_xlsx_with_title_rows(self):
        df = pd.DataFrame({"Potential applied (V)": E, "Time (s)": T, "WE(1).Current (A)": I, "Scan": 1})
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            pd.DataFrame({"x": ["notas"]}).to_excel(writer, sheet_name="Info", index=False)
            df.to_excel(writer, sheet_name="Datos", index=False, startrow=2)
        cv = read_nova(buf.getvalue(), "cv.xlsx")
        np.testing.assert_allclose(cv.current_A, I)
        np.testing.assert_allclose(cv.time_s, T)

    def test_detect_columns(self):
        df = pd.DataFrame({
            "Index": [1, 2], "WE(1).Potential (V)": [1.0, 2.0], "Potential applied (V)": [1.0, 2.0],
            "WE(1).Current (A)": [0.1, 0.2], "Time (s)": [0, 1], "Q+": [0, 0], "Q-": [0, 0],
        })
        m = detect_columns(df)
        self.assertEqual(m["potential"], "Potential applied (V)")
        self.assertEqual(m["current"], "WE(1).Current (A)")
        self.assertEqual(m["q_plus"], "Q+")
        self.assertEqual(m["q_minus"], "Q-")


if __name__ == "__main__":
    unittest.main()
