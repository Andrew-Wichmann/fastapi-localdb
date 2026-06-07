# Requirements

## Functional Requirements

### FR-1: Voice Interface
- The system MUST accept voice input without requiring keyboard or touch interaction during active use
- The system MUST produce voice output for all responses
- The system MUST support a wake-word or push-to-talk trigger to begin listening
- The system SHOULD handle natural pauses without cutting off the user

### FR-2: Extensible Tool System
- The system MUST expose a standard tool interface that extensions implement
- Extensions MUST be loadable without modifying core assistant code
- The tool system MUST support at minimum:
  - **Recordings**: Capture and store structured voice notes or observations
  - **Research**: Query local knowledge bases or perform web lookups
  - **Analysis**: Process captured data and surface insights
  - **Recommendation**: Suggest actions based on context or prior recordings
- The assistant MUST be able to discover available tools at runtime

### FR-3: Local Operation
- All inference (STT, LLM, TTS) MUST run on user-owned hardware by default
- No user data (audio, transcripts, tool state) MUST leave the local network
- Storage MUST be local (filesystem or local database)

### FR-4: Mobile Hands-Free
- The system MUST be accessible from a mobile device
- The system CAN be accessible from the internet
- The mobile interface MUST support hands-free operation (no tap required mid-session)
- Audio capture and playback MUST work in a mobile browser or native app
- The system SHOULD work while the mobile screen is off or locked (background audio)

## Non-Functional Requirements

### NFR-1: Latency
- End-to-end response latency (voice in → voice out) SHOULD be under 10 seconds for short queries on target hardware

### NFR-2: Privacy
- No telemetry, analytics, or usage data MUST be transmitted externally

### NFR-3: Extensibility
- Adding a new tool MUST require writing only the tool module itself — no changes to core
- Tool interface MUST be versioned to allow future evolution without breaking existing tools

### NFR-4: Model Swappability
- The STT, TTS, and LLM backends MUST each be selectable via configuration — no code changes required to switch models
- Configuration MUST support specifying the model provider, model name/path, and any provider-specific parameters (e.g. quantization, device, voice)
- The system MUST define a stable adapter interface for each backend type (STT, TTS, LLM) so that new model integrations implement the interface without touching the pipeline
- Swapping one backend MUST NOT require changes to the other two backends or to any tool

### NFR-5: Hardware Target
- MUST run on a single consumer-grade machine (no cluster required)
- SHOULD support GPU acceleration where available, with CPU fallback

## Constraints

- Primary language: TBD (Python preferred for ML ecosystem compatibility)
- No reliance on paid cloud APIs for core functionality
- Must support Linux as the primary host OS (user's environment)
