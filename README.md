# ⚡ CV → Capacidad · Voltametrías cíclicas de NOVA (Metrohm Autolab)

[![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://novacvcapacity-wu5q2r84turttxshfwshyj.streamlit.app/)
[![Python](https://img.shields.io/badge/Python-3.9%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
[![Tests](https://github.com/PedroJNS/nova-cv-capacity/actions/workflows/tests.yml/badge.svg)](https://github.com/PedroJNS/nova-cv-capacity/actions)
[![Idioma](https://img.shields.io/badge/Idioma-ES%20%7C%20EN-orange)](#-english-summary)

Aplicación web desarrollada en **Streamlit** y librería en **Python** para el análisis automatizado de **voltametrías cíclicas (CV)** exportadas de **Metrohm Autolab NOVA**. Pensada para **ánodos de grafito en semicelda frente a Li**, sirve para cualquier material de intercalación medido por CV.

> 👉 **[Abrir la aplicación](https://novacvcapacity-wu5q2r84turttxshfwshyj.streamlit.app/)** — sin instalar nada.

<img width="1675" height="622" alt="image" src="https://github.com/user-attachments/assets/d2beb47e-3d6f-4dd6-bd58-ccb6aca71324" />

---

## 🚀 Características principales

- 🔋 **Capacidad por ciclo:** litiación y delitiación en C, mAh, mAh/g y mAh/cm²; eficiencia coulómbica, capacidad irreversible y retención.
- 📍 **Análisis de picos:** potencial, corriente, desplazamiento respecto al ciclo de referencia y ΔEp, marcados directamente en la gráfica.
- 🎨 **CV coloreada por ciclo:** degradados de un solo tono (azules, rojos, verdes, violetas, naranjas o grises).
- 🗃️ **Base de datos de muestras:** ID, condiciones de preparación y notas, con búsqueda, filtros y comparación entre muestras.
- 📊 **Exportación lista para OriginLab:** Excel con cabeceras Long Name / Units / Comments, además de Excel de resultados y CSV.
- 📥 **Carga multiformato:** `.txt`, `.dat`, `.asc`, `.csv`, `.tsv`, `.xlsx`, `.xlsm` y `.xls`.
- ✅ **Validada con datos reales:** la carga integrada coincide con las columnas Q+/Q− de NOVA (diferencia < 0,001 %).
- 🌐 **Bilingüe:** interfaz, tablas, avisos, gráficas y exportaciones en español e inglés.

---

## 🧭 Secciones de la app

### 🔬 Analizar

1. Sube uno o varios archivos exportados de NOVA e indica la **masa activa** de cada electrodo.
2. Revisa las **ventanas de picos**. Por defecto, para grafito:

   | Ventana | Tipo | Rango |
   |---|---|---|
   | SEI | catódico | 0,40–1,00 V |
   | Litiación (estadios) | catódico | 0,03–0,25 V |
   | Delitiación | anódico | 0,10–0,50 V |

   Puedes añadir, editar o borrar ventanas, y activar también la detección automática.

3. Para cada archivo verás:
   - **Gráficas:** CV coloreada por ciclo con los picos marcados (▲ anódicos, ▼ catódicos), capacidad por ciclo y eficiencia coulómbica.
   - **Picos:** potencial de pico por ciclo, tabla completa con ΔE (mV) y ΔI (%) respecto al ciclo de referencia, ΔEp entre los dos picos que elijas y evolución del potencial de pico.
   - **Resultados por ciclo, segmentos y comprobación** (la integración se compara con las columnas Q+/Q− de NOVA cuando existen).
   - **Muestra y guardado:** ID (automático `S-0001`… o uno propio), nombre, material, lote, fecha, preparación (composición, mezclado, recubrimiento, espesor, prensado, secado, separador, electrolito, volumen, celda) y notas.
   - **Descargas:** Excel para OriginLab (corriente en mA, µA, A o A/g), Excel de resultados y CSV.

### 🗃️ Base de datos

- **Catálogo** con búsqueda (ID, nombre, lote, notas, preparación) y filtro por material.
- **Detalle de cada muestra:** CV con picos, capacidades, tablas, edición de datos y notas, exportación a Origin y borrado.
- **Comparar muestras:** capacidad y eficiencia coulómbica por ciclo, resumen y Excel para Origin conjunto.
- **Copia de seguridad:** descarga de la base de datos completa (`.sqlite`) y del catálogo (Excel), con restauración o importación.

> ⚠️ **Persistencia:** en Streamlit Community Cloud el disco se borra cuando la app se reinicia o se vuelve a desplegar. Descarga la copia de seguridad con regularidad y restáurala cuando haga falta, o ejecuta la app en local (la base de datos queda en `data/cvcap.sqlite`, o en la ruta de la variable de entorno `CVCAP_DB_PATH`). Si la app es pública, todos los visitantes comparten la misma base de datos: **configúrala como privada**.

---

## 📊 Excel para OriginLab

Cada hoja tiene tres filas de cabecera y después los datos:

| Fila | Contenido | Ejemplo |
|---|---|---|
| 1 | Long Name | Potencial, Corriente |
| 2 | Units | V, mA |
| 3 | Comments | S-0001 · Ciclo 2 |

**Hojas generadas:**

- `<ID> CV` — pares de columnas E/I, una pareja por ciclo.
- `<ID> Cap` — ciclo, capacidades, eficiencia coulómbica y retención.
- `<ID> Picos` — ciclo, E e I de cada pico (los extremos en el borde de la ventana se dejan vacíos).
- `Comparación` — si hay varias muestras.
- `Info` — metadatos, preparación, notas y resumen.

**En Origin:** *Data → Import from File → Excel*. En el asistente indica que la fila 1 es Long Name, la 2 Units y la 3 Comments. Después selecciona las columnas de un ciclo y usa *Plot → Line*.

---

## 📥 Formatos de entrada

| Formato | Detalles |
|---|---|
| `.txt`, `.dat`, `.asc`, `.csv`, `.tsv` | Separador `;`, tabulador, `,` o espacios; decimal con coma o punto; UTF-8, UTF-16 o Windows-1252 |
| `.xlsx`, `.xlsm`, `.xls` | Se elige automáticamente la hoja que contiene potencial y corriente |

Las columnas se reconocen por su nombre (`Potential applied (V)`, `WE(1).Current (A)`, `Time (s)`, `Scan`, `Index`, `Q+`, `Q-`…) y las unidades (mA, µA, mV, min…) se convierten a SI. Si NOVA exporta las filas ordenadas por potencial, se reordenan por tiempo.

> ℹ️ El formato `.nox` de NOVA es binario: hay que exportar los datos (comando *CV staircase → tabla de datos → exportar*).

---

## 🧮 Cómo se calcula

1. **Segmentación:** los datos se ordenan en el tiempo y se detectan los vértices del barrido (zigzag con histéresis de 20 mV).
2. **Ciclos:** cada tramo es un semiciclo catódico (litiación + SEI) o anódico (delitiación). Un ciclo es un catódico seguido de un anódico; si la CV empieza en el OCP, el primer barrido va del OCP a 0,01 V.
3. **Carga:** se integra en el tiempo, Q = ∫ I dt (o ∫ I dE / v si no hay tiempo).
4. **Criterio por signo de corriente (por defecto):** litiación = toda la corriente negativa del ciclo; delitiación = toda la positiva. Es lo correcto para el grafito, que sigue litiándose al principio del barrido anódico, y equivale a las Q+/Q− de NOVA. La alternativa, por dirección de barrido, infravalora la eficiencia coulómbica.
5. **Métricas:**
   - Capacidad (mAh/g) = |Q| / 3,6 / masa activa (g)
   - Eficiencia coulómbica (%) = Q<sub>delit</sub> / Q<sub>lit</sub> × 100
   - Retención (%) = C<sub>delit, ciclo n</sub> / C<sub>delit, ciclo ref</sub> × 100
6. **Picos:** la corriente se suaviza (Savitzky-Golay) y en cada ventana se toma el mínimo (catódico) o el máximo (anódico). Si cae en el borde de la ventana se marca como «en el borde» y se dibuja hueco, porque no es un pico verdadero. La detección automática usa `scipy.signal.find_peaks` con una prominencia mínima.

🎨 Los colores de los ciclos son rampas de un solo tono validadas como escala ordinal (luminosidad monótona y tono más claro con contraste ≥ 2:1 sobre fondo blanco). Las muestras se comparan con una paleta categórica de orden fijo.

---

## 🗂️ Estructura del proyecto

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

---

## ⚠️ Limitaciones

- La capacidad por CV depende de la velocidad de barrido y suele ser menor que la de un ensayo galvanostático lento. Úsala para **comparar muestras medidas con el mismo protocolo**.
- La corriente capacitiva se incluye en la integral (a 0,1 mV/s su contribución es pequeña).

---

## 📜 Autoría y licencia

Este proyecto ha sido desarrollado y es propiedad intelectual de **Pedro J. Navarrete Segado** (Universidad de Jaén).

Esta aplicación es software libre y se distribuye bajo los términos de la **Licencia Pública General GNU v3.0 (GPL-3.0)**.

- Puedes usar, copiar, modificar y redistribuir este código libremente.
- Cualquier trabajo derivado o copia debe mantener esta misma licencia pública (GPLv3) y reconocer explícitamente la autoría original.
- Consulta el archivo [`LICENSE`](LICENSE) para obtener más detalles.

---

## 🇬🇧 English summary

**CV → Capacity** is a Streamlit web app and Python library to analyse cyclic voltammetry exported from **Metrohm Autolab NOVA**.

- 🔋 Lithiation/delithiation capacity per cycle (C, mAh, mAh/g, mAh/cm²), coulombic efficiency, irreversible capacity and retention.
- 📍 Peaks per cycle (named potential windows plus optional automatic detection), marked on the CV.
- 🎨 Cycles coloured in single-hue shades (blues, reds…).
- 🗃️ Sample database with IDs, preparation conditions and notes (backup/restore as `.sqlite`).
- 📊 OriginLab-ready Excel (3 header rows: Long Name / Units / Comments; E/I column pairs per cycle).
- 🌐 Full Spanish/English toggle.

👉 **[Open the app](https://novacvcapacity-wu5q2r84turttxshfwshyj.streamlit.app/)**, or deploy your own copy for free on Streamlit Community Cloud by pointing it at `app.py`. Note that the Community Cloud disk is wiped on restart: download database backups regularly, or run locally for a persistent database.

Developed by **Pedro J. Navarrete Segado**. Licensed under **GPL-3.0**.
