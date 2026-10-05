"""Aplicación web: capacidad a partir de CV exportadas de NOVA (Metrohm Autolab).

Ejecutar en local:   streamlit run app.py
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from cvcap import __version__
from cvcap import analysis as an
from cvcap import io as cvio
from cvcap import report

EXAMPLE_FILE = Path(__file__).parent / "examples" / "ejemplo_nova_cv.txt"
FILE_TYPES = sorted(ext.lstrip(".") for ext in cvio.SUPPORTED_EXTENSIONS)
NONE = "(ninguna)"

st.set_page_config(page_title="CV → Capacidad", page_icon="🔋", layout="wide")


class _LocalFile:
    """Imita el objeto de st.file_uploader para el archivo de ejemplo."""

    def __init__(self, path: Path):
        self.name = path.name
        self._data = path.read_bytes()

    def getvalue(self) -> bytes:
        return self._data


@st.cache_data(show_spinner=False)
def parse_table(data: bytes, name: str) -> pd.DataFrame:
    return cvio.load_table(data, name)


def fmt_number(value, digits=1, suffix=""):
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return "—"
    return f"{value:,.{digits}f}{suffix}".replace(",", " ").replace(".", ",")


# --------------------------------------------------------------------------
# Barra lateral
# --------------------------------------------------------------------------
with st.sidebar:
    st.header("Electrodo")
    mass_mode = st.radio(
        "Masa activa",
        ["Introducir la masa activa", "Calcular desde el disco"],
        help="Masa activa = (masa del disco − masa del Cu) × fracción de material activo.",
    )
    if mass_mode == "Introducir la masa activa":
        default_mass = st.number_input("Masa activa (mg)", min_value=0.0, value=2.0, step=0.01, format="%.3f")
    else:
        disc = st.number_input("Masa del disco con electrodo (mg)", min_value=0.0, value=6.0, step=0.01, format="%.3f")
        cu = st.number_input("Masa de un disco de Cu limpio (mg)", min_value=0.0, value=3.5, step=0.01, format="%.3f")
        frac = st.number_input("Fracción de material activo", min_value=0.0, max_value=1.0, value=0.80, step=0.01)
        default_mass = an.active_mass_mg(disc, cu, frac)
        st.caption(f"Masa activa: **{fmt_number(default_mass, 3)} mg**")
    use_area = st.checkbox("Calcular capacidad areal (mAh/cm²)")
    area = None
    if use_area:
        diameter = st.number_input("Diámetro del disco (mm)", min_value=1.0, value=12.0, step=0.5)
        area = an.disc_area_cm2(diameter)
        st.caption(f"Área: {fmt_number(area, 3)} cm²")

    st.header("Cálculo")
    method_label = st.radio(
        "Reparto de la carga en cada ciclo",
        ["Por signo de corriente (recomendado)", "Por dirección de barrido"],
        help=(
            "Por signo: litiación = toda la corriente negativa del ciclo; delitiación = toda la positiva "
            "(equivale a Q+/Q− de NOVA). Tiene en cuenta que el grafito sigue litiándose al principio del "
            "barrido anódico. Por dirección: carga neta de cada barrido."
        ),
    )
    method = "signo" if method_label.startswith("Por signo") else "direccion"
    ref_cycle = st.number_input("Ciclo de referencia para la retención", min_value=1, value=2, step=1)
    with st.expander("Opciones avanzadas"):
        hysteresis_mV = st.number_input(
            "Umbral de detección de vértices (mV)", min_value=1.0, value=20.0, step=1.0,
            help="Cambio mínimo de potencial en sentido contrario para considerar que el barrido ha girado.",
        )
        scan_rate_mV = st.number_input(
            "Velocidad de barrido (mV/s)", min_value=0.001, value=0.1, step=0.05, format="%.3f",
            help="Solo se usa si el archivo no tiene columna de tiempo.",
        )
        use_window = st.checkbox("Integrar solo dentro de una ventana de potencial")
        window = None
        if use_window:
            c1, c2 = st.columns(2)
            e_min = c1.number_input("E mín (V)", value=0.01, step=0.01, format="%.3f")
            e_max = c2.number_input("E máx (V)", value=1.0, step=0.05, format="%.3f")
            window = (e_min, e_max)
        auto_sign = st.checkbox("Corregir automáticamente el signo de la corriente", value=True)
    st.caption(f"cvcap v{__version__}")

# --------------------------------------------------------------------------
# Cabecera y carga de archivos
# --------------------------------------------------------------------------
st.title("Capacidad a partir de voltametría cíclica")
st.write(
    "Sube los archivos de CV exportados desde **NOVA** (ASCII `.txt`/`.csv`/`.dat` o Excel `.xlsx`/`.xls`). "
    "El programa ordena los datos en el tiempo, detecta los barridos y calcula, para cada ciclo, "
    "la capacidad de litiación y delitiación, la eficiencia coulómbica y la retención."
)

uploads = st.file_uploader("Archivos de NOVA", type=FILE_TYPES, accept_multiple_files=True)
use_example = False
if not uploads and EXAMPLE_FILE.exists():
    use_example = st.toggle("Probar con un archivo de ejemplo (datos simulados)")
files = list(uploads or [])
if use_example:
    files = [_LocalFile(EXAMPLE_FILE)]

if not files:
    st.info("Sube uno o varios archivos para empezar. En NOVA: selecciona el comando de la CV → "
            "tabla de datos → exportar como ASCII o Excel.")
    with st.expander("¿Cómo se calcula?"):
        st.markdown(an.__doc__)
    st.stop()

# Nombres únicos (por si se suben dos archivos con el mismo nombre)
names, seen = [], {}
for f in files:
    count = seen.get(f.name, 0)
    seen[f.name] = count + 1
    names.append(f.name if count == 0 else f"{f.name} ({count + 1})")

# Masa por archivo (editable)
st.subheader("Masa activa de cada electrodo")
mass_table = pd.DataFrame({"Archivo": names, "Masa activa (mg)": [round(default_mass, 4)] * len(names)})
mass_table = st.data_editor(
    mass_table,
    hide_index=True,
    disabled=["Archivo"],
    use_container_width=True,
    column_config={
        "Masa activa (mg)": st.column_config.NumberColumn(min_value=0.0, step=0.001, format="%.3f"),
    },
    key="masses_" + "|".join(names) + f"_{default_mass:.4f}",
)
masses = dict(zip(mass_table["Archivo"], mass_table["Masa activa (mg)"]))

# --------------------------------------------------------------------------
# Análisis de cada archivo
# --------------------------------------------------------------------------
results = []
for f, label in zip(files, names):
    st.divider()
    st.header(label)
    try:
        table = parse_table(f.getvalue(), f.name)
    except cvio.NovaFormatError as exc:
        st.error(f"No se pudo leer el archivo: {exc}")
        continue
    except Exception as exc:  # noqa: BLE001
        st.error(f"Error inesperado al leer el archivo: {exc}")
        continue

    detected = cvio.detect_columns(table)
    missing = "potential" not in detected or "current" not in detected
    with st.expander("Columnas detectadas", expanded=missing):
        options = [NONE] + [str(c) for c in table.columns]
        mapping = {}
        cols = st.columns(4)
        for k, role in enumerate(["potential", "current", "time", "scan"]):
            default = detected.get(role)
            index = options.index(str(default)) if default is not None and str(default) in options else 0
            choice = cols[k].selectbox(cvio.ROLE_LABELS[role], options, index=index, key=f"{label}_{role}")
            if choice != NONE:
                mapping[role] = choice
        for role in ("index", "q_plus", "q_minus"):
            if role in detected:
                mapping[role] = detected[role]
        st.dataframe(table.head(8), use_container_width=True)

    try:
        cv = cvio.to_cvdata(table, mapping, source=label)
        mass = masses.get(label)
        res = an.analyze(
            cv,
            mass_mg=mass if mass and mass > 0 else None,
            area_cm2=area,
            reference_cycle=int(ref_cycle),
            hysteresis=hysteresis_mV / 1000.0,
            scan_rate_V_s=scan_rate_mV / 1000.0,
            window=window,
            auto_sign=auto_sign,
            name=label,
            method=method,
        )
    except (cvio.NovaFormatError, ValueError) as exc:
        st.error(str(exc))
        continue
    results.append(res)

    for note in res.notes:
        st.caption(f"ℹ️ {note}")

    cyc = res.cycles
    has_mass = an.COL_CAP_DELIT in cyc.columns
    complete = cyc[cyc[an.COL_Q_DELIT].notna()]
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Eficiencia coulómbica ciclo 1", fmt_number(cyc[an.COL_CE].iloc[0], 1, " %"))
    if has_mass:
        m2.metric("Delitiación ciclo 1", fmt_number(cyc[an.COL_CAP_DELIT].iloc[0], 1, " mAh/g"))
        if not complete.empty:
            m3.metric(f"Delitiación ciclo {int(complete[an.COL_CYCLE].iloc[-1])}",
                      fmt_number(complete[an.COL_CAP_DELIT].iloc[-1], 1, " mAh/g"))
    else:
        m2.metric("Delitiación ciclo 1", fmt_number(cyc[an.COL_MAH_DELIT].iloc[0], 4, " mAh"))
    if not complete.empty:
        m4.metric("Retención último ciclo", fmt_number(complete[an.COL_RET].iloc[-1], 1, " %"))

    tab_res, tab_cv, tab_seg = st.tabs(["Resultados por ciclo", "Gráficas", "Segmentos y comprobación"])
    with tab_res:
        st.dataframe(cyc, hide_index=True, use_container_width=True,
                     column_config={c: st.column_config.NumberColumn(format="%.4g") for c in cyc.columns
                                    if c not in (an.COL_CYCLE, an.COL_NOTES)})
    with tab_cv:
        left, right = st.columns(2)
        fig = go.Figure()
        e, i = res.cv.potential_V, res.current_A * 1e3
        for cycle_label in pd.unique(res.point_cycle):
            mask = res.point_cycle == cycle_label
            fig.add_trace(go.Scattergl(x=e[mask], y=i[mask], mode="lines", name=str(cycle_label)))
        fig.update_layout(title="Voltamograma", xaxis_title="Potencial (V vs Li⁺/Li)",
                          yaxis_title="Corriente (mA)", height=420, legend_title_text="")
        left.plotly_chart(fig, use_container_width=True)

        ycol = an.COL_CAP_DELIT if has_mass else an.COL_MAH_DELIT
        ylit = an.COL_CAP_LIT if has_mass else an.COL_MAH_LIT
        unit = "mAh/g" if has_mass else "mAh"
        fig2 = make_subplots(specs=[[{"secondary_y": True}]])
        fig2.add_trace(go.Bar(x=cyc[an.COL_CYCLE], y=cyc[ylit], name="Litiación"), secondary_y=False)
        fig2.add_trace(go.Bar(x=cyc[an.COL_CYCLE], y=cyc[ycol], name="Delitiación"), secondary_y=False)
        fig2.add_trace(go.Scatter(x=cyc[an.COL_CYCLE], y=cyc[an.COL_CE], name="Ef. coulómbica",
                                  mode="lines+markers"), secondary_y=True)
        fig2.update_layout(title="Capacidad y eficiencia por ciclo", barmode="group", height=420,
                           xaxis=dict(title="Ciclo", dtick=1), legend_title_text="")
        fig2.update_yaxes(title_text=f"Capacidad ({unit})", secondary_y=False)
        fig2.update_yaxes(title_text="Eficiencia coulómbica (%)", range=[0, 110], secondary_y=True)
        right.plotly_chart(fig2, use_container_width=True)
    with tab_seg:
        st.dataframe(res.segments, hide_index=True, use_container_width=True)
        if res.nova_check is not None:
            st.markdown("**Comprobación con las columnas Q+ / Q− de NOVA** (carga total de todo el archivo)")
            st.dataframe(res.nova_check, hide_index=True, use_container_width=True)

# --------------------------------------------------------------------------
# Comparación y descargas
# --------------------------------------------------------------------------
if not results:
    st.stop()

st.divider()
st.header("Resumen")
summary = report.summary_table(results)
st.dataframe(summary, hide_index=True, use_container_width=True)

if len(results) > 1:
    comp = go.Figure()
    for r in results:
        col = an.COL_CAP_DELIT if an.COL_CAP_DELIT in r.cycles.columns else an.COL_MAH_DELIT
        comp.add_trace(go.Scatter(x=r.cycles[an.COL_CYCLE], y=r.cycles[col], mode="lines+markers", name=r.name))
    comp.update_layout(title="Capacidad de delitiación por ciclo", xaxis=dict(title="Ciclo", dtick=1),
                       yaxis_title="Capacidad", height=420)
    st.plotly_chart(comp, use_container_width=True)

c1, c2 = st.columns(2)
c1.download_button(
    "Descargar resultados (Excel)",
    data=report.results_to_excel(results),
    file_name="capacidad_cv.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    use_container_width=True,
)
c2.download_button(
    "Descargar ciclos (CSV)",
    data=report.results_to_csv(results),
    file_name="capacidad_cv.csv",
    mime="text/csv",
    use_container_width=True,
)

with st.expander("¿Cómo se calcula?"):
    st.markdown(an.__doc__)
