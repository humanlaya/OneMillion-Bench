# $OneMillion-Bench

<p align="center">
  <a href="https://huggingface.co/datasets/humanlaya-data-lab/OneMillion-Bench">Hugging Face</a> •
  <a href="https://arxiv.org/abs/2603.07980">arXiv</a> •
  <a href="https://www.bigai.ai/blog/news/%e9%80%9a%e7%a0%94%e9%99%a2%e5%8f%91%e5%b8%83%e8%a1%8c%e4%b8%9a%e6%99%ba%e8%83%bd%e4%bd%93%e5%9f%ba%e5%87%86%ef%bc%8c%e9%87%8d%e6%96%b0%e5%ae%9a%e4%b9%89%e6%95%b0%e5%ad%97%e5%91%98%e5%b7%a5">BIGAI</a> •
  <a href="https://humanlaya.com/#/leaderboard/one-million-bench">Humanlaya</a> •
  <a href="https://xbench.org/profession/onemillion">xbench</a>
</p>

<img alt="npr-poster" src="assets/omb.png">

</div>

A rubric-based automated evaluation system for language agents capabilities on economically conceptual tasks across professional domains. It evaluates 50+ models or agent systems from 6 API-based providers with weighted binary grading, async concurrency, cost tracking, and Excel/JSON reporting.

Contact: liuyang@bigai.ai

**Table of contents**

* [Overview](#overview)
* [Dataset](#dataset)
* [Installation](#installation)
* [Quick start](#quick-start)
* [CLI reference](#cli-reference)
* [Configuration](#configuration)
* [Task format](#task-format)
* [Output format](#output-format)
* [Architecture](#architecture)
* [Development](#development)
* [Frequently asked questions](#frequently-asked-questions)
* [License](#license)
* [Citation](#citation)

## Overview

$OneMillion-Bench is a CLI tool (`omb`) that generates LLM responses, grades them against weighted rubrics using judge models, and produces reports.

- **50+ models** across 6 providers (OpenRouter, Qwen/DashScope, VolcEngine, Hunyuan, Ling-1T, LiteLLM)
- **Concurrent async processing** with up to 128 parallel requests
- **Weighted rubric scoring** with binary (yes/no) evaluation
- **Repeated sampling & judging** for variance estimation
- **Web search augmentation** for search-enabled generation
- **Automatic cost tracking** per model with token usage and pricing
- **Rich reporting**: Gruvbox-themed Excel workbooks, JSON summaries

## Dataset

### $OneMillion-Bench

**5 professional domains**, bilingual (Chinese + English), **400 questions**:

| Domain | CN | EN | Total | Description |
| ------ | -- | -- | ----- | ----------- |
| Healthcare | 40 | 40 | 80 | Clinical medicine, oncology, pharma, gene & cell therapy |
| Finance | 40 | 40 | 80 | Investment, equities, financial analysis |
| Industry | 40 | 40 | 80 | Systems engineering, embedded systems, robotics |
| Law | 40 | 40 | 80 | Corporate/commercial law, M&A |
| Natural Sciences | 40 | 40 | 80 | Chemistry, materials science |

Each test case contains a prompt, optional system prompt, domain tags, and 5-23 **weighted rubrics** labeled as: Factual Information, Analytical Reasoning, Instructions Following, or Structure and Formatting.

## Installation

Requires Python 3.10+. conda recommended.

```bash
conda create -n evals python=3.10 -y && conda activate evals
git clone https://github.com/humanlaya/OneMillion-Bench.git
cd OneMillion-Bench
pip install -e .
omb --version  # verify installation
```

## Quick start

### 1. Download the dataset

```bash
mkdir datasets
hf download Humanlaya-Research-Insititution/OneMillion-Bench --repo-type=dataset --local-dir datasets/OneMillion-Bench
```

### 2. Set API keys

```bash
export OPENROUTER_API_KEY="your-key"                  # Required (recommended for 50+ models)
export DASHSCOPE_API_KEY="your-key"                   # Optional: Qwen / DashScope
export VOLC_API_KEY="your-key"                        # Optional: VolcEngine (Doubao)
export HUNYUAN_API_KEY="your-key"                     # Optional: Tencent Hunyuan
export LING_API_KEY="your-key"                        # Optional: Ling-1T
export LITELLM_API_KEY="your-key"                     # Optional: LiteLLM
```

p.s. add these to `~/.bashrc` or `~/.zshrc` to persist across sessions.

### 3. Configure evals

```bash
cp src/omb/config/default.yaml my_config.yaml
```

Edit `my_config.yaml` to select models (API keys are read from environment variables, not the config file):

```yaml
JUDGE_MODELS:
  - "google/gemini-3-pro-preview"

GENERATOR_MODELS:
  - "openai/gpt-5.4"
  - "anthropic/claude-opus-4.6"
  - "google/gemini-3.1-pro-preview"
```

### 4. Run evals

```bash
omb eval --dataset datasets/OneMillion-Bench/Healthcare --config my_config.yaml            # single domain
omb eval --dataset datasets/OneMillion-Bench --config my_config.yaml --recursive           # all domains
omb eval --dataset datasets/OneMillion-Bench/Law --config my_config.yaml --grade-only      # grade only
```

### 5. Python API

```bash
python examples/auto_grading.py --dataset datasets/OneMillion-Bench/Healthcare --config my_config.yaml
```

Results are written to `outputs/result_YYYYMMDD_HHMMSS/`.

## CLI reference

```bash
omb eval [OPTIONS]
```

| Flag | Description |
| ---- | ----------- |
| `--dataset PATH` | Path to test file or directory (required) |
| `--config` / `-c FILE` | YAML configuration file |
| `--recursive` | Scan subdirectories recursively |
| `--grade-only` | Grade existing responses only, skip generation |
| `--overwrite` | Force regeneration and regrading |
| `--enable-search` | Enable web search augmentation |
| `--limit N` | Limit number of test questions |
| `--repeat-sample N` | Independent responses per generator (default: 1) |
| `--repeat-judge N` | Repeated judge runs per response (default: 1) |
| `--detect-metadata` | Auto-detect model context length and max tokens |
| `--verbose` / `-v` | Verbose output |
| `--quiet` / `-q` | Suppress non-essential output |
| `--debug` | Show questions and responses |
| `--no-color` | Disable colored output |

**Exit codes:** 0 = success, 2 = config error, 3 = input error, 4 = partial failure, 130 = interrupted.

## Configuration

Managed via YAML files. Copy `src/omb/config/default.yaml` and modify as needed. API keys are read from environment variables, not config files.

### API keys

| Environment variable | Provider |
| --------- | -------- |
| `OPENROUTER_API_KEY` | OpenRouter (50+ models) |
| `DASHSCOPE_API_KEY` | Qwen / DashScope |
| `VOLC_API_KEY` | VolcEngine (Doubao) |
| `HUNYUAN_API_KEY` | Tencent Hunyuan |
| `LING_API_KEY` | Ling-1T |
| `LITELLM_API_KEY` | LiteLLM |

### Model selection

| Parameter | Description |
| --------- | ----------- |
| `JUDGE_MODELS` | Models used for grading |
| `GENERATOR_MODELS` | Models to evaluate |
| `REFERENCE_MODELS` | Optional baseline models with existing responses |
| `REASONING_EFFORT` | Judge reasoning: `"low"`, `"medium"`, `"high"`, `"xhigh"`, or `null` |

### Parameters

| Parameter | Default | Description |
| --------- | ------- | ----------- |
| `MAX_TOKENS` | 128,000 | Max output tokens |
| `TIMEOUT` | 600 | API timeout (seconds) |
| `RETRY_TIMES` | 8 | Retry attempts |
| `SAMPLE_K` | 1 | Response samples per generator |
| `REPEATED_JUDGE` | 1 | Judge runs per response |
| `MAX_GENERATION_CONCURRENCY` | 128 | Parallel generation requests |
| `MAX_GRADING_CONCURRENCY` | 128 | Parallel grading requests |
| `TEMPERATURE` | 1.0 | Sampling temperature |
| `TOP_P` | 0.95 | Nucleus sampling threshold |
| `TOP_K` | 20 | Top-k sampling |

## Task format

Each test case is a JSON file:

| Field | Type | Description |
| ----- | ---- | ----------- |
| `prompt` | string | Question or instruction |
| `system_prompt` | string | Optional system prompt |
| `tags` | list[string] | Domain hierarchy, e.g., `["Healthcare", "Pharma", "Gene Therapy"]` |
| `case_id` | int | Unique test case ID |
| `rubrics` | list[object] | Evaluation rubrics (see below) |

Each rubric:

| Field | Type | Description |
| ----- | ---- | ----------- |
| `rubric_number` | int | Index within the case |
| `rubric_detail` | string | Evaluation criterion |
| `rubric_weight` | int | Score weight (positive to award, negative to penalize) |
| `rubricLabel` | string | Category label |

**Example:**

```json
{
  "prompt": "Explain the concept of viral titer in gene therapy ...",
  "system_prompt": "",
  "tags": ["Healthcare", "Pharma", "Gene Therapy"],
  "case_id": 2860,
  "rubrics": [
    {"rubric_number": 1, "rubric_detail": "Clearly defines viral titer and distinguishes infectious vs. physical titer.", "rubric_weight": 10, "rubricLabel": "Analytical Reasoning"},
    {"rubric_number": 2, "rubric_detail": "Lists at least 3 common titer measurement methods.", "rubric_weight": 8, "rubricLabel": "Factual Information"}
  ]
}
```

## Output format

Results are saved to `outputs/result_YYYYMMDD_HHMMSS/`:

- **Updated JSON files** — input files augmented with `model_response`, `rubric_auto_score`, `judge_cot`, and `rubric_auto_vs_human` fields.
- **grading_results.xlsx** — Gruvbox-themed workbook with per-judge scores, aggregate sheets, and cost breakdowns.
- **grading_results.json** — Machine-readable summary with per-model metrics and costs.

## Architecture

```
src/omb/
├── cli/               # CLI entry point (omb eval ...)
├── orchestrator.py    # Main workflow: load -> generate -> grade -> retry -> report
├── clients/           # LLM API clients (OpenRouter, Qwen, VolcEngine, Hunyuan, Ling-1T)
├── config/            # YAML configuration management with pricing data
├── grading/           # Grading prompt construction and response parsing
├── processing/        # Async generation and grading with semaphore concurrency
├── reporting/         # Excel (Gruvbox-themed) and JSON report generation
├── tracking/          # Token usage and cost tracking per model
└── utils/             # Rich console UI and Gruvbox color palette
```

See [docs/arch.md](docs/arch.md) for detailed architecture documentation.

## Development

```bash
make install        # Install dev dependencies
make test           # Run tests (pytest)
make lint           # Static analysis (flake8, mypy, pylint)
make format         # Format code (black, isort)
make format-check   # Check formatting without modifying
make check          # Run all checks
make clean          # Remove build artifacts
```

## Frequently asked questions

**What models are supported?** 50+ models through 6 providers. Specified as `provider/model` (e.g., `openai/gpt-5.4`). See `src/omb/config/default.yaml` for the full list.

**Can I add a new LLM provider?** Yes. Extend `BaseLLMClient` in `src/omb/clients/` and implement the `call()` method.

**Can I use custom rubrics?** Yes. Create JSON files following the [task format](#task-format) schema.

**How does grading work?** The judge evaluates each rubric with a binary yes/no judgment and chain-of-thought justification. Scores are weighted by rubric weights. Multiple judges and repeated runs are supported.

**How is cost tracked?** Token usage is tracked per model per call. Costs are computed from the pricing table in the config and reported in both Excel and JSON outputs.

## Citation
```latex
@article{yang2026onemillionbench,
    title={\$OneMillion-Bench: How Far are Language Agents from Human Experts?},
    author={Yang, Qianyu and Liu, Yang and Li, Jiaqi and Bai, Jun and Chen, Hao and Chen, Kaiyuan and Duan, Tiliang and Dong, Jiayun and Hu, Xiaobo and Jia, Zixia and Liu, Yang and Peng, Tao and Ren, Yixin and Tian, Ran and Wang, Zaiyuan and Xiao, Yanglihong and Yao, Gang and Yin, Lingyue and Zhang, Ge and Zhang, Chun and Jiao, Jianpeng and Zheng, Zilong and Gong, Yuan},
    journal={arXiv preprint arXiv:2603.07980},
    year={2026}
}
```

## License

[Apache License 2.0](LICENSE)
