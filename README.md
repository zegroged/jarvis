# Jarvis

> A Turkish-speaking security and software engineering assistant that runs entirely on local hardware: a tool-using agent loop over an open-weights LLM, a hybrid retrieval layer with cross-encoder reranking, and a 523-document Turkish technical corpus.

![Python](https://img.shields.io/badge/Python-3.12-blue)
![PyTorch](https://img.shields.io/badge/PyTorch-CUDA%2012.8-ee4c2c)
![Runtime](https://img.shields.io/badge/LLM%20runtime-llama.cpp%20(GGUF)-lightgrey)
![License](https://img.shields.io/badge/License-MIT-green)
![Status](https://img.shields.io/badge/Status-research%20project-orange)

There is no hosted demo. The whole system runs offline against a GGUF model file on disk, and the model weights (~14 GB) are not stored in this repository — see [Getting started](#getting-started).

Turkish README: [README.tr.md](README.tr.md) (original, kept for reference).

---

**How this was built:** the code was written with AI assistance and reviewed by the author.

## Overview

Small local models are cheap to run and hard to make useful. A 7B model quantized to fit in 6 GB of VRAM will happily hallucinate a security recommendation, call the same tool five times in a row, or drift out of its own JSON format halfway through a task. **Jarvis is an attempt to make a 7B model do real work anyway — not by making the model smarter, but by building the harness around it.** The intelligence is deliberately pushed out of the weights and into the tool layer, the retrieval layer, and the control loop.

The system has three working parts. An **agent runtime** (`src/jarvis_agent.py`, 805 lines) exposes 18 tools — shell execution, file I/O, static analysis, dependency CVE audit, secret scanning, TLS and HTTP header checks, log triage — and drives a think/act/observe loop with an approval gate for destructive operations, loop detection, a hard tool budget, context-window trimming, and forced answer synthesis when the model gets stuck. A **hybrid retrieval layer** (`src/rag.py`) blends dense multilingual embeddings with BM25, pulls 30 candidates, reranks them with a cross-encoder, and blends the reranker score back into the hybrid score — with a graceful degradation chain so it still returns results when the reranker or the embedding model is missing. A **Turkish technical corpus** (`bilgi_hazinesi/`, 523 Markdown documents, ~10 MB) covers security and software engineering in a language where high-quality open-source domain text is genuinely scarce.

A fourth part is honest scaffolding rather than a product: a from-scratch GPT implementation, a Turkish BPE tokenizer, and an instruction fine-tuning loop with loss masking. It was written to learn how the pieces fit together. It is documented at the bottom of this README, under [Learning foundation](#learning-foundation), with a clear statement of what it does and does not do.

The project was built and tested on a single consumer laptop: RTX 3050 Laptop (6 GB VRAM), 16 GB RAM, Windows 11, Python 3.12. Nearly every design decision in it is a consequence of that constraint.

---

## Defensive-security scope

The `bilgi_hazinesi/` corpus contains Turkish-language security material written in the OWASP / MITRE ATT&CK tradition: **concept → observable artifact → detection → mitigation.** Automated scanners may flag directory and file names such as `process-injection`, `persistence`, `amsi-etw-tamper`, or `post-exploitation` — this section exists so that a human reviewer has the context those scanners lack.

What the corpus actually contains, verifiable by reading it:

- **Detection engineering, not operations.** The 68 documents under `bilgi_hazinesi/tespit/` are structured around telemetry sources (Sysmon event IDs, Windows Security log, EDR traces) and are anchored to **106 real SigmaHQ rules, cited by rule ID**. 49 of those appear across the corpus as complete Sigma YAML blocks; the rest are walked through clause by clause in Turkish — logsource, selection, condition — so the reader learns why the rule fires. The offensive technique is described conceptually so the defender knows what artifacts to hunt for.
- **Explicit framing in the documents themselves.** Red-team and DFIR methodology files open with a scope statement — for example, `dfir_kirmizi/guvenlik/post-exploitation-metodoloji.md` states that it is a methodology and judgment document for authorized security testing, not an attack recipe.
- **No weaponized code and no real infrastructure.** Code blocks are vulnerable-code examples, detection queries, Sigma rules, and hardening configuration. A scan of all 523 documents for IPv4 literals returns only non-routable, documentation, or well-known public-service addresses: RFC 1918 private ranges (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`), loopback, RFC 5737 documentation ranges (`192.0.2.0`, `198.51.100.0`, `203.0.113.0`), the cloud metadata address `169.254.169.254`, LLMNR and mDNS multicast, transparent placeholders (`1.2.3.4`, `6.6.6.6`), and public DNS resolvers (`8.8.8.8`, `1.1.1.1`). There are no command-and-control hosts and no real indicators of compromise.
- **Balanced coverage.** Mitigation, defense, and hardening sections and detection or threat-hunting sections appear in comparable numbers — roughly 700 headings each, out of about 9,700 section headings across the corpus.

The agent's system prompt also instructs the model to stay defense-oriented and to ground security answers in the knowledge base rather than improvising.

---

## Tech stack

| Layer | Choice |
| --- | --- |
| LLM runtime | `llama-cpp-python` (CUDA build), Qwen2.5-Coder-7B-Instruct GGUF Q4_K_M (~4.7 GB), partial GPU offload |
| Agent | Plain Python — no LangChain, no agent framework; loop, tool registry, and parsing hand-written |
| Retrieval — lexical | `rank_bm25` (BM25Okapi) |
| Retrieval — dense | `multilingual-e5-base` (falls back to `e5-small`) via `transformers`, CPU |
| Retrieval — reranking | `bge-reranker` cross-encoder via `transformers`, CPU |
| From-scratch model | PyTorch (CUDA 12.8), `tokenizers` for byte-level BPE |
| Fine-tuning | PyTorch training loop; QLoRA path via `peft` + `bitsandbytes` |
| Security tooling | `bandit` (static analysis), `pip-audit` (dependency CVEs), both shelled out |
| Platform | Windows 11, PowerShell, Python 3.12 |

---

## Features

### Tool-using agent — `src/jarvis_agent.py`

An 805-line agent runtime with **18 registered tools** in four groups:

| Group | Tools |
| --- | --- |
| Core | `komut_calistir` (PowerShell) · `dosya_oku` · `dosya_yaz` · `dizin_listele` · `dosya_ara` · `python_calistir` |
| Security | `guvenlik_tara` (bandit) · `bagimlilik_denetle` (pip-audit) · `sir_ara` (secret scanning, 6 patterns) · `port_tara` · `hash_tanimla` · `base_coz` · `http_baslik_denetle` · `ssl_denetle` · `guvenli_parola_uret` · `dosya_hash` |
| Knowledge | `bilgi_ara` (hybrid RAG over the indexed documentation) |
| Blue team | `log_analiz` (7 IOC pattern families over a log file) |

The model returns a single JSON object per turn — either a tool call or a final answer — and the runtime executes it, feeds the result back, and continues. Tool outputs are masked before display where relevant: `sir_ara` reports the file, line, and pattern name for every hit but redacts the matched secret itself.

### Hybrid retrieval — `src/rag.py`, `src/rag_kur.py`, `src/rag_embed_kur.py`

Two-stage retrieval over documentation harvested from upstream repositories. Two source lists are involved and they are not the same list, which is worth stating plainly:

- `src/kaynak_indir.py` clones **55 repositories** (28 security, 27 software) and packs their text files into `data/raw/`.
- `src/rag_kur.py` declares the **23 archives plus MITRE ATT&CK** that are actually chunked into the index: OWASP CheatSheets / WSTG / ASVS / MASTG / Top10 / API-Security, PayloadsAllTheThings, InternalAllTheThings, HackTricks, h4cker, the book of secret knowledge, the nginx admins handbook, Kubernetes docs, CPython `Doc/*.rst`, FastAPI, Django, the Rust book, Go `doc/`, .NET docs, You-Dont-Know-JS, the system design primer, javascript-algorithms, and TheAlgorithms.

Several archives on the second list are fetched by `src/prepare_data.py`, not by `kaynak_indir.py` — see [Known limitations](#known-limitations).

1. **Candidate generation** — dense cosine similarity from a multilingual e5 embedding and BM25 lexical scores are min-max normalized and blended at `0.68 / 0.32`, and the top **30** candidates are pulled.
2. **Reranking** — a `bge-reranker` cross-encoder scores each (query, chunk) pair; the reranker score is min-max normalized and blended back into the hybrid score at `0.35 / 0.65`, and the top 5 are returned.

The index builder strips non-English translation directories and filename language suffixes (so the same OWASP page does not appear 30 times in 30 languages), cleans Markdown and reStructuredText markup, and packs paragraphs into 200–1,400-character chunks on blank-line boundaries.

### Turkish technical corpus — `bilgi_hazinesi/`

523 Markdown documents, ~10 MB, ~1.26 million whitespace-separated words, organized as:

| Directory | Files | Content |
| --- | --- | --- |
| `uretilen/guvenlik` | 211 | Security deep-dives across web, network, AD, cloud, crypto, binary exploitation, forensics |
| `uretilen/yazilim` | 169 | Software engineering: languages, systems, distributed design, testing, performance |
| `tespit/guvenlik` | 68 | Detection engineering, structured around telemetry and Sigma rules |
| `yazilim_pratisyen/yazilim` | 24 | Practitioner decision documents ("which testing strategy, and why") |
| `dfir_kirmizi/guvenlik` | 23 | DFIR and authorized red-team methodology |
| `derin/guvenlik`, `derin/yazilim` | 24 | Long-form treatments of individual vulnerability classes and engineering topics |
| (top level) | 4 | Index and orientation files, including the coverage-gap roadmap |

Coverage is tracked against a taxonomy of **186 topics** (107 security, 79 software) in `uretim_araclari/taksonomi.json`, and `bilgi_hazinesi/YOL_HARITASI_eksikler.md` is a prioritized list of **194 identified coverage gaps** — the corpus knows what it is missing.

### Corpus production pipeline — `uretim_araclari/`

42 Python scripts and 4 JavaScript workflow definitions (~3,400 lines of Python) that produce and quality-screen the corpus:

- **Grounding extractors** pull real source material before generation: CVE records from the harvested corpus (`cve_gronla.py`), Sigma rules from the SigmaHQ repository (`sigma_gronla*.py`), Vulhub lab READMEs (`vulhub_gronla.py`), and Atomic Red Team procedures (`atomic_gronla.py`). Generated articles are anchored to real artifacts rather than written from memory.
- **Quality screening** — `kalite_tara.py` flags documents whose Turkish-diacritic ratio falls below 2% (a reliable signal that ASCII-mangled Turkish crept in) and documents under 4000 characters (truncated generation).
- **Homoglyph normalization** — `homoglyph_tara.py` maps Cyrillic and Azerbaijani visual twins (`а`, `е`, `о`, `с`, `ə`…) back to Latin in question/answer *values only*, preserving JSON structure. Turkish-specific characters have no Cyrillic homoglyph, so the mapping is safe.
- **QA generation and analysis** — scripts that turn corpus sections into Turkish instruction pairs, then split, merge, and audit them.

### Learning foundation

The from-scratch language modeling stack, kept because the reasoning is documented in the code and the exercise was the point:

- `src/model.py` — a GPT implementation (causal self-attention, MLP, residual blocks) with weight tying between the token embedding and the LM head. At 6 layers, 6 heads, 384 embedding dimensions, a 16,384-token vocabulary and a 512-token context, it comes to roughly **17M parameters**.
- `src/train_tokenizer.py` — a byte-level BPE tokenizer trained on Turkish-weighted data, with a token-efficiency report comparing Turkish, code, and security sentences.
- `src/finetune.py` — instruction fine-tuning with **loss masking**: prompt tokens are set to `-1` so the model learns the answer distribution rather than memorizing questions.
- `src/finetune_qlora.py` — a QLoRA path (4-bit NF4, gradient checkpointing, paged 8-bit optimizer, batch size 1 with accumulation) sized for 6 GB of VRAM.

**This is a learning core, not a production model.** A 17M-parameter model trained on a laptop produces broken Turkish. It is not what answers questions in this project; the local 7B does that. It is included because the code is readable and the engineering reasoning is written down, not because the checkpoint is useful.

---

## Architecture / Design notes

**The harness is the product.** A quantized 7B is an unreliable planner. Rather than accept that, the agent loop is built to absorb specific, observed failure modes:

- **Loop detection by call signature.** Each tool call is keyed as `tool_name | sorted-JSON-params`. If the model emits the same signature twice, it gets a corrective message; on the third, the runtime stops arguing and forces a final answer from whatever context has been gathered.
- **Hard tool budget.** Three calls to any single tool, or seven calls total, ends the research phase. Without this, a small model will research indefinitely and never commit to an answer.
- **Forced answer synthesis.** When the budget or the 12-step limit is hit, `_final_cevap_zorla()` appends an explicit instruction to stop calling tools, and falls back to stripping the JSON shell off a plain-text response if the model refuses to emit valid JSON. The user always gets an answer, never a bare "step limit reached".
- **Context trimming as a data-structure operation.** History is capped at 14,000 characters. When it overflows, `_baglam_kirp()` deletes `gecmis[2:4]` — the oldest *(assistant tool-call, user tool-result)* pair, always as a pair, never breaking the alternation. Index 0 (system prompt) and index 1 (the original task) are structurally protected. If the runtime still overflows the context window, `_uret()` catches the error, trims harder, and retries up to three times.
- **Lenient decision parsing.** `json_ayikla()` is a brace-matching scanner that respects string state and escapes, so it extracts a JSON object even when the model wraps it in prose. `_cevap_cek()` accepts the several shapes a small model actually produces for a final answer — `{"cevap": …}`, `{"arac": "final_answer", "parametreler": {…}}`, and variants — instead of a single rigid schema.

**Approval gate as a seam, not a sandbox.** Destructive commands are matched against a regex denylist (`rm`, `format`, `Remove-Item`, `diskpart`, `Stop-Computer`, redirection to `/dev/`…), and overwriting an existing file always prompts. The gate is injected as an `onayci` callable into every tool with a uniform `(params, onayci)` signature, so a tool cannot forget to ask and the policy can be swapped in one place. `--otonom` replaces it with a permissive callable. This is a guard against model error, not against an adversary — see [Known limitations](#known-limitations).

**Graceful degradation, declared explicitly.** `rag.ara()` degrades in a documented chain: reranker present → two-stage retrieval; reranker missing → hybrid top-k; embeddings missing → BM25 alone. Each stage is wrapped so a runtime failure falls through to the weaker method rather than propagating. The number of candidates pulled also adapts — 30 when a reranker exists, `k` when it does not, so no work is wasted generating candidates nothing will rerank.

**Why the reranker score is blended rather than trusted.** The comment in `_rerank()` records the observation that motivated it: a pure cross-encoder ranking sometimes demoted a strong hybrid result — the correct OWASP cheat sheet — below a semantically fluent but less useful chunk. Blending at `0.35 / 0.65` keeps both signals. This is the kind of tuning that only comes from looking at bad results.

**CPU/GPU split by resource pressure.** The embedding model and the cross-encoder are pinned to CPU on purpose: the 7B already owns the 6 GB of VRAM, and the code notes a single e5-small query costs roughly 50 ms on CPU. Splitting the workload across both devices is what makes the whole stack fit on one laptop.

**Model selection without code changes.** `_model_sec()` resolves the model in priority order: the `JARVIS_MODEL` environment variable, then the largest `.gguf` in `models/`, then a default filename. Dropping a 14B GGUF into the directory upgrades the agent with no edit.

**A CUDA DLL workaround worth noting.** `llama-cpp-python`'s CUDA backend looks for `cudart64_12.dll` and `cublas64_12.dll`. Rather than requiring a full CUDA Toolkit install, the code calls `os.add_dll_directory()` on PyTorch's own `lib/` — which already ships those DLLs — *before* importing `llama_cpp`. It removes a multi-gigabyte prerequisite from setup.

**A resumable downloader, because the network is not reliable.** `src/model_indir.py` downloads a 4.7 GB file with HTTP Range requests, appends to a `.part` file, re-reads the on-disk size after every failure (rather than trusting its own counter), retries up to 100 times with exponential backoff capped at 30 s, and verifies the final size before renaming. It exists because unauthenticated HuggingFace downloads kept dropping mid-transfer.

**License-aware `.gitignore`.** Harvested third-party documentation is excluded from the repository with an explicit comment naming the reason: HackTricks is CC BY-NC-SA and OWASP is CC BY-SA, neither of which can be redistributed inside an MIT-licensed repository. The download scripts in `src/` re-fetch it from source instead.

---

## Getting started

**Prerequisites:** Windows 11, Python 3.12, an NVIDIA GPU (6 GB VRAM is enough), git. Roughly 25 GB of free disk for models and harvested corpora.

### 1. Environment

Install PyTorch from the CUDA index **first** — `requirements.txt` also lists `torch`, and letting pip resolve it from PyPI silently installs the CPU-only build.

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install torch --index-url https://download.pytorch.org/whl/cu128
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe src\test_kurulum.py
```

`test_kurulum.py` checks the PyTorch/CUDA install, builds the model and prints its parameter count, runs a complete training step (forward, backward, optimizer) on the GPU to confirm VRAM headroom, and does a generation smoke test.

`requirements.txt` covers only the from-scratch training path. The agent and retrieval stack need additional packages:

```powershell
.venv\Scripts\python.exe -m pip install llama-cpp-python transformers rank_bm25
.venv\Scripts\python.exe -m pip install bandit pip-audit                 # security tools
.venv\Scripts\python.exe -m pip install huggingface_hub datasets pyarrow # data-prep path only
```

### 2. Download the model

Model weights are not in the repository (`models/` is ~14 GB and gitignored).

```powershell
.venv\Scripts\python.exe src\model_indir.py    # Qwen2.5-Coder-7B-Instruct Q4_K_M, resumable
```

To use a different model, point `JARVIS_MODEL` at a GGUF file or drop it in `models/` — the largest file wins.

The retrieval layer additionally expects `models/e5-base` (or `models/e5-small`) and `models/bge-reranker` in HuggingFace format. **There is no download script for these** — place them in `models/` yourself. Without them, retrieval still works and degrades to hybrid or BM25-only, as described in [Design notes](#architecture--design-notes).

### 3. Build the knowledge base

```powershell
.venv\Scripts\python.exe src\kaynak_indir.py   # clone + zip 55 upstream doc repos into data/raw/
.venv\Scripts\python.exe src\rag_kur.py        # BM25 index -> data/processed/guvenlik_rag.pkl
.venv\Scripts\python.exe src\rag_embed_kur.py  # dense embeddings -> guvenlik_rag_embed.npz
```

A fully populated `data/raw/` is around 8.6 GB. `rag_kur.py` skips any archive it cannot find, so it will build an index from whatever is present — but that index will be smaller than the source list implies unless the archives named in the previous section are all in place.

Both index steps are skippable if you only want to read the corpus in `bilgi_hazinesi/`, which is checked into the repository in full.

### 4. Run

```powershell
.venv\Scripts\python.exe src\jarvis_agent.py                                 # interactive
.venv\Scripts\python.exe src\jarvis_agent.py --tekil "task in one shot"      # single task
.venv\Scripts\python.exe src\jarvis_agent.py --otonom                        # no approval prompts
.venv\Scripts\python.exe src\rag.py "password storage best practices"        # query retrieval directly
```

There is no `.env` file and no API key anywhere in this project — nothing calls a hosted model.

---

## Known limitations

Stated plainly, because a reader will find these anyway:

1. **No automated test suite.** `src/test_kurulum.py` is an environment and GPU smoke check, not unit tests. There is no pytest suite, no CI, and no regression coverage on the agent loop or the retrieval blending — the two places most likely to break silently.
2. **Retrieval quality is unmeasured.** There is no evaluation set, no recall@k benchmark, and no A/B comparison between hybrid-only and hybrid-plus-reranker. The `0.68/0.32` and `0.35/0.65` weights were tuned by inspecting results by hand. They work; they are not proven optimal.
3. **`uretim_araclari/` scripts are not portable.** Most contain hard-coded absolute Windows paths from the machine they were written on and were built as one-off pipeline steps. They document how the corpus was produced; they will not run unmodified elsewhere.
4. **The approval gate is a denylist, not a security boundary.** It regex-matches command text. Obfuscation, encoded commands, and destructive operations expressed in ways the pattern does not cover will pass. `--otonom` disables it entirely. It protects against a confused model, not a hostile one.
5. **Windows-only in practice.** `komut_calistir` shells out to `powershell`, and the CUDA DLL workaround assumes Windows path semantics. Nothing is conceptually Windows-bound, but nothing has been tested elsewhere.
6. **The 7B agent still makes mistakes.** It sometimes picks the wrong tool or drifts off-topic. Loop detection, the tool budget, and forced synthesis make it converge on an answer — they do not make the answer correct. The reliability lives in the tools and the knowledge base, not in the model.
7. **The from-scratch 17M model produces broken Turkish.** It is a learning artifact. It is not demoable and is not used by the agent.
8. **The corpus is machine-generated and heuristically screened.** Documents were produced by an LLM-driven pipeline grounded in real CVEs, Sigma rules, and vendor documentation, then screened for Turkish-character ratio, length, and homoglyph contamination. They were not peer-reviewed by a domain expert. Treat them as well-structured study material, and verify specifics against primary sources.
9. **RAG coverage is uneven by language.** Go, Java, and C++ do not publish Markdown documentation the way Python, Rust, and .NET do, so those languages are thin in the index and answers fall back to the model's general knowledge.
10. **Setup is partly manual.** `requirements.txt` covers the training path only; agent, retrieval, and QLoRA dependencies are listed in [Getting started](#getting-started) but are not pinned in a manifest. There is also a resumable downloader for the 7B GGUF but none for the embedding and reranker models — those have to be fetched by hand.
11. **The voice layer does not exist.** Whisper STT and TTS were planned and are described as a future phase in the Turkish README. No code for them is in this repository.
12. **The index source list and the downloader do not match.** `src/rag_kur.py` expects 23 named archives, but `src/kaynak_indir.py` fetches a different set of 55 repositories. Archives such as OWASP ASVS / MASTG / Top10 / API-Security, HackTricks, h4cker, CPython, Django, FastAPI, the nginx admins handbook, Kubernetes, Go, and .NET docs come from `src/prepare_data.py` or were placed in `data/raw/` by hand. Reproducing the exact index the agent was developed against therefore takes more than running `kaynak_indir.py`.
13. **The agent's own docstring is stale.** The module docstring and the startup banner in `src/jarvis_agent.py` still say 12 tools; the registry actually holds 18. The count in this README reflects the registry.

---

## Status

**Personal research project. Not a product, not maintained as one, and never shipped to users.**

It was built to answer a specific question — how much useful work can a 7B model on a 6 GB laptop GPU actually do, if the surrounding engineering is taken seriously — and it answers it. Development has stopped at the point where that question was answered.

It is published as a reference implementation and a portfolio artifact. The parts worth reading are `src/jarvis_agent.py` (the control loop and its failure-mode handling), `src/rag.py` (two-stage retrieval with score blending and a declared degradation chain), and `bilgi_hazinesi/` (a Turkish security and software corpus of a kind that is hard to find in the open).

The repository was published as a snapshot after removing license-restricted harvest artifacts and local machine details.

---

## License

This repository is dual-licensed — code and corpus are covered separately.

| What | License | |
| --- | --- | --- |
| Source code (`src/`, `uretim_araclari/`, everything else) | **MIT** | [LICENSE](LICENSE) |
| Turkish technical corpus (`bilgi_hazinesi/`, 523 documents) | **CC BY-SA 4.0** | [bilgi_hazinesi/LICENSE](bilgi_hazinesi/LICENSE) |

The code is free to reuse without conditions. The corpus is also free to reuse —
including as training or evaluation data — but asks for **attribution**, and for
derivative corpora to stay under the same terms. It represents roughly 254,000
words written for this project in a domain where open Turkish technical text is
scarce, which is why it carries a different license from the code.

**Provenance disclosure:** the corpus was authored with LLM assistance and then
curated, quality-scanned, and deduplicated with the tooling in `uretim_araclari/`.
Anyone weighing it as training data should factor that in.

Third-party documentation harvested by the download scripts in `src/` is **not** covered by either license and is not redistributed here. HackTricks (CC BY-NC-SA), OWASP material (CC BY-SA), and Microsoft docs (CC BY) retain their own terms; the downloader fetches them from their sources at setup time.
