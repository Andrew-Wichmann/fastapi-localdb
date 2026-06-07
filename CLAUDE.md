# Voice Assistant — Project Context for Claude

## What This Is

A personal, self-hosted voice assistant modeled after Claude's conversational interface. Built to be used hands-free, extensible via specialized tools, and fully local — no data leaves the user's hardware.

## Core Requirements

| # | Requirement | Detail |
|---|-------------|--------|
| 1 | **Voice-first interface** | Fully hands-free. Wake word or push-to-talk. Both input (STT) and output (TTS) are voice. |
| 2 | **Extensible tool system** | Plugin/tool architecture supporting: specialized recordings, research, analysis, recommendation, and notifications. New tools can be added without modifying core. |
| 3 | **Fully local** | All models, storage, and processing run on user-owned hardware. No cloud APIs for core functionality. Data never leaves the machine. |
| 4 | **Mobile hands-free** | Works on mobile devices. No physical interaction required during a session. |

## Architecture Principles

- **Local-first**: Prefer on-device models (Whisper for STT, Kokoro/Piper for TTS, Ollama for LLM)
- **Tool interface**: Tools expose a standard interface (name, description, schema, handler) so the assistant can discover and invoke them uniformly
- **Stateless core, stateful tools**: The assistant pipeline is stateless; tools own their state
- **Progressive enhancement**: Core voice loop works standalone; tools layer on top

## Key Decisions Log

_Record non-obvious technical decisions here as the project evolves._

## Stack (TBD)

To be decided as implementation begins. Candidates:
- STT: Whisper (faster-whisper / whisper.cpp)
- TTS: Kokoro, Piper, or Coqui
- LLM backend: Ollama (local) with Claude API as optional fallback
- Tool runtime: Python with a simple plugin loader
- Mobile: Progressive Web App (PWA) or native with a local server

## Out of Scope

- Cloud hosting of any user data
- Proprietary voice APIs (Google, AWS, Azure) as primary path
- GUI-heavy interfaces — voice is the primary UX
