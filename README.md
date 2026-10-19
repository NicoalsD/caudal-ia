# CAUDAL IA

Servicio de pronóstico del nivel del tanque a 1 a 3 días con **Chronos** (cuantiles p10, p50 y p90), en **Python 3.12 + FastAPI**, sin estado y sin acceso a la base de datos. El backend lo llama con un token de servicio y, si falla, usa una estimación simple de respaldo.

## Estado

**Fase 6: pronóstico con Chronos.** `POST /v1/forecasts` re-muestrea la serie a un valor por día en `America/Bogota`, la envía a Chronos (por defecto `autogluon/chronos-2-small`, en CPU) y devuelve `p10`, `p50` y `p90` de los días siguientes. Protegido con token de servicio rotable. Especificación: [Módulo de IA](https://github.com/NicoalsD/caudal-backend/blob/develop/docs/Modulo-IA.md) y [Contrato backend-IA](https://github.com/NicoalsD/caudal-backend/blob/develop/docs/Contrato-IA.md). Pendiente: backtest (Fase 10) y despliegue (Fase 12).

## Uso local

```bash
uv sync
cp .env.example .env    # y pon un IA_SERVICE_TOKEN de al menos 32 bytes
uv run uvicorn caudal_ia.main:app --reload     # http://localhost:8000/docs
uv run pytest && uv run ruff check . && uv run mypy .
uv run pytest -m chronos   # prueba de humo con los pesos reales (los descarga)
```

`GET /v1/health` responde de inmediato; `GET /v1/ready` queda en `503` hasta que el modelo termina de cargar en segundo plano.

## Documentación

- [AGENTS.md](AGENTS.md): reglas obligatorias para personas y agentes.
- [Flujo de trabajo](.agents/workflow.md): cuentas, ramas, commits y PR.
- [Política de seguridad](SECURITY.md).

## Equipo

Nicolas Diaz (`NicoalsD`) · Drako Salazar (`Drako2305`) · Nicolas Mora (`nicomora70`). Proyecto de la materia Patrones de Software.
