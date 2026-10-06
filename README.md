# CV → Capacidad (NOVA / Metrohm Autolab)

*[English summary below](#english-summary)*

Aplicación web y librería en Python para analizar **voltametrías cíclicas** exportadas de **NOVA**:

- capacidad de **litiación** y **delitiación** por ciclo (C, mAh, mAh/g y mAh/cm²), **eficiencia coulómbica**, **capacidad irreversible** y **retención**;
- **picos** de cada ciclo (potencial, corriente, desplazamiento respecto al ciclo de referencia y ΔEp), marcados en la gráfica;
- **CV con los ciclos diferenciados por color** en degradados de un mismo tono (azules, rojos, verdes, violetas, naranjas o grises);
- **base de datos de muestras** con ID, condiciones de preparación y notas;
- exportación a **Excel listo para OriginLab**, Excel de resultados y CSV;
- interfaz, tablas, avisos, gráficas y exportaciones en **español e inglés**.

Pensada para ánodos de grafito en semicelda frente a Li, sirve para cualquier material de intercalación medido por CV.

---

## Secciones de la app

### Analizar
1. Sube uno o varios archivos exportados de NOVA y escribe la masa activa de cada electrodo.
2. Revisa las **ventanas de picos** (por defecto, para grafito: *SEI* catódico 0,40–1,00 V, *Litiación (estadios)* catódico 0,03–0,25 V y *Delitiación* anódico 0,10–0,50 V). Puedes añadir, editar o borrar ventanas, y activar también la detección automática.
3. Para cada archivo verás:
   - **Gráficas**: la CV coloreada por ciclo, con los picos marcados (▲ anódicos, ▼ catódicos), la capacidad por ciclo y la eficiencia coulómbica.
   - **Picos**: el potencial de pico por ciclo, la tabla completa con ΔE (mV) y ΔI (%) respecto al ciclo de referencia, ΔEp entre los dos picos que elijas y la evolución del potencial de pico.
   - **Resultados por ciclo**, **Segmentos y comprobación** (la integración se compara con las columnas Q+/Q− de NOVA cuando existen).
   - **Muestra y guardado**: ID (automático `S-0001`… o uno propio), nombre, material, lote, fecha, preparación (composición, mezclado, recubrimiento, espesor, prensado, secado, separador, electrolito, volumen, celda) y notas. *Guardar en la base de datos*.
4. **Descargas**: Excel para OriginLab (con la unidad de corriente que elijas: mA, µA, A o A/g), Excel de resultados y CSV.

### Base de datos
- Catálogo de muestras con **búsqueda** (ID, nombre, lote, notas, preparación) y filtro por material.
- **Detalle** de cada muestra: CV con picos, capacidades, tablas, edición de datos y notas, exportación a Origin y borrado.
- **Comparar** varias muestras: capacidad y eficiencia coulómbica por ciclo, resumen y Excel para Origin conjunto.
- **Copia de seguridad**: descarga de la base de datos completa (`.sqlite`) y del catálogo (Excel), y restauración o importación.

> **Persistencia:** en Streamlit Community Cloud el disco se borra cuando la app se reinicia o se vuelve a desplegar. Descarga la copia de seguridad con regularidad y restáurala cuando haga falta, o ejecuta la app en local (la base de datos queda en `data/cvcap.sqlite`, o en la ruta indicada en la variable de entorno `CVCAP_DB_PATH`). Si la app es pública, todos los visitantes comparten la misma base de datos: configúrala como **privada**.

---

## Excel para OriginLab

Cada hoja tiene **tres filas de cabecera** y después los datos:

| Fila | Contenido | Ejemplo |
|---|---|---|
| 1 | Long Name | `Potencial`, `Corriente` |
| 2 | Units | `V`, `mA` |
| 3 | Comments | `S-0001 · Ciclo 2` |

Hojas: `<ID> CV` (pares de columnas E/I, una pareja por ciclo), `<ID> Cap` (ciclo, capacidades, eficiencia coulómbica, retención), `<ID> Picos` (ciclo, E y I de cada pico; los extremos que caen en el borde de la ventana se dejan vacíos), `Comparación` (si hay varias muestras) e `Info` (metadatos, preparación, notas y resumen).

En Origin: *Data → Import from File → Excel*. En el asistente indica que la fila 1 es *Long Name*, la 2 *Units* y la 3 *Comments*. Después selecciona las columnas de un ciclo y usa *Plot → Line*.

---

## Formatos de entrada

| Formato | Detalles |
|---|---|
| `.txt`, `.dat`, `.asc`, `.csv`, `.tsv` | separador `;`, tabulador, `,` o espacios; decimal con coma o punto; UTF-8, UTF-16 o Windows-1252 |
| `.xlsx`, `.xlsm`, `.xls` | se elige automáticamente la hoja que contiene potencial y corriente |

Las columnas se reconocen por su nombre (`Potential applied (V)`, `WE(1).Current (A)`, `Time (s)`, `Scan`, `Index`, `Q+`, `Q-`…) y las unidades (mA, µA, mV, min…) se convierten a SI. Si NOVA exporta las filas ordenadas por potencial, se **reordenan por tiempo**. El formato `.nox` de NOVA es binario: hay que exportar los datos (comando *CV staircase* → tabla de datos → exportar).

---

## Cómo se calcula

1. Los datos se ordenan en el tiempo y se detectan los vértices del barrido (zigzag con histéresis de 20 mV).
2. Cada tramo es un semiciclo **catódico** (litiación + SEI) o **anódico** (delitiación). Un ciclo es un catódico seguido de un anódico; si la CV empieza en el OCP, el primer barrido va del OCP a 0,01 V.
3. La carga se integra en el tiempo, `Q = ∫ I dt` (o `∫ I dE / v` si no hay tiempo).
4. **Por signo de corriente** (por defecto): litiación = toda la corriente negativa del ciclo y delitiación = toda la positiva. Es lo correcto para el grafito, que **sigue litiándose al principio del barrido anódico**. Equivale a las Q+/Q− de NOVA. La alternativa, *por dirección de barrido*, infravalora la eficiencia coulómbica.
5. Capacidad (mAh/g) = |Q| / 3,6 / masa activa (g) · Eficiencia coulómbica = Q delit / Q lit × 100 · Retención = C delit, ciclo n / C delit, ciclo de referencia × 100.
6. **Picos:** la corriente se suaviza (Savitzky-Golay) y en cada ventana se toma el mínimo (catódico) o el máximo (anódico). Si cae en el borde de la ventana, se marca como "en el borde" y se dibuja hueco, porque no es un pico verdadero. La detección automática usa `scipy.signal.find_peaks` con una prominencia mínima.

**Validación:** con datos reales de un grafito comercial, la carga integrada coincide con las columnas Q+/Q− de NOVA con una diferencia inferior al 0,001 %.

Los colores de los ciclos son rampas de un solo tono validadas como escala ordinal (luminosidad monótona y tono más claro con contraste ≥ 2:1 sobre fondo blanco). Las muestras se comparan con una paleta categórica de orden fijo.

---

## Publicarla online (gratis): GitHub + Streamlit Community Cloud

1. Crea un repositorio en GitHub y sube esta carpeta:
   ```bash
   git init && git add . && git commit -m "cvcap v2"
   git branch -M main
   git remote add origin https://github.com/TU_USUARIO/nova-cv-capacity.git
   git push -u origin main
   ```
2. Entra en **https://share.streamlit.io** con tu cuenta de GitHub → **Create app** → elige el repositorio, la rama `main` y el archivo **`app.py`** → **Deploy**.
3. Opcional: en *Settings → Sharing* hazla **privada** e invita solo a tu grupo.

## Uso en local

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

### Línea de comandos

```bash
python -m cvcap datos_cv.txt --masa-activa 2.64 --diametro 12 --origin cv_origin.xlsx
python -m cvcap m1.txt m2.xlsx --masa-disco 6.2 --masa-cu 4.1 --salida resultados.xlsx --idioma en
```

Opciones: `--metodo signo|direccion`, `--ciclo-ref 2`, `--ventana 0.01 1.0`, `--velocidad 0.1` (mV/s), `--histeresis 20` (mV), `--unidad-corriente mA|uA|A|A/g`, `--idioma es|en`.

### Desde Python

```python
from cvcap import read_nova, analyze
from cvcap.peaks import default_windows, window_peaks
from cvcap.report import item_from_result, origin_workbook

cv = read_nova("datos_cv.txt")
res = analyze(cv, mass_mg=2.64)
print(res.cycles_table("es"))
peaks = window_peaks(res, default_windows("es"))
open("origin.xlsx", "wb").write(origin_workbook([item_from_result(res, peaks=peaks)], "es"))
```

## Tests

```bash
pip install pytest && pytest -q
```

Cubren la lectura de todos los formatos, el cálculo con CV de carga conocida, los picos, los colores, la base de datos (guardar, editar, borrar, copia de seguridad y restauración), el Excel para Origin y que todos los textos existan en los dos idiomas. GitHub Actions los ejecuta en cada `push`.

## Estructura

```
app.py              interfaz web (Streamlit): páginas Analizar y Base de datos
cvcap/io.py         lectura de archivos de NOVA
cvcap/analysis.py   segmentación, integración y métricas por ciclo
cvcap/peaks.py      picos por ventanas y detección automática
cvcap/colors.py     degradados por ciclo y paleta categórica
cvcap/db.py         base de datos SQLite de muestras
cvcap/report.py     Excel de resultados, CSV y Excel para OriginLab
cvcap/i18n.py       textos en español e inglés
cvcap/cli.py        línea de comandos
examples/           archivo de ejemplo (datos simulados)
tests/              tests unitarios
```

## Limitaciones

- La capacidad por CV depende de la velocidad de barrido y suele ser menor que la de un galvanostático lento. Úsala para comparar muestras medidas con el mismo protocolo.
- La corriente capacitiva se incluye en la integral (a 0,1 mV/s su contribución es pequeña).

---

## English summary

Web app and Python library to analyse **cyclic voltammetry** exported from Metrohm Autolab **NOVA**: lithiation/delithiation capacity per cycle, coulombic efficiency, irreversible capacity and retention; **peaks** per cycle (named potential windows plus optional automatic detection) marked on the CV; cycles coloured in **single-hue shades** (blues, reds…); a **sample database** with IDs, preparation conditions and notes (backup/restore as `.sqlite`); **OriginLab-ready Excel** (3 header rows: Long Name / Units / Comments; E/I column pairs per cycle); full **Spanish/English** toggle. Deploy for free on Streamlit Community Cloud by pointing it at `app.py`. Note that the Community Cloud disk is wiped on restart: download database backups regularly, or run locally for a persistent database. License: MIT.
