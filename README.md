# Beets Semantic Enricher (Gemini & Ollama)

A [Beets](https://beets.io/) plugin that uses Multimodal AI to enrich your music library with deep semantic metadata. It samples your tracks using `ffmpeg` and performs MIR (Music Information Retrieval) analysis via Google Gemini or local LLMs via Ollama.

## Features

*   **Temporal Sampling**: Dynamic sampling strategy based on track duration:
    *   `< 5m`: 30s sample at midpoint.
    *   `5-10m`: Two 20s samples (25% and 75%).
    *   `> 10m`: Four 15s samples (5%, 25%, 50%, and 85%) to capture track evolution.
*   **Three-Layer Analysis**:
    *   **MIR Standard**: Mood and technical timbre (dissonance, rhythm texture).
    *   **AudioSet Taxonomy**: Detection of natural sounds (birds, water) and textures (hiss, white noise).
    *   **Temporal Narrative**: A one-sentence summary of the track's journey.
*   **Provider Extensibility**: Supports **Google Gemini** (multimodal audio) and **Ollama** (local LLM) via a modular provider architecture.
*   **Docker Ready**: Optimized for Alpine-based Beets containers (like `beets-flask`).
*   **Auto-Import**: Automatically enriches tracks during the `beet import` process.

## Installation

### 1. Dependencies
Ensure `ffmpeg` is installed on your system. 

```bash
pip install google-genai beets
```

### 2. Plugin Setup
Copy `enricher.py` to your Beets plugin directory. In your `config.yaml`, add the plugin path:

```yaml
pluginpath: [/path/to/plugins]
plugins: enricher

enricher:
    auto: yes                   # Run during import
    provider: gemini            # 'gemini' or 'ollama'
    model: gemini-1.5-pro       # Gemini model string
    api_key: ${GEMINI_API_KEY}  # Your Google AI Studio API Key
```

## Docker Integration (e.g., beets-flask)

### Dockerfile
Add the following to your `Dockerfile`:
```dockerfile
RUN apk add --no-cache ffmpeg
RUN pip install google-genai beets
```

### docker-compose.yml
Ensure the plugin is mounted and the API key is passed:
```yaml
services:
  beets:
    environment:
      - GEMINI_API_KEY=your_key_here
    volumes:
      - ./enricher.py:/config/plugins/enricher.py
      - ./tmp:/tmp/beets  # Used for temporary audio samples
```

## Usage

### Automatic
If `auto: yes` is set in your config, enrichment happens automatically during `beet import`.

### Manual
Enrich specific tracks or albums manually:
```bash
# Enrich a specific album
beet enrich album:"Dark Side of the Moon"

# Enrich everything by an artist
beet enrich artist:"Pink Floyd"
```

## Metadata Storage
The plugin stores analysis in two places:
1.  **Comments Tag**: Appends a readable summary to the standard comments metadata.
2.  **Flexible Attribute**: Stores the full JSON response in the `ai_summary` field (accessible via `beet ls -f '$ai_summary'`).

## Local LLM (Ollama)
To use a local model, switch the provider in your config:
```yaml
enricher:
    provider: ollama
    ollama_url: http://localhost:11434/api/generate
    model: your-multimodal-model
```
*Note: Audio analysis in Ollama requires a multimodal model capable of processing audio or a pre-processing transcription pipeline.*

## License
MIT
