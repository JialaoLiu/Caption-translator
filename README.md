# Caption translator

Caption translator is a native Windows desktop app for realtime speech subtitles and translation during livestreams. It is designed for Bilibili Live Companion plus PUBG: low resource usage first, GPU disabled by default, and a separate pinned subtitle window that can be captured as a live material.

This is not a localhost web app. It runs as a desktop GUI and can be packaged into a Windows exe.

Repository: [JialaoLiu/Caption-translator](https://github.com/JialaoLiu/Caption-translator)

## Current Features

- Native PyQt6 control window with `pyqt-siliconui` installed as a UI dependency and a PyQt6 QSS runtime fallback
- Always-on-top pinned subtitle window for Bilibili Live Companion window capture
- Microphone input device selection
- Audio modes: Mic only, System only, Mic + System
- Windows WASAPI loopback for system audio capture
- Default ASR: SenseVoiceSmall 234M
- Optional ASR engines: Qwen3-ASR-0.6B, Qwen3-ASR-1.7B, Fun-ASR-Nano, local vLLM/FunASR service presets
- Model switching: `tiny`, `base`, `small`, `medium`, `large-v3`
- Runtime device selection: `cpu` or `cuda`
- Compute type selection: `int8`, `float16`, `float32`
- Source languages: `auto`, Cantonese (`yue`), Mandarin (`zh`), English (`en`)
- Target languages: Mandarin Simplified (`zh_hans`), Mandarin Traditional (`zh_hant`), Cantonese (`yue`), English (`en`)
- App language switch: English / Simplified Chinese
- Accuracy mode: low latency, balanced, accuracy first
- Display modes: original, translation, bilingual
- Translation backends: Ollama by default, Disabled for original-only subtitles
- Realtime pinned subtitle display plus UTF-8 `subtitle.txt`
- Config persistence with corrupted-config recovery
- Windows packaging script using PyInstaller

## Recommended Live Settings

For PUBG plus Bilibili Live Companion:

- Start with `SenseVoiceSmall + cpu`
- If CPU usage is too high, increase the chunk interval or switch to a server/GPU ASR setup after testing
- Do not default to CUDA, because it can compete with the game and stream encoder
- Do not use `medium` or `large-v3` during gameplay unless you have tested your headroom
- Keep the chunk interval around `2` to `3` seconds

## Install From Source

Use Python 3.10 or newer on Windows.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

`pyqt-siliconui` is listed as a dependency because the product direction targets that visual style. The current runtime keeps a PyQt6 QSS fallback so the app does not break when PyQt5-oriented SiliconUI APIs are unavailable.

## Run

```powershell
python -m realtime_subtitle.main
```

The first ASR run may need the selected ASR model. Models are not bundled into the exe by default.

Optional ASR engines need extra dependencies:

```powershell
pip install -r requirements-asr.txt
```

Then open Advanced settings, choose an ASR engine, and click `Download ASR model`. The app shows download progress and stores models under `models/asr/`. The default recommended model is SenseVoiceSmall.

## Optional Local vLLM / FunASR ASR

For high-accuracy or GPU-heavy ASR, run the model as a local offline vLLM/FunASR service and let Caption translator connect to it automatically through the preset. This keeps the normal Windows app lightweight and avoids bundling vLLM into the exe.

Qwen3-ASR via vLLM:

```powershell
vllm serve Qwen/Qwen3-ASR-1.7B
```

Then choose `Qwen3-ASR local vLLM service` in Advanced settings.

FunASR OpenAI-compatible server:

```powershell
funasr-server --model sensevoice --device cuda
```

Then choose `Fun-ASR-Nano local vLLM/FunASR service`.

Local service ASR mode does not download local ASR weights inside the app. The local vLLM/FunASR service owns model loading and GPU/CPU resource usage.

## Bilibili Live Companion Capture

Recommended flow:

```text
Pinned subtitle window
↓
Bilibili Live Companion
↓
Window capture / Screen capture
```

In Bilibili Live Companion:

1. Start Caption translator.
2. Keep the `Caption Translator Subtitle` window visible.
3. Add a live material/source.
4. Choose window capture.
5. Capture the `Caption Translator Subtitle` window.
6. Resize and place the subtitle source in your scene.

If window capture is unstable, use screen capture and select the subtitle area.

See [docs/bilibili_live_setup.zh-CN.md](docs/bilibili_live_setup.zh-CN.md) for the Chinese setup guide.

## Translation Backends

Whisper/faster-whisper is used only for speech-to-text. Arbitrary language translation is handled by `translator.py`.

Backends:

- `Ollama`: local HTTP API, default model field is `qwen2.5:3b`
- `Disabled`: original subtitles only, no translation

For Cantonese to natural Simplified Mandarin, use:

- Source language: `Cantonese / 粤语`
- Target language: `Mandarin Simplified / 简体普通话`
- Display mode: `Translation only` or `Bilingual`
- Translator backend: `Ollama`

Do not use Mock for real translation.

Mock is an internal test translator. It does not translate; it only helps developers test whether the subtitle pipeline is connected.

## Ollama Default

The default real translation backend is Ollama with `qwen2.5:3b`.

On startup and before translation, the app checks:

```text
GET http://localhost:11434/api/tags
```

If Ollama is not running, the app does not crash. Translation is disabled and original text is shown. If Ollama is running but the model is missing, run:

```powershell
ollama pull qwen2.5:3b
```

`qwen3:4b` and custom model names are also available in the UI.

## Audio Modes

- `Mic only`: microphone input only
- `System only`: Windows WASAPI loopback, computer audio only
- `Mic + System`: microphone plus WASAPI loopback mixed inside the app, then sent to one ASR worker

Mic + System is the default. The app does not assume WASAPI loopback includes microphone audio.

Private API keys should not be committed to GitHub. The normal UI currently avoids API-key fields.

## Build Windows exe

```powershell
.\build_windows.ps1 -Clean
```

Output:

```text
dist/CaptionTranslator.exe
```

Large ASR models are not forced into the exe. They download/cache on first use or can be pre-cached on the target machine.

See [docs/build_windows.zh-CN.md](docs/build_windows.zh-CN.md).

## Disclaimer

Realtime ASR and translation can be inaccurate, especially with game noise, music, accents, slang, or overlapping voices. Test CPU/GPU load before going live.
