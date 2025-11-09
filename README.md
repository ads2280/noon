
```
   _   _    .-----.  .-----.    _   _
  | \ | |  / 12 ^ \ / 12 ^ \  | \ | |
  |  \| | |  \ |  ||  | /  | |  \| |
  | |\  | |  / o  ||  o \  | | |\  |
  |_| \_|  \__6__/  \__6__/  |_| \_|

  it's time, but it's really simple.
```


## Development

Make sure you have [uv](https://docs.astral.sh/uv) installed:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## iOS Color Palette

SwiftUI uses a centralized palette in `noon-ios/Noon/ColorPalette.swift`:

- `ColorPalette.Semantic` provides semantic `Color` values (primary, secondary, destructive, success, warning).
- `ColorPalette.Text` and `ColorPalette.Surface` cover common text and background tones.
- `ColorPalette.Gradients` exposes reusable gradients, including the orangey primary gradient for call-to-action elements.

Use these helpers rather than hard-coding colors to keep the interface consistent. For example:

```swift
Text("CTA")
    .foregroundStyle(ColorPalette.Text.inverted)
    .padding()
    .background(ColorPalette.Gradients.primary)
    .clipShape(Capsule())
```


Usage:

```bash
# To format
uv run ruff format

# To lint
uv run ruff check

# To auto-fix lint issues
uv run ruff check --fix

# To add dependencies
uv add anthropic

# To sync your env
uv sync

# To run a script
uv run
```

## Voice Transcription Service

The iOS microphone button posts audio to the local Deepgram proxy in `noon-v2nl`. To start it:

1. `cd noon-v2nl`
2. Create `.env` in that directory with `DEEPGRAM_API_KEY=<your key>` (the app loads it automatically).
3. Install dependencies once: `uv pip install -r requirements.txt`
4. Launch the API: `uv run uvicorn noon-v2nl.main:app --host 0.0.0.0 --port 8001`

The service exposes `POST /v1/transcriptions`, which the app calls at `http://localhost:8001/v1/transcriptions`. Keep the server running while you test press-and-hold transcription in the simulator or on device.