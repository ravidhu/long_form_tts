# Sample PDFs for Testing

Free, legally downloadable PDFs that exercise different aspects of the pipeline.

| # | Book | Pages | Year | Best for testing |
|---|------|-------|------|------------------|
| 1 | [Understanding Deep Learning](https://udlbook.github.io/udlbook/) — Simon J.D. Prince | ~500 | 2024 | Math-heavy, figures, tables, deep TOC (parts/chapters/subsections) |
| 2 | [Foundations of Large Language Models](https://arxiv.org/pdf/2501.09223) — Xiao et al. | ~150 | 2025 | Academic paper format, dense technical content, no embedded TOC |
| 3 | [Software Design by Example (Python)](https://third-bit.com/sdxpy/) — Greg Wilson | ~300 | 2024 | Code-heavy chapters, shell commands, structured TOC |
| 5 | [Handbook of Software Engineering Methods](https://open.oregonstate.education/setextbook/) — Oregon State | ~250 | 2024 | Structured textbook, tables, lists, multi-chapter |
| 6 | [Mathematical Foundation of Reinforcement Learning](https://github.com/MathFoundationRL/Book-Mathematical-Foundation-of-Reinforcement-Learning/blob/main/Book-all-in-one.pdf) — Shiyu Zhao | ~450 | 2024 | Heavy math (Bellman, policy gradient), per-chapter PDFs available, deep TOC |
| 15 | [The Little Book of Deep Learning](https://fleuret.org/public/lbdl.pdf) — François Fleuret | ~185 | 2023 | Rich 3-level TOC (parts/chapters/sections), front matter, compact |

## Research Papers (arXiv)

Iconic papers — tests both embedded TOC and `infer_toc` font-analysis fallback.

| # | Paper | Pages | Year | TOC | Why it's iconic |
|---|-------|-------|------|-----|-----------------|
| 7 | [Attention Is All You Need](https://arxiv.org/pdf/1706.03762) — Vaswani et al. | ~15 | 2017 | embedded | Introduced the Transformer architecture |
| 8 | [BERT](https://arxiv.org/pdf/1810.04805) — Devlin et al. | ~16 | 2018 | — | Pre-train/fine-tune paradigm for NLP (masked LM) |
| 9 | [Language Models are Few-Shot Learners (GPT-3)](https://arxiv.org/pdf/2005.14165) — Brown et al. | ~75 | 2020 | embedded | 175B params, few-shot without fine-tuning |
| 10 | [Deep Residual Learning (ResNet)](https://arxiv.org/pdf/1512.03385) — He et al. | ~12 | 2015 | — | Skip connections, 100+ layer networks |
| 11 | [An Image is Worth 16x16 Words (ViT)](https://arxiv.org/pdf/2010.11929) — Dosovitskiy et al. | ~22 | 2020 | — | Pure Transformer for image classification |
| 12 | [NodeRAG](https://arxiv.org/pdf/2504.11544) — Xu et al. | ~20 | 2025 | — | Heterogeneous graph-based RAG framework |
| 13 | [AlexNet](https://papers.nips.cc/paper/2012/file/c399862d3b9d6b76c8436e924a68c45b-Paper.pdf) — Krizhevsky et al. | ~9 | 2012 | **none** | Deep CNNs for ImageNet, launched modern deep learning |
| 14 | [Adam Optimizer](https://arxiv.org/pdf/1412.6980) — Kingma & Ba | ~15 | 2014 | **none** | Default optimizer for most deep learning |

## What each tests

- **Math & equations**: #1 (Understanding Deep Learning), #6 (Math Foundation of RL)
- **Code blocks & shell commands**: #3 (Software Design by Example)
- **Zero embedded TOC (pure `infer_toc`)**: #13 (AlexNet), #14 (Adam) — tests font-analysis fallback end-to-end
- **Research papers with embedded TOC**: #7 (Transformer), #9 (GPT-3) — tests embedded TOC on short/long papers
- **Academic/arXiv format**: #2 (Foundations of LLMs), #8, #10–#12 — various paper formats
- **Rich embedded TOC (3 levels)**: #15 (Little Book of DL) — tests extract_toc, front matter classification, resolve_content_sections at level 1 and 2
- **Structured textbook**: #5 (Handbook of SE Methods) — tests cross-chapter coherence
- **Large document handling**: #1 (500+ pages) — tests auto-subdivision and context budget
- **Short documents**: #7, #8, #10 (~12–16 pages) — tests handling of compact single-section papers

## Licenses

| Book / Paper | License |
|------|---------|
| Understanding Deep Learning | MIT Press, free PDF from author |
| Foundations of LLMs | arXiv open access |
| Software Design by Example | CC-BY-NC |
| Handbook of SE Methods | CC-BY-NC |
| Math Foundation of RL | Free PDF from author (Springer published version separate) |
| Research papers (#7–#12, #14) | arXiv open access (non-exclusive license to distribute) |
| AlexNet (#13) | NeurIPS proceedings, open access |
| Little Book of Deep Learning (#15) | Free PDF from author |
