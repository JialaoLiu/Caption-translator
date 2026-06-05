# Contributing

Thanks for helping improve Caption translator.

## Development Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Run the app:

```powershell
python -m realtime_subtitle.main
```

## Guidelines

- Keep the app as a native desktop GUI, not a localhost-only web app.
- Do not commit private API keys, local `.env` files, or personal config overrides.
- Keep default runtime settings stream-friendly: `small + cpu + int8`.
- Avoid platform-specific assumptions unless they are isolated behind a small helper.
- Prefer replaceable interfaces for ASR, translation, output, and packaging logic.

## Pull Requests

Please include:

- What changed
- How you tested it
- Any CPU/GPU or streaming impact
- Screenshots if the UI changed
