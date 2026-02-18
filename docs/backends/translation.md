# Translation

Both pipelines can read a document in one language and produce audio in another. The LLM translates and adapts the content in a single pass — no separate translation step required.

## Configuration

Set `source_lang` (language of the input) and `target_lang` (language of the output):

| Field | Audiobook (`NarrationConfig`) | Podcast (`DialogueConfig`) |
|-------|-------------------------------|----------------------------|
| `source_lang` | Language of the input PDF/URL | Language of the input PDF/URL |
| `target_lang` | Language of the narration output | Language of the dialogue output |

Both default to `"en"`.

## How translation works

The LLM adapts its behaviour based on the language pair:

| Scenario | What the LLM does |
|---|---|
| `source_lang == target_lang == "en"` | No extra instruction — prompts are already in English |
| `source_lang == target_lang` (non-English) | Writes all output in `target_lang` |
| `source_lang != target_lang` | Translates and adapts the source material into `target_lang` |

The TTS backend then renders the translated output using voices matched to `target_lang` (see [TTS Backends — Language coverage](tts_backends.md#language-coverage)).

Both pipelines support **any language pair** the LLM can handle. They append a dynamic instruction to the base English prompt:

> *"The source material is written in {source_lang}. Write ALL output in {target_lang}, translating and adapting the content naturally."*

Any combination works — English to Japanese, French to Chinese, etc. — as long as the LLM is capable and a TTS backend supports the target language.

## Examples

### English PDF → French podcast

```python
config = PodcastConfig(
    dialogue=DialogueConfig(source_lang="en", target_lang="fr"),
    llm=OllamaLLM(...),
)
# LLM reads English, generates French dialogue
# TTS auto-selects French voices
```

### French PDF → English audiobook

```python
config = AudiobookConfig(
    narration=NarrationConfig(source_lang="fr", target_lang="en"),
    llm=OllamaLLM(...),
)
# LLM reads French, generates English narration
# TTS auto-selects English voices
```

### Japanese PDF → Japanese podcast

```python
config = PodcastConfig(
    dialogue=DialogueConfig(source_lang="ja", target_lang="ja"),
    llm=OllamaLLM(...),
)
# LLM writes all output in Japanese
# TTS auto-selects Japanese voices
```

### English PDF → Chinese podcast with Chatterbox

```python
config = PodcastConfig(
    dialogue=DialogueConfig(source_lang="en", target_lang="zh"),
    llm=OllamaLLM(...),
    tts=ChatterboxTTS(lang="zh"),
)
# LLM translates English to Chinese dialogue
# Chatterbox renders with Chinese voices
```

## TTS voice auto-selection

When `tts` is not explicitly set, a `KokoroTTS` backend is created automatically from `target_lang` with voices from `KOKORO_VOICE_PRESETS`. To use a different backend or custom voices, pass an explicit `tts=` — see [TTS Backends](tts_backends.md) for all options.
