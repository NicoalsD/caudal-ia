# Política de seguridad

Gracias por ayudar a proteger CAUDAL. Este repositorio contiene `caudal-ia`, el servicio de pronóstico del nivel del tanque. Es una API FastAPI con el modelo Chronos. No guarda datos ni accede a la base de datos.

La política global de seguridad del proyecto, con las reglas del backend, la base de datos y la infraestructura, está en [`docs/Seguridad.md`](https://github.com/NicoalsD/caudal-backend/blob/develop/docs/Seguridad.md) del repositorio `caudal-backend`. Este documento solo cubre lo que pasa en `caudal-ia`.

## Versiones soportadas

| Versión | Soporte de seguridad |
|---|---|
| Última versión etiquetada en `main` | Sí |
| Versiones anteriores a la última etiqueta | No |
| Rama `develop` | No garantizada (es la rama de integración) |

Propuesta a confirmar: la política de versiones soportadas se revisará al publicar la versión `v1.0.0` del proyecto.

## Cómo reportar una vulnerabilidad

**No abras un issue público, un PR ni un comentario** con los detalles de una vulnerabilidad.

Repórtala de forma privada:

1. Ve a la pestaña **Security** del repositorio.
2. Elige **Report a vulnerability** (reporte privado de vulnerabilidades de GitHub).
3. Completa el formulario con la información que se indica abajo.

Solo los integrantes del equipo con acceso al repositorio pueden leer el reporte.

## Qué incluir en el reporte

- Descripción breve del problema y el tipo de riesgo (por ejemplo, bypass de autenticación, fuga del token de servicio, denegación de servicio por series grandes, carga de un modelo no confiable).
- Endpoint afectado (`POST /v1/forecasts`, `GET /v1/health`, `GET /v1/ready`, `GET /v1/models`) y versión o commit.
- Pasos para reproducirlo, con la solicitud HTTP concreta. Usa series de prueba sintéticas.
- Impacto esperado.
- Evidencia mínima: respuestas HTTP y, si aplica, un fragmento de log. No incluyas tokens reales.
- Propuesta de corrección, si la tienes (opcional).

## Tiempos de respuesta

| Etapa | Tiempo objetivo |
|---|---|
| Acuse de recibo | Por definir |
| Confirmación o descarte del problema | Por definir |
| Corrección o plan de mitigación | Por definir |
| Publicación de la corrección y, si aplica, del aviso | Por definir |

Los tiempos se confirmarán antes de la versión `v1.0.0`. Mientras tanto, son objetivos y no garantías.

## Alcance

**Dentro del alcance:**

- El código de este repositorio y su imagen de contenedor (Docker, Hugging Face Spaces o Render, según el despliegue).
- La autenticación del endpoint de pronóstico con el token de servicio (`Authorization: Bearer`) y su comparación en tiempo constante.
- Los límites de entrada: series de hasta 2.000 puntos, valores finitos, marcas de tiempo crecientes, `prediction_length` de hasta 30 y la validación con Pydantic v2.
- La carga del modelo Chronos (`chronos-forecasting`), la selección del modelo por variable de entorno y el manejo de errores (`MODEL_NOT_READY`, `INSUFFICIENT_HISTORY`, `INVALID_SERIES`).
- La configuración de dependencias (PyTorch CPU, pandas, numpy y el resto del `uv.lock`).

**Fuera del alcance:**

- Vulnerabilidades del backend Java, de la base de datos o del frontend. Repórtalas según la política global o en el repositorio correspondiente.
- Servicios de terceros (Hugging Face, Render, GitHub). Repórtalos a cada proveedor.
- Pruebas de carga que degraden un servicio en uso.
- Ingeniería social y ataques físicos.

## Reglas para quien investiga

- Prueba solo en tu entorno local (Docker o `uv run`) o en el entorno de pruebas que indique el equipo.
- No envíes series con datos de personas. El proyecto no tiene datos reales de la región; todo es simulado.
- No hagas pruebas que degraden el servicio para otros usuarios.

## Notas de seguridad del servicio

Estas notas describen el diseño y no sustituyen el reporte. Están sujetas a confirmación técnica:

- **Sin almacenamiento de datos.** El servicio no guarda series, pronósticos ni tokens. Cada solicitud se procesa en memoria. No hay acceso a PostgreSQL.
- **Token de servicio.** Al menos 32 bytes aleatorios. Se acepta el token actual y el anterior para permitir la rotación. Nunca se escribe en logs, respuestas ni la URL.
- **Pesos del modelo.** Los pesos de Chronos se descargan de Hugging Face. Verificar la revisión (commit) fijada del modelo y el formato de carga. Preferir formatos sin ejecución de código al cargar pesos (verificar en la versión de PyTorch y de Chronos que se use).
- **Dependencias de PyTorch y Chronos.** Versiones fijadas con `uv.lock`. Las alertas de Dependabot se revisan antes de cada release. Las versiones de referencia y las rutas de instalación de PyTorch CPU se verifican al instalar.
- **Recursos.** Límites de tamaño de serie y de horizonte para evitar agotamiento de memoria o de CPU. El backend aplica además sus propios timeouts (conexión de 2 s, lectura de 10 s) y un circuit breaker.
- **Registros.** Logs en JSON con `requestId`. No se registran cuerpos de series ni el encabezado `Authorization`.

Relacionados: [Política global de seguridad](https://github.com/NicoalsD/caudal-backend/blob/develop/docs/Seguridad.md), [Validación de entradas del backend](https://github.com/NicoalsD/caudal-backend/blob/develop/.agents/input-validation.md), [Política de seguridad del simulador](https://github.com/NicoalsD/caudal-simulador/blob/develop/SECURITY.md)
