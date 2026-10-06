"""Aplicación web: capacidad a partir de CV exportadas de NOVA (Metrohm Autolab).

Ejecutar en local:   streamlit run app.py
"""
from __future__ import annotations

import os
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from cvcap import __version__, colors
from cvcap import analysis as an
from cvcap import io as cvio
from cvcap import peaks as pk
from cvcap import report
from cvcap.db import MATERIALS, PREP_FIELDS, Database, record_from_result
from cvcap.i18n import CvcapError, t

APP_DIR = Path(__file__).parent
EXAMPLE_FILE = APP_DIR / "examples" / "ejemplo_nova_cv.txt"
FILE_TYPES = sorted(ext.lstrip(".") for ext in cvio.SUPPORTED_EXTENSIONS)
NONE = "__none__"
LANGS = {"es": "Español", "en": "English"}
CURRENT_UNIT_LABELS = {"mA": "mA", "uA": "µA", "A": "A", "A/g": "A/g"}
PREP_DEFAULTS = {
    "composition": "80:10:10",
    "coating": "Doctor blade",
    "electrolyte": "1 M LiPF6 EC/DEC/EMC 1:1:1",
    "cell": "CR2025",
}

st.set_page_config(page_title="CV → Capacity", page_icon="🔋", layout="wide")
ss = st.session_state

# --------------------------------------------------------------------------
# Idioma y navegación
# --------------------------------------------------------------------------
with st.sidebar:
    lang = st.radio("Idioma / Language", list(LANGS), format_func=LANGS.get, horizontal=True, key="lang")


def T(key: str, **params) -> str:
    return t(key, lang, **params)


def err_text(exc: Exception) -> str:
    return exc.localized(lang) if isinstance(exc, CvcapError) else str(exc)


def fmt(value, digits=1, suffix=""):
    if value is None or (isinstance(value, float) and not np.isfinite(value)):
        return "—"
    text = f"{value:,.{digits}f}"
    if lang == "es":
        text = text.replace(",", " ").replace(".", ",")
    return text + suffix


def db_location() -> str:
    path = os.environ.get("CVCAP_DB_PATH")
    if not path:
        try:
            path = st.secrets.get("CVCAP_DB_PATH")  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001 - sin archivo de secretos
            path = None
    return str(path or APP_DIR / "data" / "cvcap.sqlite")


@st.cache_resource(show_spinner=False)
def get_db(path: str) -> Database:
    return Database(path)


@st.cache_data(show_spinner=False)
def parse_table(data: bytes, name: str) -> pd.DataFrame:
    return cvio.load_table(data, name)


db = get_db(db_location())

with st.sidebar:
    page = st.radio(T("nav.page"), ["analyze", "database"], format_func=lambda p: T(f"nav.{p}"), key="page")


class _LocalFile:
    """Imita el objeto de st.file_uploader para el archivo de ejemplo."""

    def __init__(self, path: Path):
        self.name = path.name
        self._data = path.read_bytes()

    def getvalue(self) -> bytes:
        return self._data


# --------------------------------------------------------------------------
# Gráficas
# --------------------------------------------------------------------------
def cv_figure(potential, current_A, point_cycle, peaks_df, ramp, darkest_first, show_peaks, peak_labels, title,
              show_edge=False):
    fig = go.Figure()
    cycles = sorted(int(c) for c in np.unique(point_cycle) if c > 0)
    shades = dict(zip(cycles, colors.cycle_shades(ramp, len(cycles), darkest_first)))
    i_mA = np.asarray(current_A) * 1e3
    outside = point_cycle == 0
    if outside.any():
        fig.add_trace(go.Scattergl(x=potential[outside], y=i_mA[outside], mode="lines", name=T("no_cycle"),
                                   line=dict(color=colors.NO_CYCLE_COLOR, width=1, dash="dot")))
    for c in cycles:
        mask = point_cycle == c
        fig.add_trace(go.Scattergl(
            x=potential[mask], y=i_mA[mask], mode="lines", name=an.cycle_label(c, lang),
            line=dict(color=shades[c], width=2),
            hovertemplate="E = %{x:.3f} V<br>I = %{y:.4f} mA<extra>" + an.cycle_label(c, lang) + "</extra>",
        ))
    if show_peaks and peaks_df is not None and not peaks_df.empty:
        shown_peaks = peaks_df if show_edge else peaks_df[~peaks_df["edge"].astype(bool)]
        # Etiqueta cada pico una sola vez: en el último ciclo en que aparece como pico verdadero
        label_rows = set()
        true_peaks = shown_peaks[~shown_peaks["edge"].astype(bool)]
        for _name, group in true_peaks.groupby("name"):
            label_rows.add(group["cycle"].idxmax())
        for kind, symbol in ((an.ANODIC, "triangle-up"), (an.CATHODIC, "triangle-down")):
            sub = shown_peaks[shown_peaks["kind"] == kind]
            if sub.empty:
                continue
            labels = [str(n) if idx in label_rows else "" for idx, n in zip(sub.index, sub["name"])]
            fig.add_trace(go.Scatter(
                x=sub["e_peak"], y=sub["i_peak"] * 1e3,
                mode="markers+text" if peak_labels else "markers",
                name=T(f"legend.peaks_{kind}"),
                text=labels if peak_labels else None,
                textposition="top center" if kind == an.ANODIC else "bottom center",
                textfont=dict(size=11, color="#444444"),
                marker=dict(
                    size=12, color=[shades.get(int(c), colors.NO_CYCLE_COLOR) for c in sub["cycle"]],
                    symbol=[symbol + ("-open" if e else "") for e in sub["edge"]],
                    line=dict(color="#ffffff", width=2),
                ),
                customdata=np.stack([sub["name"], sub["cycle"]], axis=1),
                hovertemplate="%{customdata[0]} · " + T("col.cycle") + " %{customdata[1]}"
                              "<br>E = %{x:.3f} V<br>I = %{y:.4f} mA<extra></extra>",
            ))
    fig.update_layout(title=title, xaxis_title=T("axis.potential"), yaxis_title=T("axis.current"), height=460,
                      legend_title_text="", hovermode="closest", margin=dict(t=50, r=10))
    fig.update_xaxes(showgrid=True, gridcolor="#eeeeee", zeroline=False)
    fig.update_yaxes(showgrid=True, gridcolor="#eeeeee", zeroline=True, zerolinecolor="#cccccc")
    return fig


def capacity_figures(cycles: pd.DataFrame):
    has_mass = "cap_delit" in cycles.columns
    lit, delit = ("cap_lit", "cap_delit") if has_mass else ("mah_lit", "mah_delit")
    unit = "mAh/g" if has_mass else "mAh"
    fig = go.Figure()
    fig.add_trace(go.Bar(x=cycles["cycle"], y=cycles[lit], name=T("legend.lithiation"),
                         marker_color=colors.categorical(0)))
    fig.add_trace(go.Bar(x=cycles["cycle"], y=cycles[delit], name=T("legend.delithiation"),
                         marker_color=colors.categorical(1)))
    fig.update_layout(title=T("plot.capacity"), barmode="group", bargap=0.3, bargroupgap=0.08, height=380,
                      xaxis=dict(title=T("col.cycle"), dtick=1), yaxis_title=f"{T('axis.capacity')} ({unit})",
                      legend_title_text="", margin=dict(t=50, r=10))
    fig_ce = go.Figure(go.Scatter(x=cycles["cycle"], y=cycles["ce"], mode="lines+markers",
                                  name=T("col.ce"), line=dict(color=colors.categorical(0), width=2),
                                  marker=dict(size=9)))
    fig_ce.update_layout(title=T("plot.ce"), height=380, xaxis=dict(title=T("col.cycle"), dtick=1),
                         yaxis=dict(title=T("col.ce"), range=[0, 105]), showlegend=False, margin=dict(t=50, r=10))
    return fig, fig_ce


def peaks_tables(peaks_df: pd.DataFrame, reference_cycle: int):
    """Tabla larga traducida y tabla pivotada de potenciales de pico."""
    shifted = pk.add_reference_shifts(peaks_df, reference_cycle)
    long = pd.DataFrame({
        T("pk.name"): shifted["name"],
        T("pk.kind"): shifted["kind"].map(lambda k: T(f"kind_short.{k}")),
        T("col.cycle"): shifted["cycle"].astype(int),
        T("pk.e"): shifted["e_peak"],
        T("pk.i"): shifted["i_peak"] * 1e3,
        T("pk.de_ref", ref=reference_cycle): shifted["de_ref"],
        T("pk.di_ref", ref=reference_cycle): shifted["di_ref"],
        T("pk.edge"): shifted["edge"].map(lambda e: T("yes") if e else T("no")),
    })
    pivot = peaks_df.pivot_table(index="name", columns="cycle", values="e_peak", aggfunc="first")
    pivot.columns = [an.cycle_label(int(c), lang) for c in pivot.columns]
    pivot.index.name = T("pk.name")
    return long, pivot


def compute_peaks(res: an.AnalysisResult, windows, use_auto: bool, prominence: float) -> pd.DataFrame:
    frames = [pk.window_peaks(res, windows)] if windows else []
    if use_auto:
        frames.append(pk.auto_peaks(res, prominence=prominence))
    frames = [f for f in frames if not f.empty]
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=pk.PEAK_COLUMNS)


# --------------------------------------------------------------------------
# Formulario de muestra (análisis y base de datos)
# --------------------------------------------------------------------------
def sample_form(prefix: str, defaults: dict, with_id: bool = False, id_default: str = ""):
    out = {}
    if with_id:
        out["id"] = st.text_input(T("meta.id"), value=id_default, key=f"{prefix}_id", help=T("help.id"))
    c1, c2, c3 = st.columns(3)
    out["name"] = c1.text_input(T("meta.name"), value=defaults.get("name", ""), key=f"{prefix}_name")
    material = defaults.get("material", "commercial")
    out["material"] = c2.selectbox(T("meta.material"), MATERIALS, format_func=lambda m: T(f"material.{m}"),
                                   index=MATERIALS.index(material) if material in MATERIALS else 0,
                                   key=f"{prefix}_material")
    out["batch"] = c3.text_input(T("meta.batch"), value=defaults.get("batch", ""), key=f"{prefix}_batch")
    measured = defaults.get("measured_on") or date.today().isoformat()
    try:
        measured_value = date.fromisoformat(str(measured)[:10])
    except ValueError:
        measured_value = date.today()
    out["measured_on"] = c1.date_input(T("meta.measured_on"), value=measured_value,
                                       key=f"{prefix}_date").isoformat()
    st.markdown(f"**{T('prep.title')}**")
    prep_defaults = defaults.get("prep") or {}
    prep = {}
    cols = st.columns(3)
    for k, (field_key, kind) in enumerate(PREP_FIELDS.items()):
        col = cols[k % 3]
        value = prep_defaults.get(field_key)
        if kind == "number":
            prep[field_key] = col.number_input(T(f"prep.{field_key}"), value=float(value) if value else None,
                                               min_value=0.0, step=1.0, key=f"{prefix}_{field_key}")
        else:
            prep[field_key] = col.text_input(T(f"prep.{field_key}"), value=str(value or ""),
                                             placeholder=T(f"ph.{field_key}"), key=f"{prefix}_{field_key}")
    out["prep"] = {k: v for k, v in prep.items() if v not in (None, "")}
    out["notes"] = st.text_area(T("meta.notes"), value=defaults.get("notes", ""), height=110,
                                placeholder=T("ph.notes"), key=f"{prefix}_notes")
    return out


# ==========================================================================
# Página: analizar
# ==========================================================================
def page_analyze():
    with st.sidebar:
        st.header(T("sb.electrode"))
        mass_mode = st.radio(T("sb.mass_mode"), ["direct", "disc"], format_func=lambda m: T(f"sb.mass_{m}"),
                             help=T("help.mass"), key="mass_mode")
        if mass_mode == "direct":
            default_mass = st.number_input(T("sb.active_mass"), min_value=0.0, value=2.0, step=0.01, format="%.3f",
                                           key="mass_direct")
        else:
            disc = st.number_input(T("sb.disc_mass"), min_value=0.0, value=6.0, step=0.01, format="%.3f", key="disc")
            cu = st.number_input(T("sb.cu_mass"), min_value=0.0, value=3.5, step=0.01, format="%.3f", key="cu")
            frac = st.number_input(T("sb.fraction"), min_value=0.0, max_value=1.0, value=0.80, step=0.01, key="frac")
            default_mass = an.active_mass_mg(disc, cu, frac)
            st.caption(T("sb.active_mass_is", value=fmt(default_mass, 3)))
        area = None
        if st.checkbox(T("sb.areal"), key="use_area"):
            diameter = st.number_input(T("sb.diameter"), min_value=1.0, value=12.0, step=0.5, key="diameter")
            area = an.disc_area_cm2(diameter)
            st.caption(T("sb.area_is", value=fmt(area, 3)))

        st.header(T("sb.calc"))
        method = st.radio(T("sb.method"), ["signo", "direccion"], format_func=lambda m: T(f"method_long.{m}"),
                          help=T("help.method"), key="method")
        ref_cycle = int(st.number_input(T("sb.ref_cycle"), min_value=1, value=2, step=1, key="ref_cycle"))
        with st.expander(T("sb.advanced")):
            hysteresis_mV = st.number_input(T("sb.hysteresis"), min_value=1.0, value=20.0, step=1.0,
                                            help=T("help.hysteresis"), key="hyst")
            scan_rate_mV = st.number_input(T("sb.scan_rate"), min_value=0.001, value=0.1, step=0.05, format="%.3f",
                                           help=T("help.scan_rate"), key="rate")
            window = None
            if st.checkbox(T("sb.window"), key="use_window"):
                c1, c2 = st.columns(2)
                window = (c1.number_input(T("sb.e_min"), value=0.01, step=0.01, format="%.3f", key="wmin"),
                          c2.number_input(T("sb.e_max"), value=1.0, step=0.05, format="%.3f", key="wmax"))
            auto_sign = st.checkbox(T("sb.auto_sign"), value=True, key="auto_sign")

        st.header(T("sb.plots"))
        ramp = st.selectbox(T("sb.ramp"), list(colors.RAMPS), format_func=lambda r: T(f"ramp.{r}"), key="ramp")
        darkest_first = st.checkbox(T("sb.darkest_first"), key="darkest_first")
        show_peaks = st.checkbox(T("sb.show_peaks"), value=True, key="show_peaks")
        peak_labels = st.checkbox(T("sb.peak_labels"), value=True, key="peak_labels")
        show_edge = st.checkbox(T("sb.show_edge"), value=False, key="show_edge", help=T("help.edge"))

    st.title(T("app.title"))
    st.write(T("app.intro"))

    uploads = st.file_uploader(T("upload.label"), type=FILE_TYPES, accept_multiple_files=True, key="uploads")
    files = list(uploads or [])
    if not files and EXAMPLE_FILE.exists() and st.toggle(T("upload.example"), key="use_example"):
        files = [_LocalFile(EXAMPLE_FILE)]
    if not files:
        st.info(T("upload.hint"))
        with st.expander(T("app.how")):
            st.markdown(T("doc.method"))
        return

    names, seen = [], {}
    for f in files:
        count = seen.get(f.name, 0)
        seen[f.name] = count + 1
        names.append(f.name if count == 0 else f"{f.name} ({count + 1})")

    # Masas
    st.subheader(T("mass.title"))
    mass_col = T("mass.col")
    mass_table = pd.DataFrame({T("mass.file"): names, mass_col: [round(default_mass, 4)] * len(names)})
    mass_table = st.data_editor(
        mass_table, hide_index=True, disabled=[T("mass.file")], use_container_width=True,
        column_config={mass_col: st.column_config.NumberColumn(min_value=0.0, step=0.001, format="%.3f")},
        key="masses_" + lang + "|".join(names) + f"_{default_mass:.4f}",
    )
    masses = dict(zip(names, mass_table[mass_col]))

    # Ventanas de picos
    with st.expander(T("pw.title"), expanded=False):
        st.caption(T("pw.help"))
        windows = peak_window_editor()
        c1, c2 = st.columns(2)
        use_auto = c1.checkbox(T("pw.auto"), value=False, key="auto_peaks", help=T("help.auto"))
        prominence = c2.slider(T("pw.prominence"), 1, 30, 5, key="prominence", disabled=not use_auto) / 100
        anodic_names = [w.name for w in windows if w.kind == an.ANODIC]
        cathodic_names = [w.name for w in windows if w.kind == an.CATHODIC]
        dep_pair = None
        if anodic_names and cathodic_names:
            c1, c2 = st.columns(2)
            a_name = c1.selectbox(T("pw.dep_anodic"), anodic_names, key="dep_a")
            c_default = 1 if len(cathodic_names) > 1 else 0
            c_name = c2.selectbox(T("pw.dep_cathodic"), cathodic_names, index=c_default, key="dep_c")
            dep_pair = (a_name, c_name)

    results, items = [], []
    for k, (f, label) in enumerate(zip(files, names)):
        st.divider()
        st.header(label)
        try:
            table = parse_table(f.getvalue(), f.name)
        except CvcapError as exc:
            st.error(T("err.read", msg=err_text(exc)))
            continue
        except Exception as exc:  # noqa: BLE001
            st.error(T("err.unexpected", msg=str(exc)))
            continue

        detected = cvio.detect_columns(table)
        missing = "potential" not in detected or "current" not in detected
        with st.expander(T("cols.title"), expanded=missing):
            options = [NONE] + [str(c) for c in table.columns]
            mapping = {}
            cols = st.columns(4)
            for j, role in enumerate(["potential", "current", "time", "scan"]):
                default = detected.get(role)
                index = options.index(str(default)) if default is not None and str(default) in options else 0
                choice = cols[j].selectbox(T(f"role.{role}"), options, index=index, key=f"{label}_{role}",
                                           format_func=lambda o: T("cols.none") if o == NONE else o)
                if choice != NONE:
                    mapping[role] = choice
            for role in ("index", "q_plus", "q_minus"):
                if role in detected:
                    mapping[role] = detected[role]
            st.dataframe(table.head(8), use_container_width=True)

        try:
            cv = cvio.to_cvdata(table, mapping, source=label)
            mass = masses.get(label)
            res = an.analyze(cv, mass_mg=mass if mass and mass > 0 else None, area_cm2=area,
                             reference_cycle=ref_cycle, hysteresis=hysteresis_mV / 1000.0,
                             scan_rate_V_s=scan_rate_mV / 1000.0, window=window, auto_sign=auto_sign,
                             name=label, method=method)
        except CvcapError as exc:
            st.error(err_text(exc))
            continue
        peaks_df = compute_peaks(res, windows, use_auto, prominence)
        results.append(res)
        items.append(report.item_from_result(res, label=label, peaks=peaks_df))

        for note in res.notes_text(lang):
            st.caption(f"ℹ️ {note}")

        cyc = res.cycles
        has_mass = "cap_delit" in cyc.columns
        complete = cyc[cyc["q_delit"].notna()]
        m1, m2, m3, m4 = st.columns(4)
        m1.metric(T("metric.ce1"), fmt(cyc["ce"].iloc[0], 1, " %"))
        if has_mass:
            m2.metric(T("metric.delit1"), fmt(cyc["cap_delit"].iloc[0], 1, " mAh/g"))
            if not complete.empty:
                m3.metric(T("metric.delit_n", n=int(complete["cycle"].iloc[-1])),
                          fmt(complete["cap_delit"].iloc[-1], 1, " mAh/g"))
        else:
            m2.metric(T("metric.delit1"), fmt(cyc["mah_delit"].iloc[0], 4, " mAh"))
        if not complete.empty:
            m4.metric(T("metric.ret_last"), fmt(complete["ret"].iloc[-1], 1, " %"))

        tabs = st.tabs([T("tab.plots"), T("tab.peaks"), T("tab.cycles"), T("tab.segments"), T("tab.save")])
        with tabs[0]:
            st.plotly_chart(cv_figure(res.cv.potential_V, res.current_A, res.point_cycle, peaks_df, ramp,
                                      darkest_first, show_peaks, peak_labels, T("plot.cv"), show_edge),
                            use_container_width=True)
            fig_cap, fig_ce = capacity_figures(cyc)
            c1, c2 = st.columns(2)
            c1.plotly_chart(fig_cap, use_container_width=True)
            c2.plotly_chart(fig_ce, use_container_width=True)
        with tabs[1]:
            if peaks_df.empty:
                st.info(T("pk.none"))
            else:
                long, pivot = peaks_tables(peaks_df, res.reference_cycle)
                st.markdown(f"**{T('pk.pivot_title')}**")
                st.dataframe(pivot, use_container_width=True)
                if dep_pair:
                    sep = pk.peak_separation(peaks_df, *dep_pair)
                    if not sep.empty:
                        st.markdown(f"**{T('pk.dep_title', a=dep_pair[0], c=dep_pair[1])}**")
                        st.dataframe(pd.DataFrame({
                            T("col.cycle"): sep["cycle"].astype(int),
                            T("pk.e_a"): sep["e_a"], T("pk.e_c"): sep["e_c"], T("pk.dep"): sep["dep"],
                        }), hide_index=True, use_container_width=True)
                st.markdown(f"**{T('pk.all_title')}**")
                st.dataframe(long, hide_index=True, use_container_width=True)
                st.plotly_chart(peak_trend_figure(peaks_df), use_container_width=True)
        with tabs[2]:
            st.dataframe(res.cycles_table(lang), hide_index=True, use_container_width=True)
        with tabs[3]:
            st.dataframe(res.segments_table(lang), hide_index=True, use_container_width=True)
            nova = res.nova_table(lang)
            if nova is not None:
                st.markdown(f"**{T('nova.title')}**")
                st.dataframe(nova, hide_index=True, use_container_width=True)
        with tabs[4]:
            save_section(res, label, k, peaks_df, windows)

    if not results:
        return

    st.divider()
    st.header(T("summary.title"))
    st.dataframe(report.summary_table(results, lang), hide_index=True, use_container_width=True)
    if len(results) > 1:
        st.plotly_chart(compare_figure([(r.name, r.cycles) for r in results], "cap"), use_container_width=True)

    st.subheader(T("dl.title"))
    unit = st.selectbox(T("dl.origin_unit"), list(CURRENT_UNIT_LABELS), format_func=CURRENT_UNIT_LABELS.get,
                        key="origin_unit")
    c1, c2, c3 = st.columns(3)
    c1.download_button(T("dl.origin"), data=report.origin_workbook(items, lang, unit),
                       file_name="cv_origin.xlsx", use_container_width=True, help=T("help.origin"),
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    c2.download_button(T("dl.excel"), data=report.results_to_excel(results, lang), file_name="cv_results.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                       use_container_width=True)
    c3.download_button(T("dl.csv"), data=report.results_to_csv(results, lang), file_name="cv_cycles.csv",
                       mime="text/csv", use_container_width=True)
    with st.expander(T("app.how")):
        st.markdown(T("doc.method"))


def peak_window_editor():
    """Editor de ventanas de picos. Las ventanas se guardan con claves internas en la sesión."""
    if "pw_current" not in ss:
        ss["pw_current"] = [w.to_dict() for w in pk.default_windows(lang)]
        ss["pw_lang"] = lang
        ss["pw_ver"] = 0
    if ss.get("pw_lang") != lang:
        previous_defaults = [w.to_dict() for w in pk.default_windows(ss.get("pw_lang", "es"))]
        if ss["pw_current"] == previous_defaults:  # sin cambios del usuario: traducir los nombres
            ss["pw_current"] = [w.to_dict() for w in pk.default_windows(lang)]
        ss["pw_lang"] = lang
        ss["pw_ver"] = ss.get("pw_ver", 0) + 1
    if st.button(T("pw.reset"), key="pw_reset"):
        ss["pw_current"] = [w.to_dict() for w in pk.default_windows(lang)]
        ss["pw_ver"] = ss.get("pw_ver", 0) + 1
    init_key = f"pw_init_{ss['pw_ver']}"
    kind_labels = {an.CATHODIC: T("kind_short.cathodic"), an.ANODIC: T("kind_short.anodic")}
    if init_key not in ss:
        base = pd.DataFrame(ss["pw_current"], columns=["name", "kind", "e_min", "e_max"])
        base["kind"] = base["kind"].map(kind_labels)
        ss[init_key] = base.rename(columns={"name": T("pw.name"), "kind": T("pw.kind"),
                                            "e_min": T("pw.e_min"), "e_max": T("pw.e_max")})
    edited = st.data_editor(
        ss[init_key], num_rows="dynamic", hide_index=True, use_container_width=True, key=f"pw_editor_{ss['pw_ver']}",
        column_config={
            T("pw.kind"): st.column_config.SelectboxColumn(options=list(kind_labels.values()), required=True),
            T("pw.e_min"): st.column_config.NumberColumn(format="%.3f", step=0.01),
            T("pw.e_max"): st.column_config.NumberColumn(format="%.3f", step=0.01),
        },
    )
    back = {v: k for k, v in kind_labels.items()}
    records = [{"name": r[T("pw.name")], "kind": back.get(r[T("pw.kind")]), "e_min": r[T("pw.e_min")],
                "e_max": r[T("pw.e_max")]} for r in edited.to_dict(orient="records")]
    windows = pk.windows_from_records(records)
    ss["pw_current"] = [w.to_dict() for w in windows]
    return windows


def peak_trend_figure(peaks_df: pd.DataFrame):
    fig = go.Figure()
    for j, (name, group) in enumerate(peaks_df.groupby("name", sort=False)):
        group = group.sort_values("cycle")
        fig.add_trace(go.Scatter(x=group["cycle"], y=group["e_peak"], mode="lines+markers", name=str(name),
                                 line=dict(color=colors.categorical(j), width=2), marker=dict(size=9)))
    fig.update_layout(title=T("plot.peak_trend"), height=340, xaxis=dict(title=T("col.cycle"), dtick=1),
                      yaxis_title=T("pk.e"), legend_title_text="", margin=dict(t=50, r=10))
    return fig


def compare_figure(series, what: str):
    fig = go.Figure()
    for j, (label, cycles) in enumerate(series):
        if what == "cap":
            col = "cap_delit" if "cap_delit" in cycles.columns else "mah_delit"
        else:
            col = "ce"
        fig.add_trace(go.Scatter(x=cycles["cycle"], y=cycles[col], mode="lines+markers", name=str(label),
                                 line=dict(color=colors.categorical(j), width=2), marker=dict(size=9)))
    title = T("plot.compare_cap") if what == "cap" else T("plot.compare_ce")
    ytitle = T("axis.capacity_delit") if what == "cap" else T("col.ce")
    fig.update_layout(title=title, height=380, xaxis=dict(title=T("col.cycle"), dtick=1), yaxis_title=ytitle,
                      legend_title_text="", margin=dict(t=50, r=10))
    return fig


def save_section(res, label, index, peaks_df, windows):
    st.caption(T("save.help"))
    defaults = {"name": Path(label).stem, "material": "commercial",
                "prep": ss.get("last_prep") or PREP_DEFAULTS}
    id_default = ss.setdefault(f"id_suggest_{label}", db.next_id(offset=index))
    meta = sample_form(f"save_{label}", defaults, with_id=True, id_default=id_default)
    exists = bool(meta["id"].strip()) and db.exists(meta["id"])
    overwrite = False
    if exists:
        st.warning(T("save.exists", id=meta["id"]))
        overwrite = st.checkbox(T("save.overwrite"), key=f"overwrite_{label}")
    if st.button(T("save.button"), key=f"save_btn_{label}", type="primary"):
        try:
            rec = record_from_result(res, meta["id"], meta, peaks=peaks_df,
                                     peak_windows=[w.to_dict() for w in windows])
            db.save(rec, overwrite=overwrite)
            ss["last_prep"] = meta["prep"]
            st.success(T("save.ok", id=rec.id))
        except CvcapError as exc:
            st.error(err_text(exc))


# ==========================================================================
# Página: base de datos
# ==========================================================================
def page_database():
    with st.sidebar:
        st.header(T("sb.plots"))
        ramp = st.selectbox(T("sb.ramp"), list(colors.RAMPS), format_func=lambda r: T(f"ramp.{r}"), key="ramp_db")
        darkest_first = st.checkbox(T("sb.darkest_first"), key="darkest_first_db")
        show_peaks = st.checkbox(T("sb.show_peaks"), value=True, key="show_peaks_db")
        peak_labels = st.checkbox(T("sb.peak_labels"), value=True, key="peak_labels_db")
        show_edge = st.checkbox(T("sb.show_edge"), value=False, key="show_edge_db", help=T("help.edge"))

    st.title(T("db.title"))
    st.caption(T("db.location", n=db.count(), path=str(db.path)))
    st.info(T("db.persistence"))

    catalog = db.list_samples()
    if catalog.empty:
        st.write(T("db.empty"))
        backup_section(catalog)
        return

    c1, c2 = st.columns([2, 1])
    query = c1.text_input(T("db.search"), key="db_search", placeholder=T("ph.search"))
    materials = c2.multiselect(T("meta.material"), MATERIALS, format_func=lambda m: T(f"material.{m}"),
                               key="db_materials")
    view = catalog
    if query:
        q = query.lower()
        haystack = (view["id"].astype(str) + " " + view["name"].astype(str) + " " + view["batch"].astype(str) + " "
                    + view["notes"].astype(str) + " " + view["prep"].astype(str)).str.lower()
        view = view[haystack.str.contains(q, regex=False)]
    if materials:
        view = view[view["material"].isin(materials)]
    shown = ["id", "name", "material", "batch", "measured_on", "mass_mg", "n_cycles", "ce1", "ce_mean",
             "cap_delit1", "cap_delit_last", "ret_last", "notes", "updated_at"]
    st.dataframe(report.localize_catalog(view[shown], lang), hide_index=True, use_container_width=True)

    ids = view["id"].tolist()
    names = dict(zip(catalog["id"], catalog["name"]))
    tab_detail, tab_compare, tab_backup = st.tabs([T("db.tab_detail"), T("db.tab_compare"), T("db.tab_backup")])

    with tab_detail:
        if not ids:
            st.write(T("db.no_match"))
        else:
            sid = st.selectbox(T("db.select"), ids, format_func=lambda i: f"{i} — {names.get(i) or ''}",
                               key="db_selected")
            detail_section(sid, ramp, darkest_first, show_peaks, peak_labels, show_edge)

    with tab_compare:
        chosen = st.multiselect(T("db.compare_select"), catalog["id"].tolist(),
                                format_func=lambda i: f"{i} — {names.get(i) or ''}", key="db_compare")
        if chosen:
            records = [db.get(i) for i in chosen]
            series = [(r.id, r.cycles) for r in records if not r.cycles.empty]
            c1, c2 = st.columns(2)
            c1.plotly_chart(compare_figure(series, "cap"), use_container_width=True)
            c2.plotly_chart(compare_figure(series, "ce"), use_container_width=True)
            rows = []
            for r in records:
                row = {T("meta.id"): r.id, T("meta.name"): r.name}
                row.update(an.localize_summary(r.summary, lang))
                rows.append(row)
            st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
            unit = st.selectbox(T("dl.origin_unit"), list(CURRENT_UNIT_LABELS), format_func=CURRENT_UNIT_LABELS.get,
                                key="origin_unit_cmp")
            st.download_button(T("dl.origin"), data=report.origin_workbook(
                [report.item_from_record(r) for r in records], lang, unit), file_name="cv_origin_compare.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", help=T("help.origin"))

    with tab_backup:
        backup_section(catalog)


def detail_section(sid, ramp, darkest_first, show_peaks, peak_labels, show_edge):
    try:
        rec = db.get(sid)
    except CvcapError as exc:
        st.error(err_text(exc))
        return
    st.caption(T("db.dates", created=rec.created_at, updated=rec.updated_at, file=rec.source_file,
                 method=T(f"method.{rec.method}")))
    m1, m2, m3, m4 = st.columns(4)
    s = rec.summary
    m1.metric(T("meta.mass_mg"), fmt(rec.mass_mg, 3))
    m2.metric(T("metric.ce1"), fmt(s.get("ce1"), 1, " %"))
    m3.metric(T("metric.delit1"), fmt(s.get("cap_delit1"), 1, " mAh/g"))
    m4.metric(T("metric.ret_last"), fmt(s.get("ret_last"), 1, " %"))

    curve = rec.curve
    if curve:
        st.plotly_chart(cv_figure(curve["potential_V"], curve["current_A"], curve["point_cycle"], rec.peaks, ramp,
                                  darkest_first, show_peaks, peak_labels, f"{rec.id} — {T('plot.cv')}", show_edge),
                        use_container_width=True)
    if not rec.cycles.empty:
        fig_cap, fig_ce = capacity_figures(rec.cycles)
        c1, c2 = st.columns(2)
        c1.plotly_chart(fig_cap, use_container_width=True)
        c2.plotly_chart(fig_ce, use_container_width=True)
        st.dataframe(an.localize_cycles(rec.cycles, rec.cycle_notes, lang), hide_index=True,
                     use_container_width=True)
    if rec.peaks is not None and not rec.peaks.empty:
        long, pivot = peaks_tables(rec.peaks, int(rec.summary.get("ref_cycle", 2)))
        st.markdown(f"**{T('pk.pivot_title')}**")
        st.dataframe(pivot, use_container_width=True)
        with st.expander(T("pk.all_title")):
            st.dataframe(long, hide_index=True, use_container_width=True)

    with st.expander(T("db.edit"), expanded=False):
        meta = sample_form(f"edit_{sid}", {"name": rec.name, "material": rec.material, "batch": rec.batch,
                                           "measured_on": rec.measured_on, "prep": rec.prep, "notes": rec.notes})
        if st.button(T("db.save_changes"), key=f"upd_{sid}", type="primary"):
            try:
                db.update_metadata(sid, **meta)
                st.success(T("db.updated", id=sid))
            except CvcapError as exc:
                st.error(err_text(exc))

    c1, c2 = st.columns(2)
    unit = c1.selectbox(T("dl.origin_unit"), list(CURRENT_UNIT_LABELS), format_func=CURRENT_UNIT_LABELS.get,
                        key=f"origin_unit_{sid}")
    c1.download_button(T("dl.origin"), data=report.origin_workbook([report.item_from_record(rec)], lang, unit),
                       file_name=f"{sid}_origin.xlsx", help=T("help.origin"),
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    with c2:
        confirm = st.checkbox(T("db.delete_confirm", id=sid), key=f"del_ok_{sid}")
        if st.button(T("db.delete"), key=f"del_{sid}", disabled=not confirm):
            db.delete(sid)
            st.success(T("db.deleted", id=sid))
            st.rerun()


def backup_section(catalog: pd.DataFrame):
    st.markdown(f"**{T('db.backup_title')}**")
    st.caption(T("db.backup_help"))
    c1, c2 = st.columns(2)
    c1.download_button(T("db.download_db"), data=db.export_bytes(), file_name="cvcap_backup.sqlite",
                       mime="application/octet-stream", use_container_width=True)
    if not catalog.empty:
        c2.download_button(T("db.download_catalog"), data=report.catalog_to_excel(catalog, lang),
                           file_name="cvcap_catalog.xlsx", use_container_width=True,
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    st.markdown(f"**{T('db.restore_title')}**")
    upload = st.file_uploader(T("db.restore_label"), type=["sqlite", "db"], key="restore_upload")
    overwrite = st.checkbox(T("db.restore_overwrite"), key="restore_overwrite")
    if upload is not None and st.button(T("db.restore_button"), key="restore_btn"):
        try:
            added, skipped = db.import_bytes(upload.getvalue(), overwrite=overwrite)
            st.success(T("db.restored", added=added, skipped=skipped))
        except CvcapError as exc:
            st.error(err_text(exc))


# --------------------------------------------------------------------------
if page == "analyze":
    page_analyze()
else:
    page_database()
with st.sidebar:
    st.caption(f"cvcap v{__version__}")
