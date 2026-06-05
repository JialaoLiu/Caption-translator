# Caption translator

Caption translator is a native Windows desktop app for realtime speech subtitles and translation during livestreams. It is designed for Bilibili Live Companion plus PUBG: low resource usage first, GPU disabled by default, and a separate pinned subtitle window that can be captured as a live material.

This is not a localhost web app. It runs as a desktop GUI and can be packaged into a Windows exe.

Repository: [JialaoLiu/Caption-translator](https://github.com/JialaoLiu/Caption-translator)

## Current Features

- Native PyQt6 control window with a custom modern dark QSS theme
- Always-on-top pinned subtitle window for Bilibili Live Companion window capture
- Microphone input device selection
- faster-whisper ASR
- Model switching: `tiny`, `base`, `small`, `medium`, `large-v3`
- Runtime device selection: `cpu` or `cuda`
- Compute type selection: `int8`, `float16`, `float32`
- Source languages: `auto`, Cantonese (`yue`), Mandarin (`zh`), English (`en`)
- Target languages: Mandarin Simplified (`zh_hans`), Mandarin Traditional (`zh_hant`), Cantonese (`yue`), English (`en`)
- App language switch: English / Simplified Chinese
- Accuracy mode: low latency, balanced, accuracy first
- Display modes: original, translation, bilingual
- Translation backends: Mock, Ollama, OpenAI-compatible API
- Realtime pinned subtitle display plus UTF-8 `subtitle.txt`
- Config persistence with corrupted-config recovery
- Windows packaging script using PyInstaller

## Recommended Live Settings

For PUBG plus Bilibili Live Companion:

- Start with `small + cpu + int8`
- If CPU usage is too high, switch to `base` or `tiny`
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

PyQt-SiliconUI is not bundled or copied. It is PyQt5-oriented and GPLv3 licensed, while this project currently stays PyQt6 + MIT. The current UI uses a self-written PyQt6 QSS theme.

## Run

```powershell
python -m realtime_subtitle.main
```

The first ASR run may download the selected faster-whisper model. Models are cached by the faster-whisper/Hugging Face stack and are not bundled into the exe by default.

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

- `Mock`: testing only, no real translation
- `Ollama`: local HTTP API, default model field is `qwen2.5:3b`
- `OpenAI-compatible API`: any `/v1/chat/completions` compatible endpoint

For Cantonese to natural Simplified Mandarin, use:

- Source language: `Cantonese / 粤语`
- Target language: `Mandarin Simplified / 简体普通话`
- Display mode: `Translation only` or `Bilingual`
- Translator backend: `Ollama` or `OpenAI-compatible API`

Do not use Mock for real translation.

API keys are entered in the GUI/config by the user. Do not commit private keys to GitHub.

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
