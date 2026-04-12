# Supported LLM Models

This project uses local LLMs to generate narration scripts (audiobook) and conversational dialogue (podcast) from source text. Models are selected for **strong instruction following**, **long context windows**, **creative writing quality**, and **multilingual support**.

Two backends are supported:

- **Ollama** — runs locally or on a remote server; works on any GPU (NVIDIA, Apple Silicon)
- **MLX** — Apple Silicon only; loads 4-bit quantized models directly in unified memory

## Model Families

### Qwen 3.5 (Recommended)

The latest generation from Alibaba's Qwen team (February 2026). All Qwen 3.5 models share a **262K native context window** (extensible to ~1M tokens), a major upgrade from Qwen 3's 40K on dense models.

| Model ID | Backend | Type | Total Params | Active Params | Context | VRAM (approx) |
|---|---|---|---|---|---|---|
| `qwen3.5:35b-a3b` | Ollama | MoE | 35B | 3B | 262K | ~8 GB (Q4) |
| `qwen3.5:27b` | Ollama | Dense | 27B | 27B | 262K | ~16 GB (Q4) |
| `qwen3.5:9b` | Ollama | Dense | 9B | 9B | 262K | ~6 GB (Q4) |
| `mlx-community/Qwen3.5-35B-A3B-4bit` | MLX | MoE | 35B | 3B | 262K | ~8 GB |
| `mlx-community/Qwen3.5-27B-4bit` | MLX | Dense | 27B | 27B | 262K | ~16 GB |
| `mlx-community/Qwen3.5-9B-MLX-4bit` | MLX | Dense | 9B | 9B | 262K | ~6 GB |

**Advantages:**

- **Best-in-class context window** — 262K tokens natively means entire book chapters fit in a single prompt, reducing the need to split content and improving narration coherence
- **MoE efficiency** — the 35B-A3B variant activates only 3B parameters per token (256 experts, 8 routed + 1 shared), delivering quality comparable to much larger dense models at a fraction of the compute cost
- **Excellent instruction following** — Qwen 3.5 models are trained with extensive RLHF and show strong adherence to formatting instructions, crucial for structured narration and dialogue output
- **Multilingual** — strong performance across 100+ languages, enabling high-quality cross-language narration (e.g., English PDF to French audiobook)
- **Multimodal foundation** — trained with vision capabilities, which contributes to richer text understanding

**Recommended pick:** `mlx-community/Qwen3.5-35B-A3B-4bit` (MLX) or `qwen3.5:35b-a3b` (Ollama) — the MoE architecture gives you 35B-level quality with 3B-level speed and memory usage. This is the default in the project configs.

---

### Qwen 3

The previous generation. Still solid, but superseded by Qwen 3.5 for new setups.

| Model ID | Backend | Type | Total Params | Active Params | Context | VRAM (approx) |
|---|---|---|---|---|---|---|
| `qwen3:32b` | Ollama | Dense | 32B | 32B | 40K | ~20 GB (Q4) |
| `qwen3:14b` | Ollama | Dense | 14B | 14B | 40K | ~10 GB (Q4) |
| `qwen3:8b` | Ollama | Dense | 8B | 8B | 40K | ~6 GB (Q4) |
| `qwen3:30b-a3b` | Ollama | MoE | 30B | 3B | 262K | ~8 GB (Q4) |
| `Qwen/Qwen3-32B-MLX-4bit` | MLX | Dense | 32B | 32B | 40K | ~20 GB |
| `Qwen/Qwen3-14B-MLX-4bit` | MLX | Dense | 14B | 14B | 40K | ~10 GB |
| `Qwen/Qwen3-8B-MLX-4bit` | MLX | Dense | 8B | 8B | 40K | ~8 GB |
| `Qwen/Qwen3-30B-A3B-MLX-4bit` | MLX | MoE | 30B | 3B | 262K | ~8 GB |

**Advantages:**

- **Proven and stable** — well-tested in this project since launch
- **Wide availability** — available on every inference platform
- **MoE variant** — `qwen3:30b-a3b` offers the same 262K context and MoE efficiency as Qwen 3.5's 35B-A3B

**Limitations:**

- Dense models are capped at 40K context — for long chapters, the pipeline must split content into smaller sections, which can break narrative flow
- Qwen 3.5 offers measurably better instruction following and creative writing quality

---

### Gemma 4

Google DeepMind's latest open model family (April 2026). Strong reasoning capabilities with configurable thinking modes.

| Model ID | Backend | Type | Total Params | Active Params | Context | VRAM (approx) |
|---|---|---|---|---|---|---|
| `gemma4:26b` | Ollama | MoE | 26B | 4B | 256K | ~10 GB (Q4) |
| `gemma4:31b` | Ollama | Dense | 31B | 31B | 256K | ~18 GB (Q4) |
| `unsloth/gemma-4-26b-a4b-it-UD-MLX-4bit` | MLX | MoE | 26B | 4B | 256K | ~10 GB |
| `unsloth/gemma-4-31b-it-UD-MLX-4bit` | MLX | Dense | 31B | 31B | 256K | ~18 GB |

**Advantages:**

- **Large context window** — 256K tokens, on par with Qwen 3.5
- **Strong reasoning** — configurable thinking mode allows the model to "think step by step" before generating output, which can improve narration quality for complex source material
- **MoE efficiency** — the 26B-A4B variant activates only 4B parameters, making it fast and memory-friendly
- **Multilingual** — supports 140+ languages
- **Apache 2.0 license** — maximally permissive for any use case

**Considerations:**

- Gemma 4 is newer to this project and less tested than the Qwen family
- The Ollama and MLX model IDs are longer/less ergonomic than Qwen equivalents

---

### Mistral

Mistral AI's instruction-tuned models. Reliable workhorses with 128K context.

| Model ID | Backend | Type | Total Params | Active Params | Context | VRAM (approx) |
|---|---|---|---|---|---|---|
| `mistral-small3.2:24b-instruct-2506-q8_0` | Ollama | Dense | 24B | 24B | 128K | ~24 GB (Q8) |
| `mistral-nemo` | Ollama | Dense | 12B | 12B | 128K | ~8 GB (Q4) |
| `mlx-community/Mistral-Small-3.2-24B-Instruct-2506-4bit` | MLX | Dense | 24B | 24B | 128K | ~14 GB |
| `mlx-community/Mistral-Nemo-Instruct-2407-4bit` | MLX | Dense | 12B | 12B | 128K | ~8 GB |

**Advantages:**

- **Solid 128K context** — handles most chapters comfortably
- **Low repetition** — Mistral Small 3.2 produces half the repetitive/infinite generations compared to its predecessor
- **Strong function calling** — robust structured output, useful for the pipeline's formatting requirements
- **Apache 2.0 license** — fully permissive

**Considerations:**

- 128K context is half that of Qwen 3.5 / Gemma 4 — very long chapters may still need splitting
- Creative writing quality is generally a step below Qwen 3.5 for narration tasks

---

## Choosing a Model

### By hardware

| Hardware | Recommended Model |
|---|---|
| Apple Silicon, 64 GB unified memory | `mlx-community/Qwen3.5-35B-A3B-4bit` (MLX) |
| Apple Silicon, 32 GB unified memory | `mlx-community/Qwen3.5-9B-MLX-4bit` or `unsloth/gemma-4-26b-a4b-it-UD-MLX-4bit` (MLX) |
| Apple Silicon, 16 GB unified memory | `mlx-community/Qwen3.5-9B-MLX-4bit` (MLX) |
| NVIDIA GPU, 24+ GB VRAM | `qwen3.5:27b` or `gemma4:31b` (Ollama) |
| NVIDIA GPU, 12-16 GB VRAM | `qwen3.5:35b-a3b` or `gemma4:26b` (Ollama) |
| NVIDIA GPU, 8 GB VRAM | `qwen3.5:9b` (Ollama) |

### By use case

| Priority | Recommended Model | Why |
|---|---|---|
| Best quality (long documents) | `qwen3.5:35b-a3b` | 262K context + MoE efficiency |
| Best quality (short documents) | `qwen3.5:27b` | Dense 27B gives maximum coherence |
| Fastest inference | `qwen3.5:35b-a3b` or `gemma4:26b` | MoE activates only 3-4B params |
| Lowest memory | `qwen3.5:9b` | ~6 GB at 4-bit quantization |
| Cross-language narration | `qwen3.5:35b-a3b` | Best multilingual quality |
| Alternative ecosystem | `gemma4:26b` | Google's strongest open MoE |

---

## Models NOT Included (and Why)

| Model | Reason for exclusion |
|---|---|
| **Phi-4 (14B)** | 16K context window is far too small for processing book chapters — would require aggressive content splitting |
| **Gemma 4 E2B / E4B** | 128K context and small parameter counts (2-4B) produce lower quality narration than the larger models |
| **Qwen 3.5 0.8B / 2B / 4B** | Too small for high-quality narration or dialogue generation — fine for classification but not creative writing |
| **Llama 3.x** | Competitive but less strong than Qwen 3.5 for multilingual creative writing; 128K context |

---

## How Context Windows Affect the Pipeline

The `context_budget` function in [loader.py](../../scripts/configs/loader.py) calculates how much source text can be processed per LLM call:

```
budget = (context_window - system_prompt_tokens) / 2
```

The division by 2 reserves half the context for the model's output. With a 262K context model, each section can process ~131K tokens of source text — enough for most book chapters in a single pass. With a 40K context model, sections are limited to ~20K tokens, which may require splitting longer chapters.

| Context Window | Per-Section Budget | Typical Chapter Coverage |
|---|---|---|
| 262K (Qwen 3.5, Gemma 4) | ~131K tokens | Full chapter in one pass |
| 128K (Mistral) | ~64K tokens | Most chapters in one pass |
| 40K (Qwen 3 dense) | ~20K tokens | May need splitting |
