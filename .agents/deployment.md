# Despliegue de caudal-ia

Guía operativa de la Fase 12. Especificación: [Módulo de IA, sección 12](https://github.com/NicoalsD/caudal-backend/blob/develop/docs/Modulo-IA.md) y [Seguridad](https://github.com/NicoalsD/caudal-backend/blob/develop/docs/Seguridad.md).

La imagen (`Dockerfile`) descarga los pesos de Chronos al construirse, corre como usuario 1000, escucha en el puerto `PORT` (7860 por defecto) y no lleva ningún secreto. El token se pasa siempre como variable o secreto del hosting.

## 1. Hugging Face Spaces (opción inicial)

### 1.1 Crear el Space

1. En Hugging Face, crea un Space con **SDK = Docker** y hardware **CPU**. Verifica en la documentación de Hugging Face la RAM del hardware elegido frente a la tabla de mediciones (sección 5).
2. Sube el repositorio al Space (o sincronízalo desde GitHub). El `Dockerfile` está en la raíz.
3. El `README.md` que lee Hugging Face debe empezar con este bloque (front matter). Hugging Face lo usa para saber en qué puerto escucha la app:

   ```yaml
   ---
   title: caudal-ia
   sdk: docker
   app_port: 7860
   ---
   ```

   Ese bloque se añade solo en el `README.md` del Space, no en el de GitHub, para que GitHub no lo muestre como texto.

### 1.2 Secretos y variables del Space

Configúralos en **Settings** del Space.

| Tipo | Nombre | Obligatorio | Valor |
|---|---|---|---|
| Secreto | `IA_SERVICE_TOKEN` | Sí | Token de servicio de al menos 32 bytes aleatorios. Generación: `python -c "import secrets; print(secrets.token_urlsafe(32))"` |
| Secreto | `IA_SERVICE_TOKEN_PREVIOUS` | No | Solo durante una rotación (sección 3). |
| Variable | `SERIES_TIMEZONE` | No (por defecto `America/Bogota`) | Debe coincidir con la zona horaria del backend (sección 4). |
| Variable | `LOG_LEVEL` | No | `INFO` por defecto. |
| Variable | `API_DOCS_ENABLED` | No | `true` por defecto; `false` oculta Swagger. |
| Variable | `RESAMPLE_AGGREGATION` | No | `last` (por defecto) o `mean`. |
| Variable | `FORECAST_MIN_POINTS` | No | `7` por defecto. |
| Variable | `FORECAST_CACHE_SIZE`, `FORECAST_CACHE_TTL_SECONDS` | No | `64` y `300` por defecto. |
| Variable | `MAX_SERIES_POINTS`, `MAX_PREDICTION_LENGTH`, `MAX_BODY_BYTES` | No | `2000`, `30` y `262144` por defecto (límites de la sección 6). |

`CHRONOS_MODEL_ID` se fija en el `Dockerfile` (`ARG` por defecto `autogluon/chronos-2-small`). Como la imagen corre con `HF_HUB_OFFLINE=1`, cambiar el modelo exige reconstruir la imagen con otro valor, no solo cambiar una variable del Space.

El token no debe aparecer en el código, en el `Dockerfile`, en los logs ni en `.env` dentro del repositorio.

### 1.3 Verificación tras el despliegue

```bash
curl -s https://<usuario>-caudal-ia.hf.space/v1/health    # 200 de inmediato
curl -s https://<usuario>-caudal-ia.hf.space/v1/ready     # 503 mientras carga, luego 200
```

`/v1/ready` tarda lo que tarde la carga del modelo desde la caché de la imagen. Mide ese tiempo con `scripts/measure_memory.py` (sección 5) antes de dar el servicio por listo.

## 2. Alternativa: Render

Render sirve la misma imagen como servicio web Docker.

- Plan con memoria suficiente para la **RAM pico** de la tabla de la sección 5 más el margen que decida el equipo. Verifica en la documentación de Render el límite de memoria del plan antes de elegirlo.
- Health check: `GET /v1/health`.
- Variables y secreto: los mismos que en la sección 1.2, configurados en el panel de Render. Render inyecta `PORT`; el `CMD` lo respeta.
- `CHRONOS_MODEL_ID` se cambia igual que en Hugging Face: reconstruyendo la imagen.

## 3. Rotación del token (contrato)

El servicio acepta el token actual (`IA_SERVICE_TOKEN`) y el anterior (`IA_SERVICE_TOKEN_PREVIOUS`) en tiempo constante. Así la rotación no corta el servicio. Los tres pasos:

1. **Acepta ambos.** En el Space, pon `IA_SERVICE_TOKEN_PREVIOUS` = token actual y `IA_SERVICE_TOKEN` = token nuevo. Espera al reinicio y comprueba que `/v1/ready` responde.
2. **Cambia el backend.** Actualiza `IA_SERVICE_TOKEN` del backend al token nuevo. Mientras tanto el servicio sigue aceptando el anterior, así que no hay corte.
3. **Retira el anterior.** Cuando el backend use el token nuevo, borra `IA_SERVICE_TOKEN_PREVIOUS` en el Space. El token anterior deja de funcionar.

Cada cambio de variable reinicia el Space.

## 4. Configuración del backend

El backend (`caudal-backend`) necesita:

| Variable | Valor |
|---|---|
| `IA_SERVICE_URL` | URL pública del servicio (`https://<usuario>-caudal-ia.hf.space` o la de Render). |
| `IA_SERVICE_TOKEN` | El mismo token de servicio que tiene el Space en `IA_SERVICE_TOKEN`. |

El backend envía `Authorization: Bearer <token>`. Si el servicio no responde, el backend usa su estimación simple de respaldo.

**`SERIES_TIMEZONE` debe coincidir con la zona horaria del backend.** El servicio agrupa las lecturas por día en esa zona y fecha los pronósticos a medianoche de ella. Si no coincide, el backend no reconoce el primer día esperado, descarta cada respuesta como `IA_ERROR` y termina abriendo el circuito. El valor por defecto es `America/Bogota`.

## 5. Mediciones (Modulo-IA, sección 12.1)

Obtenidas con `scripts/measure_memory.py` (I044) el 19 de octubre de 2026. La prueba corrió directamente en el equipo, **no dentro de un contenedor ni en el hardware de Hugging Face**, así que la memoria del contenedor y la del Space pueden diferir. Los valores de cada fila salen de los informes JSON de cada ejecución.

| Fecha (UTC) | Modelo | CPU de la máquina | Versiones | Carga (s) | RSS tras carga (MB) | RSS pico (MB) | Latencia típica, 60 puntos y horizonte 3 (ms, mediana de 5) | Latencia máxima, 2.000 puntos y horizonte 30 (ms, mediana de 5) | Límite (MB) | Resultado |
|---|---|---|---|---|---|---|---|---|---|---|
| 2026-10-19 21:11 | `autogluon/chronos-2-small` | Intel Core i5-12450H, 12 hilos, x86_64 | Python 3.12.14, torch 2.14.1+cpu, chronos-forecasting 2.3.2 | 0,5 | 391,4 | 502,8 | 8,8 | 42,5 | 2048 | Pasa |
| 2026-10-19 21:11 | `amazon/chronos-bolt-small` | Intel Core i5-12450H, 12 hilos, x86_64 | Python 3.12.14, torch 2.14.1+cpu, chronos-forecasting 2.3.2 | 0,5 | 395,9 | 577,4 | 14,9 | 43,2 | 2048 | Pasa |

Notas:

- **Carga:** los pesos ya estaban en la caché local, así que el tiempo no incluye una descarga desde cero. Dentro del contenedor construido con `podman`, `/v1/ready` respondió 200 a los ~40 s del arranque (incluye iniciar Python e importar torch). La primera carga en un contenedor con caché vacía tarda más; por eso los pesos se descargan al construir la imagen.
- **RSS pico:** `ru_maxrss` es el pico del proceso desde que arranca. Incluye la carga del modelo y las dos predicciones.
- **Límite:** 2048 MB es el valor por defecto de `MEMORY_LIMIT_MB` y es orientativo, no un criterio de hosting. Ajústalo al plan real con `--max-rss-mb` o con la variable.
- La latencia es de CPU de escritorio; en un plan de hosting con menos núcleos será mayor. Vuelve a medir allí antes de fijar objetivos de latencia.

Para repetir la medición:

```bash
uv run python scripts/measure_memory.py                                  # chronos-2-small
uv run python scripts/measure_memory.py --model-id amazon/chronos-bolt-small
```

El script sale con código `1` si el pico supera el límite. El workflow `.github/workflows/memory-ia.yml` lo ejecuta semanalmente, en PR que toquen dependencias o `src/caudal_ia/forecasting/**`, y en manual.

## 6. Límites del servicio

| Límite | Valor | Variable |
|---|---|---|
| Puntos por serie | 2.000 | `MAX_SERIES_POINTS` |
| Horizonte (`prediction_length`) | 1 a 30 | `MAX_PREDICTION_LENGTH` |
| Tamaño del cuerpo | 256 KiB (262.144 bytes) | `MAX_BODY_BYTES` |

Los cuerpos sin `Content-Length` (chunked) también se limitan: el middleware cuenta los bytes recibidos y responde `413` al superar el límite.

## 7. Seguridad

- El token solo vive en secretos del hosting. Nunca en git, en la imagen ni en logs.
- Swagger (`/docs`) documenta; ejecutar un pronóstico exige el token.
- El servicio no guarda series, pronósticos ni tokens. No tiene acceso a la base de datos.
