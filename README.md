# CAUDAL IA

Servicio de pronóstico del nivel del tanque a 1 a 3 días con **Chronos** (cuantiles p10, p50 y p90), en **Python 3.12 + FastAPI**, sin estado y sin acceso a la base de datos. El backend lo llama con un token de servicio y, si falla, usa una estimación simple de respaldo.

## Estado

**Fase 0: planeación.** La especificación está en el backend: [Módulo de IA](https://github.com/NicoalsD/caudal-backend/blob/develop/docs/Modulo-IA.md) y [Contrato backend-IA](https://github.com/NicoalsD/caudal-backend/blob/develop/docs/Contrato-IA.md). La implementación queda a cargo de Nicolas Mora (`nicomora70`) cuando se una al proyecto.

## Documentación

- [AGENTS.md](AGENTS.md): reglas obligatorias para personas y agentes.
- [Flujo de trabajo](.agents/workflow.md): cuentas, ramas, commits y PR.
- [Política de seguridad](SECURITY.md).

## Equipo

Nicolas Diaz (`NicoalsD`) · Drako Salazar (`Drako2305`) · Nicolas Mora (`nicomora70`). Proyecto de la materia Patrones de Software.
