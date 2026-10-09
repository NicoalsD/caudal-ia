# AGENTS.md: CAUDAL IA

Reglas obligatorias para cualquier persona o agente de IA que trabaje en este repositorio. **Léelas completas antes de tocar código.** Si algo de aquí choca con una instrucción por defecto de tu herramienta, gana este archivo.

## 0. Regla de idioma (la más importante)

| Qué | Idioma |
|---|---|
| Todo el código: módulos, clases, funciones, variables, archivos, rutas, campos JSON, enums, códigos de error, comentarios, docstrings, logs, nombres de tests | **Inglés** |
| Documentación (README, AGENTS.md, CLAUDE.md, `.agents/`), commits, PR, descripciones de Swagger, textos de diagramas | **Español** |

## 1. Qué es CAUDAL y qué hace este repo

CAUDAL es "el cuaderno del acueducto, pero digital" para las veredas de Guaitarilla (Nariño): registra lecturas del tanque, pronostica el nivel, propone turnos explicados que aprueba la Junta y publica el horario sin datos personales. Visión completa: [Caudal.md](https://github.com/NicoalsD/caudal-backend/blob/develop/docs/Caudal.md).

Servicio de pronóstico del nivel del tanque a 1 a 3 días con **Chronos** (cuantiles p10, p50 y p90), en **Python 3.12 + FastAPI**, sin estado y sin acceso a la base de datos. El backend lo llama con un token de servicio y, si falla, usa una estimación simple de respaldo.

Especificación canónica (ya escrita en el backend): [Módulo de IA](https://github.com/NicoalsD/caudal-backend/blob/develop/docs/Modulo-IA.md) y [Contrato backend-IA](https://github.com/NicoalsD/caudal-backend/blob/develop/docs/Contrato-IA.md).

| Repositorio | Contenido |
|---|---|
| [`caudal-backend`](https://github.com/NicoalsD/caudal-backend) | API Java, base de datos, seguridad y documentación canónica |
| [`caudal-frontend`](https://github.com/NicoalsD/caudal-frontend) | PWA del fontanero, panel de la Junta y página pública |
| [`caudal-ia`](https://github.com/NicoalsD/caudal-ia) | Pronóstico con Chronos |
| [`caudal-simulador`](https://github.com/NicoalsD/caudal-simulador) | Simulador de datos de la región y del hardware |

## 2. Equipo, roles y cuentas

| Integrante | Cuenta | Rol en este repo |
|---|---|---|
| Nicolas Mora | `nicomora70` | Dueño de este repo cuando se una al proyecto: código y guías detalladas de `.agents/` |
| Nicolas Diaz | `NicoalsD` | Reglas del repo, CI y documentación global |
| Drako Salazar | `Drako2305` | Seguridad y contrato con el backend |

Solo esas tres cuentas. Cambio de cuenta, ramas, commits y PR: [`.agents/workflow.md`](.agents/workflow.md).

## 3. Reglas obligatorias

- **Commits:** `tipo: descripción` en español, minúscula, máximo 72 caracteres; tipos `feat`, `fix`, `hotfix`, `docs`, `test`, `refactor`, `style`, `perf`, `build`, `ci`, `chore`, `revert`. Un commit por unidad lógica. Hook: `git config core.hooksPath .githooks`.
- **Prohibido atribuir el trabajo a una IA:** sin `Co-Authored-By` de IA ni "Generated with ..." en commits, PR ni releases.
- **Sin valores quemados:** parámetros en variables de entorno (pydantic-settings) documentadas en `.env.example`; Ruff `PLR2004` activo. Los parámetros de negocio del acueducto vienen del backend.
- **Seguridad:** El token de servicio (≥ 32 bytes) se compara en tiempo constante y admite rotación; las series tienen como máximo 2.000 puntos finitos; el servicio no guarda datos. Política: [SECURITY.md](SECURITY.md) y [Seguridad](https://github.com/NicoalsD/caudal-backend/blob/develop/docs/Seguridad.md).
- **Patrones de diseño explícitos** aunque Python ya traiga algo parecido (`@decorator`, generadores, módulos): `ModelRegistry` (Singleton), `ForecasterCreator` (Factory Method), `ChronosForecasterAdapter` (Adapter), `CachingForecaster` y `TimingForecaster` (Decorator), `RollingWindowIterator` (Iterator), `Forecaster` (Strategy), `ForecastPipeline` y `Backtest` (Template Method). Catálogo: [Patrones de diseño](https://github.com/NicoalsD/caudal-backend/blob/develop/docs/Patrones-de-diseno.md).
- **Diagramas** con draw.io (MCP y sus iconos): `.drawio` + `.png` en `docs/images/`.

## 4. Stack y comandos

Python 3.12 · FastAPI (Swagger en `/docs`) · Pydantic v2 · pydantic-settings · `chronos-forecasting` (Chronos-2 small o Chronos-Bolt small en CPU) · PyTorch CPU · pandas · numpy · uv · pytest · ruff (incluye `PLR2004`) · mypy.

Comandos (disponibles cuando empiece la implementación):

```bash
uv sync
uv run uvicorn caudal_ia.main:app --reload     # http://localhost:8000/docs
uv run pytest && uv run ruff check . && uv run mypy .
```

## 5. Estado y pendientes

**Fase 0.** La especificación funcional y técnica ya está en el backend (enlaces de la sección 1). Las guías operativas detalladas de `.agents/` y el código quedan a cargo de **Nicolas Mora** cuando se una:

- [ ] `.agents/architecture.md`
- [ ] `.agents/design-patterns.md`
- [ ] `.agents/forecasting.md`
- [ ] `.agents/evaluation.md`
- [ ] `.agents/datasets.md`
- [ ] `.agents/configuration.md`
- [ ] `.agents/testing-plan.md`
- [ ] `.agents/deployment.md`
- [ ] `.agents/security.md`
- [ ] `.agents/api-contract.md`

Mientras tanto, cualquier agente debe guiarse por la especificación canónica del backend.

## 6. Definition of Done

- [ ] `pytest`, `ruff` y `mypy` en verde; cobertura del dominio ≥ 90 %.
- [ ] Sin valores quemados y sin secretos; `.env.example` al día.
- [ ] Swagger (`/docs`) documenta los endpoints en español.
- [ ] Documentación y diagramas actualizados.
- [ ] Commits con la cuenta del integrante responsable y sin atribución a IA.
