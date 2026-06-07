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
- **Swappable backends**: STT, TTS, and LLM are each abstracted behind a stable adapter interface. The active implementation is selected by config — no code changes to switch models. All three are independently swappable.

## Key Decisions Log

> **Instruction for AI assistants**: Whenever a design or architecture decision is made, changed, or reversed during any session, record it here immediately. Include what was decided, what was rejected, and why. This log is the authoritative record of intent — keep it current.

**TTS mode: batch, not streaming**
Batch TTS (generate full audio, then play) chosen over streaming. Streaming requires chunking, buffer management, and partial-sentence handling — significant complexity for marginal latency gain. Piper is fast enough that batch latency is acceptable.

**Voice session framing: wake word + end word**
Sessions are bounded by a wake word (start listening) and an end word (stop listening). This is deterministic and fully hands-free. VAD (Voice Activity Detection) was considered but rejected as the primary cutoff — it is unreliable across environments and mic setups. VAD may still be used as a fallback timeout (e.g. auto-cancel if silence exceeds 10s after wake word) but never as the primary session boundary.

**Server architecture: hub-and-spoke**
A local Python server owns the full pipeline. Clients (browser, mobile PWA) connect via WebSocket and stream audio. The server handles STT → LLM → TTS and returns audio. Clients are thin.

## Stack (TBD)

To be decided as implementation begins. Candidates:
- STT: faster-whisper
- TTS: Piper (fast, good quality, batch-friendly)
- Wake word: openWakeWord (ONNX, open source)
- LLM backend: Ollama (local) with Claude API as optional fallback
- Server: Python + FastAPI + WebSockets
- Client: Progressive Web App (PWA)
- Tool runtime: Python with a simple plugin loader

## Out of Scope

- Cloud hosting of any user data
- Proprietary voice APIs (Google, AWS, Azure) as primary path
- GUI-heavy interfaces — voice is the primary UX
