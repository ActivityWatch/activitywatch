# aw-watcher-categorize

**aw-watcher-categorize** is an intelligent automated categorization watcher and rule learner for [ActivityWatch](https://activitywatch.net/).

It analyzes your active desktop and browser activity in real-time or in batch history mode, leveraging built-in heuristics and AI models (via OpenAI, Ollama, Google Gemini, Anthropic Claude, or local LLMs) to classify uncategorized events and automatically generate robust category rules.

---

## Features

- ⚡ **Real-time Categorization**: Emits continuous heartbeats into the `aw-watcher-categorize_<hostname>` bucket with category hierarchies and confidence scores.
- 🤖 **Multi-Provider AI API Integration**:
  - **OpenAI & OpenAI-Compatible**: OpenAI (GPT-4o / GPT-4o-mini), Groq, DeepSeek, OpenRouter, LocalAI, vLLM.
  - **Local Ollama**: Works 100% locally and privately without requiring an external API key (`http://localhost:11434/v1`).
  - **Google Gemini API**: Native Gemini REST API support (`gemini-1.5-flash`, `gemini-2.0-flash`).
  - **Anthropic Claude API**: Claude models (`claude-3-5-haiku`, `claude-3-5-sonnet`).
- 📚 **Built-in Offline Knowledge Base**: Pre-loaded with hundreds of heuristics for popular IDEs, tools, communication apps, streaming services, social media, and games.
- 🎯 **Batch Rule Synthesizer (`--learn`)**: Scans past uncategorized events, summarizes them by duration, and prompts AI to generate high-quality regex rules directly into ActivityWatch's server settings.
- 🔄 **Auto-Rule Learning**: Optional `--auto-update` mode to automatically append newly discovered AI rules to `aw-server` on the fly.

---

## Installation

Within the `activitywatch` workspace:

```bash
cd aw-watcher-categorize
poetry install
```

---

## Usage

### 1. Real-Time Watcher Mode

Run the watcher in the background alongside `aw-watcher-window`:

```bash
# Using OpenAI (requires OPENAI_API_KEY environment variable or config)
poetry run aw-watcher-categorize

# Using Local Ollama (100% local, offline, private)
poetry run aw-watcher-categorize --ai-provider ollama --ai-base-url http://localhost:11434/v1 --ai-model llama3

# Using Google Gemini API
poetry run aw-watcher-categorize --ai-provider gemini --ai-api-key YOUR_GEMINI_API_KEY --ai-model gemini-1.5-flash

# Using Anthropic Claude API
poetry run aw-watcher-categorize --ai-provider anthropic --ai-api-key YOUR_ANTHROPIC_KEY --ai-model claude-3-5-haiku-20241022
```

### 2. Batch Rule Learning Mode (`--learn`)

Inspect your uncategorized events from the past 7 days and generate regex category rules:

```bash
poetry run aw-watcher-categorize --learn --learn-days 7
```

To automatically apply and save the generated rules to the ActivityWatch server settings:

```bash
poetry run aw-watcher-categorize --learn --learn-days 7 --apply
```

---

## Configuration

Configuration is managed via TOML in `~/.config/activitywatch/aw-watcher-categorize/aw-watcher-categorize.toml`:

```toml
[aw-watcher-categorize]
poll_time = 5.0
enable_heuristics = true
auto_update_classes = false
min_confidence_to_learn = 0.85

# AI Provider Settings
# Options: "openai_compatible", "ollama", "gemini", "anthropic", "offline"
ai_provider = "openai_compatible"
ai_api_key = ""
ai_base_url = "https://api.openai.com/v1"
ai_model = "gpt-4o-mini"
```

---

## CLI Options

| Flag | Description | Default |
|------|-------------|---------|
| `--poll-time` | Heartbeat polling interval in seconds | `5.0` |
| `--ai-provider` | Provider (`openai`, `ollama`, `gemini`, `anthropic`, `offline`) | `openai_compatible` |
| `--ai-api-key` | API Key for cloud providers | Environment variables |
| `--ai-base-url` | Base URL for OpenAI/Ollama endpoints | `https://api.openai.com/v1` |
| `--ai-model` | Model name | `gpt-4o-mini` |
| `--no-heuristics` | Disable offline heuristics database | `false` |
| `--auto-update` | Auto-save high-confidence AI rules to server | `false` |
| `--learn` | Run batch historical analysis and exit | `false` |
| `--learn-days` | Number of days to inspect in `--learn` mode | `7` |
| `--apply` | Apply learned rules to server without prompt | `false` |
| `--testing` | Connect to testing server port | `false` |
| `--verbose` | Enable debug logging | `false` |

---

## License

MPL-2.0
