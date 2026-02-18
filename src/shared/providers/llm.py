"""LLM backend configurations and unified generate function.

Shared across audiobook and podcast pipelines.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass

import requests

# Strip <think>…</think> blocks emitted by reasoning models (e.g. Qwen3)
_THINK_RE = re.compile(r"<think>.*?</think>\s*", re.DOTALL)


# ---------------------------------------------------------------------------
# Backend configs — one class per provider
# ---------------------------------------------------------------------------


@dataclass
class OllamaLLM:
    model: str = "qwen3:14b"
    url: str = "http://localhost:11434"
    num_ctx: int = 40960
    temperature: float = 0.7
    timeout: int = 600                          # request timeout in seconds
    num_predict: int = -1                       # max output tokens (-1 = unlimited)
    top_k: int | None = None                    # top-k sampling
    top_p: float | None = None                  # nucleus sampling
    repeat_penalty: float | None = None
    stop: list[str] | None = None               # stop sequences


@dataclass
class MLXLLM:
    """Run HuggingFace models locally on Apple Silicon via mlx-lm.

    - model: any HF repo with MLX weights (e.g. "Qwen/Qwen3-14B-MLX-4bit").
      Downloaded on first use, cached in ~/.cache/huggingface/ afterward.
    - The model stays loaded in memory across all calls within a run
      (no reload per section).
    - No context-window parameter — mlx-lm uses as much unified memory as
      available.  max_tokens controls *output* length only.
    """

    model: str = "Qwen/Qwen3-14B-MLX-4bit"
    max_tokens: int = 8192
    temperature: float = 0.7


# Union type for type hints
LLMBackend = OllamaLLM | MLXLLM


# ---------------------------------------------------------------------------
# Language instruction — shared by audiobook and podcast pipelines
# ---------------------------------------------------------------------------


def language_instruction(source_lang: str, target_lang: str) -> str:
    """Build a language instruction to append to LLM system prompts.

    Returns empty string when both source and target are English (no extra
    instruction needed since prompts are already in English).
    """
    if source_lang == target_lang == "en":
        return ""
    if source_lang == target_lang:
        return f"\nIMPORTANT: Write ALL output in {target_lang}."
    return (
        f"\nIMPORTANT: The source material is written in {source_lang}. "
        f"Write ALL output in {target_lang}, translating and adapting "
        f"the content naturally."
    )


# ---------------------------------------------------------------------------
# Unified generation — dispatches on config type
# ---------------------------------------------------------------------------


def llm_generate(system: str, prompt: str, llm: LLMBackend) -> str:
    """Generate text from an LLM using the configured backend."""
    if isinstance(llm, OllamaLLM):
        return _ollama_generate(system, prompt, llm)
    elif isinstance(llm, MLXLLM):
        return _mlx_generate(system, prompt, llm)
    else:
        raise TypeError(f"Unknown LLM config type: {type(llm)}")


# ---------------------------------------------------------------------------
# Ollama preflight & retry helpers
# ---------------------------------------------------------------------------

# Tracks already-verified (url, model) pairs — preflight runs once per combo
_ollama_verified: set[tuple[str, str]] = set()

_OLLAMA_MAX_RETRIES = 3
_OLLAMA_BACKOFF_BASE = 2  # seconds; backoff = base ** (attempt * 2)


def ollama_preflight(llm: OllamaLLM) -> None:
    """Verify Ollama is reachable and the requested model is available.

    Results are cached — only the first call per (url, model) pair does work.
    """
    key = (llm.url, llm.model)
    if key in _ollama_verified:
        return

    # 1. Check connectivity
    try:
        resp = requests.get(f"{llm.url}/api/tags", timeout=10)
        resp.raise_for_status()
    except requests.ConnectionError as exc:
        raise RuntimeError(
            f"Ollama not reachable at {llm.url} — is it running? (`ollama serve`)"
        ) from exc
    except requests.Timeout as exc:
        raise RuntimeError(
            f"Ollama at {llm.url} timed out on health check — is it overloaded?"
        ) from exc
    except requests.HTTPError as exc:
        raise RuntimeError(
            f"Ollama health check failed (HTTP {exc.response.status_code}): "
            f"{exc.response.text[:500]}"
        ) from exc
    except requests.RequestException as exc:
        raise RuntimeError(
            f"Ollama not reachable at {llm.url}: {exc}"
        ) from exc

    # 2. Validate model is available
    available = [m["name"] for m in resp.json().get("models", [])]
    # Ollama tags can be "model:tag" — match with or without ":latest"
    model_matches = (
        llm.model in available
        or f"{llm.model}:latest" in available
        or any(a.startswith(f"{llm.model}:") for a in available)
    )
    if not model_matches:
        names = ", ".join(available) if available else "(none)"
        raise RuntimeError(
            f"Model '{llm.model}' not found. Available: [{names}]. "
            f"Pull it with `ollama pull {llm.model}`"
        )

    _ollama_verified.add(key)


def _ollama_generate(system: str, prompt: str, llm: OllamaLLM) -> str:
    ollama_preflight(llm)

    # Build options dict — only include non-None optional fields
    options: dict = {
        "temperature": llm.temperature,
        "num_ctx": llm.num_ctx,
    }
    if llm.num_predict != -1:
        options["num_predict"] = llm.num_predict
    if llm.top_k is not None:
        options["top_k"] = llm.top_k
    if llm.top_p is not None:
        options["top_p"] = llm.top_p
    if llm.repeat_penalty is not None:
        options["repeat_penalty"] = llm.repeat_penalty

    payload: dict = {
        "model": llm.model,
        "system": system,
        "prompt": prompt,
        "stream": False,
        "options": options,
    }
    if llm.stop is not None:
        payload["stop"] = llm.stop

    last_exc: Exception | None = None
    for attempt in range(1, _OLLAMA_MAX_RETRIES + 1):
        try:
            response = requests.post(
                f"{llm.url}/api/generate",
                json=payload,
                timeout=llm.timeout,
            )
            # Handle HTTP errors with useful context
            if response.status_code >= 500:
                body = response.text[:500]
                raise requests.HTTPError(
                    f"Ollama returned HTTP {response.status_code} "
                    f"(model={llm.model}): {body}",
                    response=response,
                )
            if response.status_code >= 400:
                body = response.text[:500]
                raise RuntimeError(
                    f"Ollama request failed (HTTP {response.status_code}, "
                    f"model={llm.model}): {body}"
                )
            return _THINK_RE.sub("", response.json()["response"])

        except (requests.ConnectionError, requests.Timeout) as exc:
            last_exc = exc
        except requests.HTTPError as exc:
            if exc.response is not None and exc.response.status_code >= 500:
                last_exc = exc
            else:
                raise  # 4xx errors are not retryable

        # Exponential backoff before retry
        if attempt < _OLLAMA_MAX_RETRIES:
            wait = _OLLAMA_BACKOFF_BASE ** (attempt * 2)  # 4s, 16s
            print(f"  [Ollama] Attempt {attempt}/{_OLLAMA_MAX_RETRIES} failed, "
                  f"retrying in {wait}s...")
            time.sleep(wait)

    raise RuntimeError(
        f"Ollama request failed after {_OLLAMA_MAX_RETRIES} attempts "
        f"(model={llm.model}, url={llm.url}): {last_exc}"
    )


# Cache loaded MLX models (loading is expensive)
_mlx_cache: dict[str, tuple] = {}


def _mlx_generate(system: str, prompt: str, llm: MLXLLM) -> str:
    from mlx_lm import generate, load
    from mlx_lm.sample_utils import make_sampler

    if llm.model not in _mlx_cache:
        _mlx_cache[llm.model] = load(llm.model)
    model, tokenizer = _mlx_cache[llm.model]

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": prompt},
    ]
    formatted = tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True,
    )
    response = generate(
        model, tokenizer,
        prompt=formatted,
        max_tokens=llm.max_tokens,
        sampler=make_sampler(temp=llm.temperature),
        verbose=False,
    )
    return _THINK_RE.sub("", response)
