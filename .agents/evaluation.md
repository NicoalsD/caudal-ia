# Backtest y evaluación offline

Esta guía explica qué mide el backtest de `caudal-ia`, con qué fórmulas, cómo ejecutarlo de forma reproducible y cómo leer el informe. Especificación: [Módulo de IA, sección 9](https://github.com/NicoalsD/caudal-backend/blob/develop/docs/Modulo-IA.md#9-evaluación).

## 1. Qué mide

El backtest responde si el modelo (Chronos) ayuda más que la **estimación simple** (persistencia, sección 6 de la especificación). Recorre una serie diaria, pronostica en cada corte con el contexto disponible hasta ese día y compara contra los días reales que siguen. Modelo y persistencia se evalúan sobre **las mismas ventanas**.

Es offline: no toca la base de datos ni el servicio en ejecución. Los pronósticos reales del servicio usan `POST /v1/forecasts`; este backtest solo sirve para decidir si un modelo merece activarse.

## 2. Ventanas

Para cada corte `k`:

- **Contexto:** todos los días hasta el corte (ventana que crece, *expanding*). Los días sin lectura viajan como `NaN`.
- **Objetivos:** los `h` días siguientes (`h = horizon`). Un objetivo `NaN` no cuenta en las métricas.
- Solo se emiten cortes con horizonte completo dentro de la serie.
- Entre dos cortes consecutivos hay `step` días.
- El primer corte tiene `min_context` días de contexto. Este valor cuenta **días**, no lecturas válidas. Por defecto es `FORECAST_MIN_POINTS` (7).

Implementación: `caudal_ia.evaluation.windows` (`RollingWindowIterator`, patrón Iterator) y `caudal_ia.evaluation.backtest` (`Backtest`, patrón Template Method; `ModelBacktest` aplica cualquier `Forecaster`).

## 3. Persistencia (estimación simple)

Sea `L` el último valor finito del contexto y `d_t` los cambios diarios entre días consecutivos con valor finito (los cambios que cruzan un hueco se ignoran).

```
p50 = L
p10 = min(L, L + Q(0,10; d))
p90 = max(L, L + Q(0,90; d))
```

`Q` es el cuantil lineal (`numpy.quantile`) de los cambios. Para todos los horizontes se usa el mismo rango, como indica la especificación (sección 6.1).

Dos decisiones de implementación, documentadas en `caudal_ia.evaluation.baseline`:

- **Banda que contiene la mediana.** La fórmula sin recorte pondría `L + Q(0,10)` por encima de `L` en una serie que sube de forma constante. Entonces el contrato (`p10 <= p50 <= p90`) reordenaría los valores y cambiaría la mediana. Por eso `p10` se limita a `L` por arriba y `p90` a `L` por abajo.
- **Mínimo de cambios `N = 5`.** Con menos de 5 cambios válidos, los tres valores son `L`, en vez de inventar un rango.

Recorte a la regla del tanque (`[gauge_min, gauge_max]` del backend): no se aplica aquí porque el backtest offline no conoce la regla.

## 4. Métricas

Por horizonte `h = 1..H`, sobre los `n` objetivos finitos (`y_t`, `p10_t`, `p50_t`, `p90_t`). Caso con `n = 0`: todas las métricas son `null`.

| Métrica | Fórmula | Lectura |
|---|---|---|
| MAE | `(1/n) Σ |y_t - p50_t|` | Error medio del p50. Menor es mejor. |
| WQL | `(1/3) Σ_q 2 Σ_t QL_q(y_t, ŷ_t,q) / Σ_t |y_t|`, con `q` en {0,1; 0,5; 0,9} | Calidad de los tres cuantiles a la vez. Menor es mejor. Es `null` si `Σ |y_t| = 0`. |
| Cobertura | `(1/n) #{t : p10_t <= y_t <= p90_t}` | Los límites cuentan como dentro. Meta: entre 70 % y 90 %. |
| Ancho | `(1/n) Σ (p90_t - p10_t)` | Precisión del rango. Con la misma cobertura, más angosto es mejor. |
| Skill | `1 - MAE_modelo,h / MAE_persistencia,h` | Mejora frente a la persistencia. Mayor que 0 significa que el modelo gana. Es `null` si el MAE de persistencia es 0. |

`QL_q(y, ŷ) = q (y - ŷ)` si `y >= ŷ`, y `(1 - q)(ŷ - y)` en otro caso.

## 5. Veredicto

El veredicto mira el **modelo** y sigue la sección 9.3 de la especificación. Se aplica a todos los horizontes:

| Veredicto | Condición |
|---|---|
| `insufficient_evidence` | Algún horizonte tiene menos de `BACKTEST_MIN_EVALUATIONS` (30) pronósticos evaluados. |
| `helps` | Skill mayor que 0 en todos los horizontes **y** cobertura entre `BACKTEST_COVERAGE_MIN` (0,7) y `BACKTEST_COVERAGE_MAX` (0,9) en todos los horizontes. |
| `does_not_help` | Cualquier otro caso. |

"Sostenido" (sección 9.3, punto 1) está por definir en la especificación. Esta implementación lo toma como "en todos los horizontes de la serie evaluada".

## 6. Cómo ejecutarlo

Requisitos: `uv sync` hecho y un `.env` con `IA_SERVICE_TOKEN` (al menos 32 bytes). El CLI lee la configuración igual que el servicio.

```bash
uv sync
cp .env.example .env    # y pon un IA_SERVICE_TOKEN de al menos 32 bytes

# Backtest con el modelo activo (CHRONOS_MODEL_ID). Los pesos deben estar en la caché de Hugging Face.
HF_HUB_OFFLINE=1 uv run python -m caudal_ia.evaluation \
  --input serie.json --output resultado.json --horizon 3 --min-context 7 --step 1

# Solo la estimación simple como modelo (sin cargar Chronos; útil para pruebas).
uv run python -m caudal_ia.evaluation \
  --input serie.json --output resultado.json --persistence-only

# Con datos simulados: el informe queda marcado.
uv run python -m caudal_ia.evaluation \
  --input serie.json --output resultado.json --simulated
```

| Opción | Por defecto | Significado |
|---|---|---|
| `--input` | (obligatoria) | Serie en JSON, ver sección 7. |
| `--output` | (obligatoria) | Informe JSON de salida. |
| `--horizon` | `3` | Días a pronosticar en cada corte (1 a 3 según el módulo). |
| `--min-context` | `FORECAST_MIN_POINTS` (7) | Días mínimos de contexto del primer corte. |
| `--step` | `1` | Días entre cortes consecutivos. |
| `--simulated` | apagado | Marca el informe como datos simulados. |
| `--persistence-only` | apagado | Usa la persistencia como modelo. Con él, el skill es 0. |

La reproducibilidad viene de tres cosas: la misma serie, los mismos pesos de Chronos (`CHRONOS_MODEL_ID` y versión del paquete) y los mismos parámetros. El informe no lleva marcas de tiempo, así que dos corridas idénticas producen el mismo archivo byte a byte. Esto se comprobó con `--persistence-only` y con `autogluon/chronos-2-small`.

Con `HF_HUB_OFFLINE=1` Hugging Face usa solo la caché local, sin intentar descargar pesos. Las pruebas automáticas nunca cargan pesos reales; usan `DeterministicForecaster` (`tests/fakes.py`).

Código de salida: `0` si el informe se escribió; `2` si la serie, los parámetros o la configuración no son válidos. El mensaje de error va a `stderr`.

## 7. Entrada

Mismo formato que `POST /v1/forecasts`:

```json
{
  "timestamps": ["2026-07-01T18:00:00-05:00", "2026-07-02T18:00:00-05:00"],
  "values": [3.0, 2.98]
}
```

- Marcas de tiempo ISO-8601 con zona, estrictamente crecientes, y listas de la misma longitud.
- Valores finitos y de tamaño admisible para el modelo.
- Máximo `MAX_SERIES_POINTS` (2.000) puntos.
- La serie se resume a un valor por día con `RESAMPLE_AGGREGATION` en `SERIES_TIMEZONE`, igual que en el servicio.

## 8. Formato del informe

```json
{
  "model": {"name": "autogluon/chronos-2-small", "version": "2.3.2"},
  "baseline": {"name": "naive-persistence", "version": "1"},
  "parameters": {"horizon": 3, "min_context": 7, "step": 1,
                 "resample_aggregation": "last", "series_timezone": "America/Bogota"},
  "thresholds": {"min_evaluations": 30, "coverage_min": 0.7, "coverage_max": 0.9},
  "simulated_data": true,
  "horizons": [
    {"horizon": 1, "evaluated": 78,
     "model": {"mae": 0.0457, "wql": 0.0150, "coverage": 0.7051, "mean_width": 0.1203},
     "persistence": {"mae": 0.0581, "wql": 0.0178, "coverage": 0.6154, "mean_width": 0.1212},
     "skill": 0.2137}
  ],
  "verdict": "does_not_help"
}
```

El ejemplo muestra solo el horizonte 1; el informe real trae un objeto por horizonte. Las métricas sin datos son `null`. El JSON se escribe con `allow_nan=False`: si aparece un `NaN`, la escritura falla en vez de producir un archivo inválido.

## 9. Datos simulados

Con `--simulated` el informe lleva `"simulated_data": true`. Un informe sobre datos simulados prueba la **integración** (que el backtest corre de punta a punta, con el formato correcto y sin errores), **no la calidad del modelo en el campo**. La especificación pide mostrarlo como "Datos simulados" en la UI y en el informe.

## 10. Pruebas

```bash
uv run pytest tests/evaluation          # ventanas, backtest, métricas, persistencia, informe y CLI
uv run pytest -m chronos                # opcional: prueba de humo con los pesos reales
```
