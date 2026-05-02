# ADR-0001: FastAPI as Web Framework
![Status](https://img.shields.io/badge/status-accepted-brightgreen)

| Date | Deciders | Supersedes |
|------|----------|------------|
| 2026-04-24 | Andy | — |

---

## Context

> [!NOTE]
> The margin calculator is a single-purpose HTTP API: one `POST /margin` endpoint that accepts a list of positions, fans work out to a `ProcessPoolExecutor`, and returns a margin total. The framework choice shapes validation, async behaviour, observability integration, and how AI tooling can introspect the API surface.

## Decision

**We use FastAPI with Pydantic v2 models and Uvicorn as the ASGI server.**

Request and response schemas are declared as `pydantic.BaseModel` subclasses. FastAPI derives validation, serialisation, and an OpenAPI spec from those types automatically. Endpoints are `async def` so that the event loop is never blocked while workers run.

## Consequences

> [!IMPORTANT]
> - **Automatic OpenAPI spec** at `/openapi.json` and interactive docs at `/docs` — used directly by the MCP server to expose the API surface to AI agents without a separate schema maintenance step.
> - **Zero-boilerplate validation** — `MarginRequest` and `MarginResponse` are plain Python dataclasses with types; FastAPI handles 422 responses for bad input automatically.
> - **First-class OTel instrumentation** — `opentelemetry-instrumentation-fastapi` wraps the middleware stack and produces spans for every request without manual instrumentation.
> - **Async-native** — the `ProcessPoolExecutor` + `asyncio.wait_for` pattern for CPU-bound work is a natural fit; a synchronous framework would require a thread pool workaround instead.
> - **Pydantic coupling** — models must be Pydantic types to get automatic schema generation; plain dataclasses or `TypedDict` lose the OpenAPI and validation benefits.

## Alternatives Considered

| Option | Why Rejected |
|--------|-------------|
| **Flask** | Synchronous by default; adding async via `quart` introduces complexity. No native Pydantic or OpenAPI integration. |
| **Django REST Framework** | Heavyweight ORM + settings machinery for a service with no relational models and no admin interface. |
| **Starlette (bare)** | FastAPI is a thin layer on top of Starlette — using it directly would mean hand-rolling validation and schema generation that FastAPI provides for free. |
| **aiohttp** | Manual routing and no OpenAPI tooling; MCP server would need a separate schema definition. |
