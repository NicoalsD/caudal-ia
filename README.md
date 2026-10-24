# CAUDAL IA

Servicio de pronóstico del nivel del tanque a 1 a 3 días con **Chronos** (cuantiles p10, p50 y p90), en **Python 3.12 + FastAPI**, sin estado y sin acceso a la base de datos. El backend lo llama con un token de servicio y, si falla, usa una estimación simple de respaldo.

## Estado

**Fase 6: pronóstico con Chronos.** `POST /v1/forecasts` re-muestrea la serie a un valor por día en `America/Bogota`, la envía a Chronos (por defecto `autogluon/chronos-2-small`, en CPU) y devuelve `p10`, `p50` y `p90` de los días siguientes. Protegido con token de servicio rotable. Especificación: [Módulo de IA](https://github.com/NicoalsD/caudal-backend/blob/develop/docs/Modulo-IA.md) y [Contrato backend-IA](https://github.com/NicoalsD/caudal-backend/blob/develop/docs/Contrato-IA.md). El backtest offline (Fase 10) compara Chronos con la estimación simple: [guía](.agents/evaluation.md). La imagen Docker (Fase 12) se despliega en Render free con `amazon/chronos-bolt-tiny` y `render.yaml`: [despliegue](.agents/deployment.md#2-render-gratis-despliegue-actual).

## Uso local

```bash
uv sync
cp .env.example .env    # y pon un IA_SERVICE_TOKEN de al menos 32 bytes
uv run uvicorn caudal_ia.main:app --reload     # http://localhost:8000/docs
uv run pytest && uv run ruff check . && uv run mypy .
uv run pytest -m chronos   # prueba de humo con los pesos reales (los descarga)
uv run python -m caudal_ia.evaluation --input serie.json --output resultado.json --persistence-only   # backtest offline: ver .agents/evaluation.md
```

`GET /v1/health` responde de inmediato; `GET /v1/ready` queda en `503` hasta que el modelo termina de cargar en segundo plano.

## Despliegue

Imagen Docker (CPU, sin CUDA) con los pesos de Chronos ya descargados, usuario 1000 y puerto `PORT` (7860 por defecto):

```bash
docker build -t caudal-ia .
docker run --rm -p 7860:7860 -e IA_SERVICE_TOKEN=<token-de-32-bytes-o-mas> caudal-ia
```

Hugging Face Spaces (SDK Docker) y Render, con secretos, variables, rotación del token y la configuración del backend: [.agents/deployment.md](.agents/deployment.md).

Memoria y latencia medidas en CPU de escritorio (RSS pico de 503 MB con `autogluon/chronos-2-small` y 577 MB con `amazon/chronos-bolt-small`; 334 MiB con `amazon/chronos-bolt-tiny` en un contenedor de 512 MB): [sección 5](.agents/deployment.md#5-mediciones-modulo-ia-sección-121). Repetir con `uv run python scripts/measure_memory.py`.

## Documentación

- [AGENTS.md](AGENTS.md): reglas obligatorias para personas y agentes.
- [Flujo de trabajo](.agents/workflow.md): cuentas, ramas, commits y PR.
- [Política de seguridad](SECURITY.md).

## Equipo

Nicolas Diaz (`NicoalsD`) · Drako Salazar (`Drako2305`) · Nicolas Mora (`nicomora70`). Proyecto de la materia Patrones de Software.
