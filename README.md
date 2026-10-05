# CV → Capacidad (NOVA / Metrohm Autolab)

Aplicación web y librería en Python para calcular, a partir de una **voltametría cíclica** exportada de **NOVA**:

- capacidad de **litiación** y **delitiación** por ciclo (C, mAh, mAh/g y, opcionalmente, mAh/cm²)
- **eficiencia coulómbica** por ciclo
- **capacidad irreversible** del primer ciclo
- **retención** respecto a un ciclo de referencia

Está pensada para ánodos de grafito en semicelda frente a Li, pero sirve para cualquier material de intercalación medido por CV.

---

## Formatos admitidos

| Formato | Detalles |
|---|---|
| `.txt`, `.dat`, `.asc` (ASCII de NOVA) | separador `;`, tabulador, `,` o espacios; decimal con coma o punto; UTF-8, UTF-16 o Windows-1252 |
| `.csv`, `.tsv` | igual que arriba |
| `.xlsx`, `.xlsm`, `.xls` | se elige automáticamente la hoja que contiene potencial y corriente |

Las columnas se reconocen por su nombre (`Potential applied (V)`, `WE(1).Current (A)`, `Time (s)`, `Scan`, `Index`, `Q+`, `Q-`…). Las unidades entre paréntesis (mA, µA, mV, min…) se convierten a SI. Si la detección falla, la app permite elegir las columnas a mano.

> El formato nativo `.nox` de NOVA es binario: hay que **exportar** los datos.
> En NOVA: selecciona el comando *CV staircase* → icono de tabla de datos → exportar (ASCII o Excel), o arrastra el comando *Export ASCII data* sobre la CV.

**Importante:** NOVA a veces exporta las filas ordenadas por potencial y no por tiempo. El programa lo detecta y las **reordena por tiempo** (o por *Index*) antes de analizar.

---

## Cómo se calcula

1. Se ordenan los datos en el tiempo.
2. Se detectan los vértices del barrido (algoritmo de *zigzag* con histéresis de 20 mV, robusto frente al ruido).
3. Cada tramo entre vértices es un semiciclo: **catódico** (litiación + SEI) o **anódico** (delitiación). Un ciclo es un catódico seguido de un anódico; un barrido anódico inicial no forma ciclo. Si la CV empieza en el OCP, el primer barrido catódico va del OCP a 0,01 V.
4. La carga se integra en el tiempo con la regla del trapecio, `Q = ∫ I dt` (o `∫ I dE / v` si no hay columna de tiempo).
5. Reparto de la carga en cada ciclo:
   - **Por signo de corriente (por defecto):** litiación = toda la corriente negativa del ciclo; delitiación = toda la positiva. Es lo correcto para el grafito, que **sigue litiándose al principio del barrido anódico** (corriente todavía negativa entre 0,01 y ~0,13 V). Equivale a las columnas `Q+`/`Q−` que calcula NOVA.
   - **Por dirección de barrido:** carga neta de cada barrido. Infravalora la eficiencia coulómbica en grafito.
6. Fórmulas:
   - Capacidad específica (mAh/g) = |Q| (C) / 3,6 / masa activa (g)
   - Masa activa = (masa del disco − masa del Cu) × fracción activa (p. ej. 0,80)
   - Eficiencia coulómbica (%) = Q delitiación / Q litiación × 100
   - Retención (%) = C delitiación ciclo n / C delitiación ciclo de referencia × 100

**Validación:** si el archivo trae las columnas `Q+` y `Q-` de NOVA, la app compara la carga total integrada con la de NOVA (pestaña *Segmentos y comprobación*). Con datos reales de un grafito comercial la diferencia es inferior al 0,001 %.

---

## Publicarla online (gratis) con GitHub + Streamlit Community Cloud

1. **Crea un repositorio en GitHub** (por ejemplo `nova-cv-capacity`) y sube todos los archivos de esta carpeta:
   ```bash
   git init
   git add .
   git commit -m "Primera versión"
   git branch -M main
   git remote add origin https://github.com/TU_USUARIO/nova-cv-capacity.git
   git push -u origin main
   ```
   (También puedes arrastrar los archivos en la web de GitHub: *Add file → Upload files*.)
2. Entra en **https://share.streamlit.io** con tu cuenta de GitHub.
3. Pulsa **Create app → Deploy a public app from GitHub**, elige el repositorio, la rama `main` y el archivo **`app.py`**.
4. En *Advanced settings* elige Python 3.11 o 3.12 y pulsa **Deploy**. En unos minutos tendrás una dirección del tipo `https://TU-APP.streamlit.app`.

Cada vez que hagas `git push`, la app se actualiza sola.

> **Privacidad:** en Streamlit Community Cloud la app puede ser pública o privada (solo para quien invites). Los archivos que se suben se procesan en memoria y no se guardan.

---

## Uso en local

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

### Línea de comandos

```bash
python -m cvcap datos_cv.txt --masa-activa 1.6
python -m cvcap muestra1.txt muestra2.xlsx --masa-disco 6.2 --masa-cu 4.1 --fraccion 0.8 \
       --diametro 12 --salida resultados.xlsx
```

Opciones: `--metodo signo|direccion`, `--ciclo-ref 2`, `--ventana 0.01 1.0`, `--velocidad 0.1` (mV/s, solo si no hay tiempo), `--histeresis 20` (mV).

### Desde Python

```python
from cvcap import read_nova, analyze

cv = read_nova("datos_cv.txt")
res = analyze(cv, mass_mg=1.6, area_cm2=1.131)
print(res.cycles)       # tabla por ciclo
print(res.summary)      # indicadores principales
print(res.nova_check)   # comparación con Q+/Q− de NOVA
```

---

## Tests

```bash
pip install pytest
pytest -q                 # o: python -m unittest discover -s tests
```

Los tests comprueban la lectura de todos los formatos (separadores, decimales, codificaciones, Excel, unidades, filas desordenadas) y el cálculo con CV sintéticas de carga conocida. GitHub Actions los ejecuta en cada `push` (`.github/workflows/tests.yml`).

## Estructura

```
app.py                  interfaz web (Streamlit)
cvcap/io.py             lectura de archivos de NOVA
cvcap/analysis.py       segmentación, integración y métricas
cvcap/report.py         tablas resumen y exportación Excel/CSV
cvcap/cli.py            línea de comandos
examples/               archivo de ejemplo (datos simulados) y su generador
tests/                  tests unitarios
```

## Limitaciones

- La capacidad obtenida por CV depende de la velocidad de barrido y suele ser menor que la de un ciclado galvanostático lento. Úsala para comparar muestras medidas con el mismo protocolo.
- Si la CV no llega a litiar el grafito por completo (barridos rápidos), la capacidad sale infravalorada.
- La corriente capacitiva (doble capa) se incluye en la integral; a velocidades lentas su contribución es pequeña.

## Licencia

MIT
