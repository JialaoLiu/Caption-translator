# Roadmap

## Near Term

- Better VAD tuning to reduce unnecessary ASR calls
- Optional system audio capture path
- Improve Qwen3-ASR and FunASR server presets, including health checks for `/v1/audio/transcriptions`
- More reliable subtitle window resize handles
- Translation backend presets for popular local OpenAI-compatible servers
- Optional vLLM offline inference helper for developer builds
- Runtime logs panel and exportable diagnostics

## Packaging

- Windows installer
- Code signing workflow
- Portable zip release
- Better first-run model download progress

## macOS

- Port the PyQt6 desktop app to macOS
- Add platform-specific audio device notes
- Package as `.dmg`
- Validate pinned/always-on-top behavior for common macOS streaming workflows

## Translation

- More local backends
- Glossary support for streamer names, game terms, and slang
- Short subtitle style controls
- Per-language punctuation cleanup

## Open Source

- CI syntax checks
- Release workflow
- More issue templates
- Contributor test matrix for CPU/GPU and streaming setups
