# Asistente de IA (Fase 13)

Contrato común (sección A de `contrato-v2`): los campos JSON van en snake_case y los enums en mayúsculas. El servicio sigue sin estado: el backend envía el *snapshot* completo en cada llamada.

## Endpoints

Todos exigen `Authorization: Bearer <IA_SERVICE_TOKEN>` y devuelven los errores con el mismo formato que `/v1/forecasts` (`{"error": {"code", "message", "details", "request_id"}}`). Un campo desconocido o inválido responde `400 VALIDATION_ERROR`.

| Ruta | Entrada | Salida |
|---|---|---|
| `POST /v1/insights/recommendations` | `{ "snapshot": Snapshot }` | `source`, `model`, `generated_at`, `summary`, `recommendations[]` (máximo 5: `action` OPEN, CLOSE, WAIT o INSPECT; `valve_id`; `reason` de hasta 280 caracteres; `confidence` de 0 a 1) |
| `POST /v1/insights/report` | `aqueduct_name`, `from`, `to`, `aggregates` (objeto libre de hasta 32 KB) | `source`, `model`, `generated_at`, `title`, `summary`, `findings[]`, `recommendations[]`, `markdown` |
| `POST /v1/insights/ask` | `question` (hasta 500 caracteres) y `snapshot` | `source`, `model`, `generated_at`, `answer` |

Límites del snapshot: 200 llaves, 200 turnos, 100 anomalías y 400 puntos de pronóstico. Todas las fechas llevan zona horaria. Como en el resto del servicio, el cuerpo no puede superar `MAX_BODY_BYTES`.

## Cómo decide

1. Si hay `LLM_API_KEY`, se llama a `{LLM_BASE_URL}chat/completions` con `response_format: {"type": "json_object"}`. Los prompts están en `src/caudal_ia/insights/prompts.py`; los datos del usuario se tratan como datos, no como instrucciones.
2. La salida se valida contra un esquema estricto. Cualquier fallo (timeout, red, 5xx tras los reintentos, 429, respuesta demasiado grande, JSON inválido o fuera del esquema) cae al respaldo: `source: "RULES"`, `model: "rules-v1"`. Un 429 no se reintenta.
3. Guardas duras sobre la salida del LLM y de las reglas: se descartan los `valve_id` que no están en el snapshot, OPEN y CLOSE sin llave, y todo OPEN con `level_pct <= reserve_floor_pct`; se cortan las razones a 280 caracteres y se dejan 5 recomendaciones. Si el LLM no deja ninguna utilizable, se usan las reglas.

Reglas de respaldo (`RulesAdvisor`): con el tanque en o bajo el piso cierra las llaves motorizadas abiertas de menor prioridad (número mayor) y espera; sobre el piso abre las llaves del turno activo solo si el nivel supera el piso más `ASSISTANT_OPEN_MARGIN_PCT` y el p10 del pronóstico no baja del piso; cierra las llaves cuyo turno ya terminó; pide inspección de anomalías de severidad ALTA y de llaves con estado desconocido. Informe y pregunta usan plantillas.

## Proveedores LLM

Cualquier servidor compatible con OpenAI sirve; solo cambian las variables:

| Proveedor | `LLM_BASE_URL` | `LLM_MODEL` |
|---|---|---|
| OpenRouter, Nemotron de NVIDIA gratis (por defecto) | `https://openrouter.ai/api/v1/` | `nvidia/nemotron-3.5-super-vl:free` (acepta `response_format` JSON) |
| Gemini | `https://generativelanguage.googleapis.com/v1beta/openai/` | `gemini-2.5-flash` |
| OpenAI | `https://api.openai.com/v1/` | un modelo con salida JSON |
| Local (Ollama) | `http://localhost:11434/v1/` | el modelo descargado |

`LLM_API_KEY` es un secreto: va en el panel de Render (`sync: false`), nunca en el repositorio. Variables: `LLM_TIMEOUT_S`, `LLM_MAX_RETRIES`, `LLM_MAX_OUTPUT_TOKENS`, `LLM_MAX_RESPONSE_BYTES`, `LLM_TEMPERATURE` y `ASSISTANT_OPEN_MARGIN_PCT` (valores por defecto en `.env.example`).

## Pruebas

`tests/insights/` usa `FakeLlmClient` (`tests/fakes.py`) y `httpx.MockTransport`; no hay red ni claves, y no carga Chronos real. Para probar con un LLM falso en la app: `app.state.llm_client = FakeLlmClient(...)`.
