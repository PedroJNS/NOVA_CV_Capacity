"""Textos de la aplicación en español e inglés.

Uso::

    from cvcap.i18n import t
    t("col.ce", "en")              # 'Coulombic efficiency (%)'
    t("cycle_n", "es", n=2)        # 'Ciclo 2'

Los avisos y errores se guardan como :class:`Note` / :class:`CvcapError` (código +
parámetros) y se traducen al mostrarlos, de modo que el mismo resultado sirve en
los dos idiomas.
"""
from __future__ import annotations

from typing import Dict

LANGUAGES = ("es", "en")

TEXTS: Dict[str, Dict[str, str]] = {"es": {}, "en": {}}


def _add(key: str, es: str, en: str) -> None:
    TEXTS["es"][key] = es
    TEXTS["en"][key] = en


# --------------------------------------------------------------------------
# Generales
# --------------------------------------------------------------------------
_add("yes", "sí", "yes")
_add("no", "no", "no")
_add("cycle_n", "Ciclo {n}", "Cycle {n}")
_add("no_cycle", "Fuera de ciclo", "Outside cycles")
_add("kind.cathodic", "Catódico (litiación)", "Cathodic (lithiation)")
_add("kind.anodic", "Anódico (delitiación)", "Anodic (delithiation)")
_add("kind_short.cathodic", "Catódico", "Cathodic")
_add("kind_short.anodic", "Anódico", "Anodic")
_add("method.signo", "por signo de corriente", "by current sign")
_add("method.direccion", "por dirección de barrido", "by sweep direction")
_add("method_long.signo", "Por signo de corriente (recomendado)", "By current sign (recommended)")
_add("method_long.direccion", "Por dirección de barrido", "By sweep direction")
_add("role.potential", "Potencial", "Potential")
_add("role.current", "Corriente", "Current")
_add("role.time", "Tiempo", "Time")
_add("role.scan", "Scan", "Scan")
_add("role.index", "Índice", "Index")
_add("role.q_plus", "Q+ (NOVA)", "Q+ (NOVA)")
_add("role.q_minus", "Q− (NOVA)", "Q− (NOVA)")
for _k, _es, _en in [
    ("commercial", "Grafito comercial", "Commercial graphite"),
    ("spent", "Grafito gastado", "Spent graphite"),
    ("recycled", "Grafito reciclado", "Recycled graphite"),
    ("other", "Otro", "Other"),
]:
    _add(f"material.{_k}", _es, _en)
for _k, _es, _en in [
    ("blues", "Azules", "Blues"), ("reds", "Rojos", "Reds"), ("greens", "Verdes", "Greens"),
    ("purples", "Violetas", "Purples"), ("oranges", "Naranjas", "Oranges"), ("greys", "Grises", "Greys"),
]:
    _add(f"ramp.{_k}", _es, _en)

# --------------------------------------------------------------------------
# Tablas de resultados
# --------------------------------------------------------------------------
for _k, _es, _en in [
    ("cycle", "Ciclo", "Cycle"),
    ("q_lit", "Q litiación (C)", "Q lithiation (C)"),
    ("q_delit", "Q delitiación (C)", "Q delithiation (C)"),
    ("cap_lit", "Capacidad litiación (mAh/g)", "Lithiation capacity (mAh/g)"),
    ("cap_delit", "Capacidad delitiación (mAh/g)", "Delithiation capacity (mAh/g)"),
    ("mah_lit", "Capacidad litiación (mAh)", "Lithiation capacity (mAh)"),
    ("mah_delit", "Capacidad delitiación (mAh)", "Delithiation capacity (mAh)"),
    ("areal_delit", "Capacidad delitiación (mAh/cm²)", "Delithiation capacity (mAh/cm²)"),
    ("ce", "Eficiencia coulómbica (%)", "Coulombic efficiency (%)"),
    ("irr", "Capacidad irreversible (mAh/g)", "Irreversible capacity (mAh/g)"),
    ("ret", "Retención (%)", "Retention (%)"),
    ("notes", "Notas", "Notes"),
    ("file", "Archivo", "File"),
]:
    _add(f"col.{_k}", _es, _en)
for _k, _es, _en in [
    ("segment", "Segmento", "Segment"), ("kind", "Tipo", "Type"), ("cycle", "Ciclo", "Cycle"),
    ("e_start", "E inicio (V)", "E start (V)"), ("e_end", "E final (V)", "E end (V)"),
    ("points", "Puntos", "Points"), ("duration", "Duración (s)", "Duration (s)"),
    ("rate", "Velocidad (mV/s)", "Scan rate (mV/s)"), ("q_net", "Carga neta (C)", "Net charge (C)"),
    ("q_pos", "Q+ (C)", "Q+ (C)"), ("q_neg", "Q− (C)", "Q− (C)"), ("partial", "Parcial", "Partial"),
]:
    _add(f"seg.{_k}", _es, _en)
for _k, _es, _en in [
    ("file", "Archivo", "File"),
    ("method", "Método", "Method"),
    ("mass_mg", "Masa activa (mg)", "Active mass (mg)"),
    ("n_cycles", "Nº ciclos", "No. of cycles"),
    ("scan_rate", "Velocidad de barrido (mV/s)", "Scan rate (mV/s)"),
    ("ce1", "EC ciclo 1 (%)", "CE cycle 1 (%)"),
    ("ce_mean", "EC media ciclos ≥2 (%)", "Mean CE cycles ≥2 (%)"),
    ("cap_lit1", "Cap. litiación ciclo 1 (mAh/g)", "Lithiation cap. cycle 1 (mAh/g)"),
    ("cap_delit1", "Cap. delitiación ciclo 1 (mAh/g)", "Delithiation cap. cycle 1 (mAh/g)"),
    ("irr1", "Cap. irreversible ciclo 1 (mAh/g)", "Irreversible cap. cycle 1 (mAh/g)"),
    ("cap_delit_last", "Cap. delitiación último ciclo (mAh/g)", "Delithiation cap. last cycle (mAh/g)"),
    ("ret_last", "Retención último ciclo vs ciclo {ref} (%)", "Retention last cycle vs cycle {ref} (%)"),
]:
    _add(f"sum.{_k}", _es, _en)
_add("nova.title", "Comprobación con las columnas Q+ / Q− de NOVA (carga total del archivo)",
     "Check against NOVA's Q+ / Q− columns (total charge in the file)")
_add("nova.quantity", "Magnitud", "Quantity")
_add("nova.nova", "NOVA (Q+ / Q−)", "NOVA (Q+ / Q−)")
_add("nova.ours", "Este programa", "This program")
_add("nova.diff", "Diferencia (%)", "Difference (%)")
_add("nova.pos", "Carga positiva total (C)", "Total positive charge (C)")
_add("nova.neg", "Carga negativa total (C)", "Total negative charge (C)")

# Catálogo de la base de datos
for _k, _es, _en in [
    ("id", "ID", "ID"), ("name", "Nombre", "Name"), ("material", "Material", "Material"),
    ("batch", "Lote", "Batch"), ("measured_on", "Fecha de medida", "Measured on"),
    ("source_file", "Archivo", "File"), ("mass_mg", "Masa activa (mg)", "Active mass (mg)"),
    ("method", "Método", "Method"), ("n_cycles", "Nº ciclos", "No. of cycles"),
    ("ce1", "EC ciclo 1 (%)", "CE cycle 1 (%)"), ("ce_mean", "EC media ≥2 (%)", "Mean CE ≥2 (%)"),
    ("cap_delit1", "Delitiación ciclo 1 (mAh/g)", "Delithiation cycle 1 (mAh/g)"),
    ("cap_delit_last", "Delitiación último (mAh/g)", "Delithiation last (mAh/g)"),
    ("ret_last", "Retención último (%)", "Retention last (%)"), ("notes", "Notas", "Notes"),
    ("updated_at", "Actualizado", "Updated"),
]:
    _add(f"cat.{_k}", _es, _en)

# Metadatos y preparación
for _k, _es, _en in [
    ("id", "ID de la muestra", "Sample ID"), ("name", "Nombre / código", "Name / code"),
    ("material", "Material", "Material"), ("batch", "Lote", "Batch"),
    ("measured_on", "Fecha de medida", "Measurement date"), ("source_file", "Archivo de origen", "Source file"),
    ("mass_mg", "Masa activa (mg)", "Active mass (mg)"), ("area_cm2", "Área (cm²)", "Area (cm²)"),
    ("notes", "Notas", "Notes"),
]:
    _add(f"meta.{_k}", _es, _en)
_add("prep.title", "Preparación del electrodo y de la celda", "Electrode and cell preparation")
for _k, _es, _en, _ph_es, _ph_en in [
    ("composition", "Composición", "Composition", "p. ej. 80:10:10 grafito:NC:PVDF", "e.g. 80:10:10 graphite:CB:PVDF"),
    ("mixing", "Mezclado de la tinta", "Ink mixing", "p. ej. agitador magnético 12 h", "e.g. magnetic stirrer 12 h"),
    ("coating", "Recubrimiento", "Coating", "p. ej. doctor blade, gap 150 µm", "e.g. doctor blade, 150 µm gap"),
    ("thickness_um", "Espesor seco (µm)", "Dry thickness (µm)", "", ""),
    ("pressing", "Prensado / calandrado", "Pressing / calendering", "p. ej. sin prensar", "e.g. not pressed"),
    ("drying", "Secado", "Drying", "p. ej. 120 °C vacío 12 h", "e.g. 120 °C vacuum 12 h"),
    ("separator", "Separador", "Separator", "p. ej. 1× Whatman GF/C", "e.g. 1× Whatman GF/C"),
    ("electrolyte", "Electrolito", "Electrolyte", "p. ej. 1 M LiPF6 EC/DEC/EMC", "e.g. 1 M LiPF6 EC/DEC/EMC"),
    ("electrolyte_ul", "Volumen de electrolito (µL)", "Electrolyte volume (µL)", "", ""),
    ("cell", "Celda", "Cell", "p. ej. CR2025 frente a Li", "e.g. CR2025 vs Li"),
]:
    _add(f"prep.{_k}", _es, _en)
    _add(f"ph.{_k}", _ph_es, _ph_en)
_add("ph.notes", "Observaciones sobre la preparación, el montaje o la medida…",
     "Notes on preparation, assembly or measurement…")
_add("ph.search", "ID, nombre, lote, notas…", "ID, name, batch, notes…")

# --------------------------------------------------------------------------
# Avisos (Note) y errores (CvcapError)
# --------------------------------------------------------------------------
_add("note.sorted_by_time", "Las filas no estaban en orden temporal; se reordenaron por tiempo.",
     "Rows were not in time order; they were sorted by time.")
_add("note.sorted_by_index", "Las filas no estaban en orden; se reordenaron por índice.",
     "Rows were not in order; they were sorted by index.")
_add("note.no_order_col", "Sin columna de tiempo ni de índice: se usa el orden de las filas del archivo.",
     "No time or index column: the row order of the file is used.")
_add("note.dropped_rows", "Se descartaron {n} filas sin datos.", "{n} rows without data were dropped.")
_add("note.unknown_unit", "Unidad '{unit}' de la columna '{col}' no reconocida: se asume SI.",
     "Unit '{unit}' of column '{col}' not recognised: SI assumed.")
_add("note.flipped", "La corriente tenía el convenio de signo contrario (litiación positiva): se ha invertido.",
     "The current used the opposite sign convention (positive lithiation): it has been inverted.")
_add("note.leading_anodic", "El primer barrido es anódico ({e0} → {e1} V): no se incluye en ningún ciclo.",
     "The first sweep is anodic ({e0} → {e1} V): it is not included in any cycle.")
_add("note.no_mass", "Sin masa activa: solo se calculan cargas (C) y capacidades absolutas (mAh).",
     "No active mass: only charges (C) and absolute capacities (mAh) are calculated.")
_add("note.ref_fallback", "Solo hay {n} ciclo(s): la retención se refiere al ciclo {ref}.",
     "Only {n} cycle(s): retention is referred to cycle {ref}.")
_add("note.window", "Integración limitada a {lo}–{hi} V.", "Integration limited to {lo}–{hi} V.")
_add("cnote.partial_lit", "litiación parcial ({e0} → {e1} V)", "partial lithiation ({e0} → {e1} V)")
_add("cnote.partial_delit", "delitiación parcial ({e0} → {e1} V)", "partial delithiation ({e0} → {e1} V)")
_add("cnote.no_anodic", "sin barrido anódico", "no anodic sweep")

_add("err.empty", "El archivo está vacío.", "The file is empty.")
_add("err.no_numeric", "El archivo no contiene columnas numéricas.", "The file has no numeric columns.")
_add("err.no_columns_found", "No se encontraron columnas numéricas. Exporte los datos desde NOVA como ASCII o Excel.",
     "No numeric columns found. Export the data from NOVA as ASCII or Excel.")
_add("err.nox", "Los archivos .nox son el formato interno de NOVA. Exporte los datos como ASCII (.txt) o Excel.",
     ".nox files are NOVA's internal format. Export the data as ASCII (.txt) or Excel.")
_add("err.excel_lib", "Falta la librería para leer este Excel (instale 'openpyxl' para .xlsx o 'xlrd' para .xls).",
     "Missing library to read this Excel file (install 'openpyxl' for .xlsx or 'xlrd' for .xls).")
_add("err.excel_no_data", "Ninguna hoja del Excel contiene datos numéricos.", "No sheet in the Excel file has numeric data.")
_add("err.missing_columns", "No se encontró la columna de {roles}. Columnas disponibles: {available}",
     "Column not found: {roles}. Available columns: {available}")
_add("err.missing_col", "La columna '{col}' no existe en el archivo.", "Column '{col}' does not exist in the file.")
_add("err.too_few", "Hay muy pocos puntos para analizar una CV.", "Too few points to analyse a CV.")
_add("err.source_type", "Fuente no reconocida: use una ruta, bytes o un archivo abierto.",
     "Unrecognised source: use a path, bytes or an open file.")
_add("err.no_time_rate", "El archivo no tiene columna de tiempo: indique la velocidad de barrido.",
     "The file has no time column: please give the scan rate.")
_add("err.no_sweeps", "No se ha podido identificar ningún barrido en los datos.", "No sweep could be identified in the data.")
_add("err.no_cathodic", "No se encontró ningún barrido catódico (litiación) en los datos.",
     "No cathodic (lithiation) sweep was found in the data.")
_add("err.method", "El método debe ser 'signo' o 'direccion'.", "Method must be 'signo' or 'direccion'.")
_add("err.db_exists", "Ya existe una muestra con el ID '{id}'.", "A sample with ID '{id}' already exists.")
_add("err.db_not_found", "No existe ninguna muestra con el ID '{id}'.", "There is no sample with ID '{id}'.")
_add("err.db_bad_id", "ID no válido: use letras, números, espacios, '-', '_', '.' o '/' (máx. 64 caracteres).",
     "Invalid ID: use letters, numbers, spaces, '-', '_', '.' or '/' (max. 64 characters).")
_add("err.db_invalid", "El archivo no es una base de datos de esta aplicación.", "The file is not a database of this app.")
_add("err.read", "No se pudo leer el archivo: {msg}", "The file could not be read: {msg}")
_add("err.unexpected", "Error inesperado: {msg}", "Unexpected error: {msg}")

# --------------------------------------------------------------------------
# Picos
# --------------------------------------------------------------------------
_add("peak.sei", "SEI", "SEI")
_add("peak.lithiation", "Litiación (estadios)", "Lithiation (stages)")
_add("peak.delithiation", "Delitiación", "Delithiation")
_add("pw.title", "Picos: ventanas de búsqueda", "Peaks: search windows")
_add("pw.help", "En cada ciclo se busca el mínimo de corriente (barrido catódico) o el máximo (anódico) dentro de "
     "cada ventana. Añada, edite o borre filas. Si el extremo cae en el borde de la ventana se marca con un "
     "símbolo hueco: amplíe o desplace la ventana.",
     "In each cycle the current minimum (cathodic sweep) or maximum (anodic) is searched within each window. "
     "Add, edit or delete rows. If the extreme falls on the window edge it is shown with an open symbol: "
     "widen or shift the window.")
_add("pw.name", "Nombre", "Name")
_add("pw.kind", "Barrido", "Sweep")
_add("pw.e_min", "E mín (V)", "E min (V)")
_add("pw.e_max", "E máx (V)", "E max (V)")
_add("pw.reset", "Restablecer ventanas de grafito", "Reset graphite windows")
_add("pw.auto", "Añadir picos detectados automáticamente", "Add automatically detected peaks")
_add("pw.prominence", "Prominencia mínima (% de la corriente máx.)", "Minimum prominence (% of max. current)")
_add("pw.dep_anodic", "ΔEp: pico anódico", "ΔEp: anodic peak")
_add("pw.dep_cathodic", "ΔEp: pico catódico", "ΔEp: cathodic peak")
_add("pk.name", "Pico", "Peak")
_add("pk.kind", "Barrido", "Sweep")
_add("pk.e", "E pico (V)", "Peak E (V)")
_add("pk.i", "I pico (mA)", "Peak I (mA)")
_add("pk.de_ref", "ΔE vs ciclo {ref} (mV)", "ΔE vs cycle {ref} (mV)")
_add("pk.di_ref", "ΔI vs ciclo {ref} (%)", "ΔI vs cycle {ref} (%)")
_add("pk.edge", "En el borde", "On edge")
_add("pk.none", "No se encontraron picos con las ventanas actuales.", "No peaks found with the current windows.")
_add("pk.pivot_title", "Potencial de pico por ciclo (V)", "Peak potential per cycle (V)")
_add("pk.all_title", "Todos los picos", "All peaks")
_add("pk.dep_title", "Separación de picos ΔEp = E({a}) − E({c})", "Peak separation ΔEp = E({a}) − E({c})")
_add("pk.e_a", "E anódico (V)", "Anodic E (V)")
_add("pk.e_c", "E catódico (V)", "Cathodic E (V)")
_add("pk.dep", "ΔEp (mV)", "ΔEp (mV)")
_add("legend.peaks_anodic", "Picos anódicos", "Anodic peaks")
_add("legend.peaks_cathodic", "Picos catódicos", "Cathodic peaks")
_add("legend.lithiation", "Litiación", "Lithiation")
_add("legend.delithiation", "Delitiación", "Delithiation")

# --------------------------------------------------------------------------
# Interfaz
# --------------------------------------------------------------------------
_add("app.title", "Capacidad a partir de voltametría cíclica", "Capacity from cyclic voltammetry")
_add("app.intro", "Sube los archivos de CV exportados desde **NOVA** (ASCII `.txt`/`.csv`/`.dat` o Excel "
     "`.xlsx`/`.xls`). El programa ordena los datos en el tiempo, detecta los barridos y calcula, para cada ciclo, "
     "la capacidad de litiación y delitiación, la eficiencia coulómbica, la retención y los picos.",
     "Upload CV files exported from **NOVA** (ASCII `.txt`/`.csv`/`.dat` or Excel `.xlsx`/`.xls`). The program "
     "sorts the data in time, detects the sweeps and calculates, for each cycle, the lithiation and delithiation "
     "capacity, coulombic efficiency, retention and peaks.")
_add("app.how", "¿Cómo se calcula?", "How is it calculated?")
_add("nav.page", "Sección", "Section")
_add("nav.analyze", "Analizar", "Analyse")
_add("nav.database", "Base de datos", "Database")
_add("upload.label", "Archivos de NOVA", "NOVA files")
_add("upload.example", "Probar con un archivo de ejemplo (datos simulados)", "Try an example file (simulated data)")
_add("upload.hint", "Sube uno o varios archivos para empezar. En NOVA: selecciona el comando de la CV → tabla de datos "
     "→ exportar como ASCII o Excel.",
     "Upload one or more files to start. In NOVA: select the CV command → data table → export as ASCII or Excel.")
_add("sb.electrode", "Electrodo", "Electrode")
_add("sb.mass_mode", "Masa activa", "Active mass")
_add("sb.mass_direct", "Introducir la masa activa", "Enter the active mass")
_add("sb.mass_disc", "Calcular desde el disco", "Calculate from the disc")
_add("sb.active_mass", "Masa activa (mg)", "Active mass (mg)")
_add("sb.disc_mass", "Masa del disco con electrodo (mg)", "Mass of coated disc (mg)")
_add("sb.cu_mass", "Masa de un disco de Cu limpio (mg)", "Mass of a bare Cu disc (mg)")
_add("sb.fraction", "Fracción de material activo", "Active material fraction")
_add("sb.active_mass_is", "Masa activa: **{value} mg**", "Active mass: **{value} mg**")
_add("sb.areal", "Calcular capacidad areal (mAh/cm²)", "Calculate areal capacity (mAh/cm²)")
_add("sb.diameter", "Diámetro del disco (mm)", "Disc diameter (mm)")
_add("sb.area_is", "Área: {value} cm²", "Area: {value} cm²")
_add("sb.calc", "Cálculo", "Calculation")
_add("sb.method", "Reparto de la carga en cada ciclo", "Charge split in each cycle")
_add("sb.ref_cycle", "Ciclo de referencia (retención y picos)", "Reference cycle (retention and peaks)")
_add("sb.advanced", "Opciones avanzadas", "Advanced options")
_add("sb.hysteresis", "Umbral de detección de vértices (mV)", "Vertex detection threshold (mV)")
_add("sb.scan_rate", "Velocidad de barrido (mV/s)", "Scan rate (mV/s)")
_add("sb.window", "Integrar solo dentro de una ventana de potencial", "Integrate only within a potential window")
_add("sb.e_min", "E mín (V)", "E min (V)")
_add("sb.e_max", "E máx (V)", "E max (V)")
_add("sb.auto_sign", "Corregir automáticamente el signo de la corriente", "Automatically correct the current sign")
_add("sb.plots", "Gráficas", "Plots")
_add("sb.ramp", "Color de los ciclos", "Cycle colour")
_add("sb.darkest_first", "Ciclo 1 en el tono más oscuro", "Cycle 1 in the darkest shade")
_add("sb.show_peaks", "Marcar picos en la CV", "Mark peaks on the CV")
_add("sb.peak_labels", "Mostrar el nombre de los picos", "Show peak names")
_add("sb.show_edge", "Mostrar también los extremos en el borde de la ventana", "Also show extremes on the window edge")
_add("help.edge", "Un extremo en el borde de la ventana no es un pico verdadero (se dibuja hueco).",
     "An extreme on the window edge is not a true peak (drawn hollow).")
_add("help.mass", "Masa activa = (masa del disco − masa del Cu) × fracción de material activo.",
     "Active mass = (disc mass − Cu mass) × active material fraction.")
_add("help.method", "Por signo: litiación = toda la corriente negativa del ciclo; delitiación = toda la positiva "
     "(equivale a Q+/Q− de NOVA). Tiene en cuenta que el grafito sigue litiándose al principio del barrido anódico. "
     "Por dirección: carga neta de cada barrido.",
     "By sign: lithiation = all negative current of the cycle; delithiation = all positive current (equivalent to "
     "NOVA's Q+/Q−). It accounts for graphite still lithiating at the start of the anodic sweep. By direction: net "
     "charge of each sweep.")
_add("help.hysteresis", "Cambio mínimo de potencial en sentido contrario para considerar que el barrido ha girado.",
     "Minimum potential change in the opposite direction to consider that the sweep has reversed.")
_add("help.scan_rate", "Solo se usa si el archivo no tiene columna de tiempo.", "Only used if the file has no time column.")
_add("help.auto", "Detecta picos con scipy.signal.find_peaks en cada barrido (nombres C1, C2… / A1, A2…).",
     "Detects peaks with scipy.signal.find_peaks in each sweep (names C1, C2… / A1, A2…).")
_add("help.id", "Identificador único. Se propone uno automático; puede usar el suyo (p. ej. el código del cuaderno).",
     "Unique identifier. An automatic one is suggested; you can use your own (e.g. your notebook code).")
_add("help.origin", "Excel con 3 filas de cabecera (Long Name, Units, Comments) y columnas E/I por ciclo.",
     "Excel with 3 header rows (Long Name, Units, Comments) and E/I columns per cycle.")
_add("mass.title", "Masa activa de cada electrodo", "Active mass of each electrode")
_add("mass.file", "Archivo", "File")
_add("mass.col", "Masa activa (mg)", "Active mass (mg)")
_add("cols.title", "Columnas detectadas", "Detected columns")
_add("cols.none", "(ninguna)", "(none)")
_add("metric.ce1", "Eficiencia coulómbica ciclo 1", "Coulombic efficiency cycle 1")
_add("metric.delit1", "Delitiación ciclo 1", "Delithiation cycle 1")
_add("metric.delit_n", "Delitiación ciclo {n}", "Delithiation cycle {n}")
_add("metric.ret_last", "Retención último ciclo", "Retention last cycle")
_add("tab.plots", "Gráficas", "Plots")
_add("tab.peaks", "Picos", "Peaks")
_add("tab.cycles", "Resultados por ciclo", "Results per cycle")
_add("tab.segments", "Segmentos y comprobación", "Segments and check")
_add("tab.save", "Muestra y guardado", "Sample and save")
_add("plot.cv", "Voltamograma", "Voltammogram")
_add("plot.capacity", "Capacidad por ciclo", "Capacity per cycle")
_add("plot.ce", "Eficiencia coulómbica por ciclo", "Coulombic efficiency per cycle")
_add("plot.peak_trend", "Potencial de pico por ciclo", "Peak potential per cycle")
_add("plot.compare_cap", "Capacidad de delitiación por ciclo", "Delithiation capacity per cycle")
_add("plot.compare_ce", "Eficiencia coulómbica por ciclo", "Coulombic efficiency per cycle")
_add("axis.potential", "Potencial (V vs Li⁺/Li)", "Potential (V vs Li⁺/Li)")
_add("axis.current", "Corriente (mA)", "Current (mA)")
_add("axis.capacity", "Capacidad", "Capacity")
_add("axis.capacity_delit", "Capacidad de delitiación", "Delithiation capacity")
_add("summary.title", "Resumen", "Summary")
_add("dl.title", "Descargas", "Downloads")
_add("dl.origin_unit", "Unidad de corriente en el Excel para Origin", "Current unit in the Origin Excel")
_add("dl.origin", "Excel para OriginLab", "Excel for OriginLab")
_add("dl.excel", "Resultados (Excel)", "Results (Excel)")
_add("dl.csv", "Ciclos (CSV)", "Cycles (CSV)")
_add("save.help", "Guarde el análisis en la base de datos con un ID y las condiciones de preparación.",
     "Save the analysis to the database with an ID and the preparation conditions.")
_add("save.exists", "Ya existe una muestra con el ID {id}.", "A sample with ID {id} already exists.")
_add("save.overwrite", "Sobrescribir la muestra existente", "Overwrite the existing sample")
_add("save.button", "Guardar en la base de datos", "Save to database")
_add("save.ok", "Muestra {id} guardada.", "Sample {id} saved.")
_add("db.title", "Base de datos de muestras", "Sample database")
_add("db.location", "{n} muestra(s) · archivo: {path}", "{n} sample(s) · file: {path}")
_add("db.persistence", "En Streamlit Community Cloud el disco se borra al reiniciar la app. Descargue una copia de "
     "seguridad con regularidad (pestaña «Copia de seguridad») o ejecute la app en local para una base de datos "
     "permanente.",
     "On Streamlit Community Cloud the disk is wiped when the app restarts. Download a backup regularly ("
     "'Backup' tab) or run the app locally for a permanent database.")
_add("db.empty", "Todavía no hay muestras. Guárdelas desde la sección «Analizar» o restaure una copia de seguridad.",
     "No samples yet. Save them from the 'Analyse' section or restore a backup.")
_add("db.search", "Buscar", "Search")
_add("db.no_match", "Ninguna muestra coincide con el filtro.", "No sample matches the filter.")
_add("db.tab_detail", "Detalle de una muestra", "Sample detail")
_add("db.tab_compare", "Comparar muestras", "Compare samples")
_add("db.tab_backup", "Copia de seguridad", "Backup")
_add("db.select", "Muestra", "Sample")
_add("db.compare_select", "Muestras a comparar", "Samples to compare")
_add("db.dates", "Creada: {created} · actualizada: {updated} · archivo: {file} · método: {method}",
     "Created: {created} · updated: {updated} · file: {file} · method: {method}")
_add("db.edit", "Editar datos de la muestra y notas", "Edit sample data and notes")
_add("db.save_changes", "Guardar cambios", "Save changes")
_add("db.updated", "Muestra {id} actualizada.", "Sample {id} updated.")
_add("db.delete_confirm", "Confirmo que quiero borrar {id}", "I confirm I want to delete {id}")
_add("db.delete", "Borrar muestra", "Delete sample")
_add("db.deleted", "Muestra {id} borrada.", "Sample {id} deleted.")
_add("db.backup_title", "Descargar", "Download")
_add("db.backup_help", "La copia (.sqlite) contiene todas las muestras, notas, resultados y curvas. El catálogo "
     "(Excel) es una tabla resumen.",
     "The backup (.sqlite) contains all samples, notes, results and curves. The catalogue (Excel) is a summary table.")
_add("db.download_db", "Copia de seguridad (.sqlite)", "Backup (.sqlite)")
_add("db.download_catalog", "Catálogo (Excel)", "Catalogue (Excel)")
_add("db.restore_title", "Restaurar / importar", "Restore / import")
_add("db.restore_label", "Archivo de copia de seguridad", "Backup file")
_add("db.restore_overwrite", "Sobrescribir las muestras con el mismo ID", "Overwrite samples with the same ID")
_add("db.restore_button", "Importar", "Import")
_add("db.restored", "Importadas: {added} · omitidas (ID ya existente): {skipped}",
     "Imported: {added} · skipped (existing ID): {skipped}")

# --------------------------------------------------------------------------
# Exportaciones
# --------------------------------------------------------------------------
_add("xl.summary", "Resumen", "Summary")
_add("xl.cycles", "Ciclos", "Cycles")
_add("xl.seg", "segm", "segm")
_add("xl.notes", "notas", "notes")
_add("xl.catalog", "Catálogo", "Catalogue")
_add("origin.potential", "Potencial", "Potential")
_add("origin.current", "Corriente", "Current")
_add("origin.specific_current", "Corriente específica", "Specific current")
_add("origin.cap_sheet", "Cap", "Cap")
_add("origin.peaks_sheet", "Picos", "Peaks")
_add("origin.compare_sheet", "Comparación", "Comparison")
_add("origin.info_sheet", "Info", "Info")
_add("origin.cap_lit", "Capacidad de litiación", "Lithiation capacity")
_add("origin.cap_delit", "Capacidad de delitiación", "Delithiation capacity")
_add("origin.ce", "Eficiencia coulómbica", "Coulombic efficiency")
_add("origin.ret", "Retención", "Retention")
_add("origin.irr", "Capacidad irreversible", "Irreversible capacity")
_add("origin.e_peak", "Potencial de pico", "Peak potential")
_add("origin.i_peak", "Corriente de pico", "Peak current")

# --------------------------------------------------------------------------
# Documentación del método
# --------------------------------------------------------------------------
_add("doc.method", """
1. Los datos se ordenan en el tiempo (NOVA a veces exporta ordenado por potencial).
2. Se detectan los vértices del barrido (zigzag con histéresis, 20 mV por defecto).
3. Cada tramo entre vértices es un semiciclo **catódico** (litiación + SEI) o **anódico** (delitiación).
   Un ciclo = catódico + anódico siguiente; un barrido anódico inicial no forma ciclo.
4. Carga: Q = ∫ I dt (regla del trapecio), o ∫ I dE / v si no hay tiempo.
5. **Por signo de corriente** (por defecto): litiación = corriente negativa del ciclo; delitiación = corriente
   positiva. Equivale a Q+/Q− de NOVA y tiene en cuenta que el grafito sigue litiándose al empezar el barrido anódico.
6. Capacidad (mAh/g) = |Q| / 3,6 / masa activa (g) · Eficiencia coulómbica = Q delit / Q lit × 100 ·
   Retención = C delit ciclo n / C delit ciclo de referencia × 100.
7. **Picos**: en cada ciclo, extremo de la corriente suavizada (Savitzky-Golay) dentro de cada ventana;
   se dan su potencial, corriente, desplazamiento respecto al ciclo de referencia y ΔEp entre dos picos.
""", """
1. Data are sorted in time (NOVA sometimes exports sorted by potential).
2. Sweep vertices are detected (zigzag with hysteresis, 20 mV by default).
3. Each stretch between vertices is a **cathodic** half-cycle (lithiation + SEI) or an **anodic** one (delithiation).
   A cycle = cathodic + following anodic; an initial anodic sweep is not a cycle.
4. Charge: Q = ∫ I dt (trapezoidal rule), or ∫ I dE / v if there is no time.
5. **By current sign** (default): lithiation = negative current of the cycle; delithiation = positive current.
   Equivalent to NOVA's Q+/Q−, it accounts for graphite still lithiating at the start of the anodic sweep.
6. Capacity (mAh/g) = |Q| / 3.6 / active mass (g) · Coulombic efficiency = Q delith / Q lith × 100 ·
   Retention = C delith cycle n / C delith reference cycle × 100.
7. **Peaks**: in each cycle, extreme of the smoothed current (Savitzky-Golay) within each window; its potential,
   current, shift vs the reference cycle and ΔEp between two peaks are given.
""")


# --------------------------------------------------------------------------
# API
# --------------------------------------------------------------------------
def fmt_num(value, lang: str = "es", digits: int = 2) -> str:
    text = f"{value:.{digits}f}"
    return text.replace(".", ",") if lang == "es" else text


def t(key: str, lang: str = "es", **params) -> str:
    table = TEXTS.get(lang) or TEXTS["es"]
    text = table.get(key) or TEXTS["es"].get(key) or key
    if not params:
        return text
    try:
        return text.format(**params)
    except (KeyError, IndexError, ValueError):
        return text


class Note:
    """Aviso traducible: código + parámetros."""

    __slots__ = ("code", "params")

    def __init__(self, code: str, **params):
        self.code = code
        self.params = params

    def text(self, lang: str = "es") -> str:
        values = {}
        for key, value in self.params.items():
            if isinstance(value, float):
                values[key] = fmt_num(value, lang)
            elif key == "roles" and isinstance(value, (list, tuple)):
                joiner = " ni de " if lang == "es" else ", "
                values[key] = joiner.join(t(f"role.{r}", lang).lower() for r in value)
            else:
                values[key] = value
        return t(self.code, lang, **values)

    def __eq__(self, other):
        return isinstance(other, Note) and (self.code, self.params) == (other.code, other.params)

    def __repr__(self) -> str:
        return f"Note({self.code!r}, {self.params!r})"

    def __str__(self) -> str:
        return self.text("es")


class CvcapError(ValueError):
    """Error con mensaje traducible."""

    def __init__(self, code: str, **params):
        self.note = Note(code, **params)
        super().__init__(self.note.text("es"))

    @property
    def code(self) -> str:
        return self.note.code

    def localized(self, lang: str = "es") -> str:
        return self.note.text(lang)
