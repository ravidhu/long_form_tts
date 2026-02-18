# Troubleshooting

## Ollama

### "Ollama not reachable at http://localhost:11434 — is it running?"

The pipeline runs a preflight check at startup to verify Ollama is running. If you see this error:

1. Start Ollama: `ollama serve`
2. Or if using a custom URL, check the `url` field in your `OllamaLLM(url=...)` config

### "Model 'xyz' not found. Available: [...]. Pull it with `ollama pull xyz`"

The model specified in your config isn't downloaded yet. Pull it:

```bash
ollama pull qwen3:14b
```

The preflight check lists all available models so you can see what's installed.

### "Ollama request failed after 3 attempts"

The request to Ollama failed even after retries. Common causes:

- **Ollama crashed mid-run** — restart with `ollama serve` and resume the pipeline (same `--output` directory)
- **Out of memory** — the model is too large for your hardware. Try a smaller model (e.g. `qwen3:4b`)
- **Very long section** — increase `timeout` in your `OllamaLLM(timeout=900)` config (default is 600s)

### Ollama is slow

Large sections can take several minutes per LLM call. The default timeout is 600 seconds (10 minutes). If you're running on slower hardware, increase it:

```python
llm = OllamaLLM(model="qwen3:14b", timeout=900)  # 15 minutes
```

## Installation

### `uv sync` fails on `mlx-audio`

MLX requires Apple Silicon. Not supported on Intel Macs or Linux.

## PDF processing

### No TOC found in PDF

If the PDF has no embedded bookmarks, the entire document is treated as one section. Options:

- Use a PDF editor to add bookmarks
- Switch to `MAX_TOC_LEVEL=2` with the docling backend which detects headers via AI layout analysis

## TTS

### TTS model download hangs

Models are downloaded from HuggingFace on first run. Expected sizes:

| Runtime | Model | Size |
|---------|-------|------|
| MLX | `mlx-community/Kokoro-82M-bf16` | ~160 MB |
| MLX | `mlx-community/chatterbox-fp16` | ~2.6 GB |
| PyTorch | `hexgrad/Kokoro-82M` | ~360 MB |
| PyTorch | `ResembleAI/chatterbox` | ~9.6 GB |

Check your internet connection. Models are cached in `~/.cache/huggingface/` after the first download.

### Voice/language mismatch error

The podcast pipeline validates that voice prefixes match `target_lang` at startup. If you see this error, make sure your `KokoroTTS(voices=(...))` uses voices that match the target language. For example, French voices start with `f` (e.g. `ff_siwis`), English voices start with `a` (American) or `b` (British).
