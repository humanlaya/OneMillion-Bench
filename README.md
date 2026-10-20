# $OneMillion-Bench

<p align="center">
  <a href="https://huggingface.co/datasets/humanlaya-data-lab/OneMillion-Bench">Hugging Face</a> •
  <a href="https://arxiv.org/abs/2603.07980">arXiv</a> •
  <a href="https://www.bigai.ai/blog/news/%e9%80%9a%e7%a0%94%e9%99%a2%e5%8f%91%e5%b8%83%e8%a1%8c%e4%b8%9a%e6%99%ba%e8%83%bd%e4%bd%93%e5%9f%ba%e5%87%86%ef%bc%8c%e9%87%8d%e6%96%b0%e5%ae%9a%e4%b9%89%e6%95%b0%e5%ad%97%e5%91%98%e5%b7%a5">BIGAI</a> •
  <a href="https://humanlaya.com/#/leaderboard/one-million-bench">Humanlaya</a> •
  <a href="https://xbench.org/profession/onemillion">xbench</a>
</p>

> As AI learns to gather the scattered sixpence, human gains the liberty to look up at the moon.

<img alt="omb-poster" src="assets/omb.png">

</div>

A rubric-based automated evaluation system for language agents capabilities on economically conceptual tasks across professional domains. It evaluates 50+ models or agent systems from 6 API-based providers with weighted binary grading, async concurrency, cost tracking, and Excel/JSON reporting.

Contact: liuyang@bigai.ai

## News
- **[2026.09.28]** $OMB are now available to evaluate with [**EvalScope**](https://evalscope.readthedocs.io/en/latest/benchmarks/one_million_bench.html).
- **[2026.09.26]** $OMB has been accepted by [**NeurIPS 2026**](https://openreview.net/forum?id=2gAr3pMVHH) ✨. See you in 🇺🇸 Atlanta!
- **[2026.08.28]** $OMB has been adopted by **Tencent [Hy4-preview](https://hy.tencent.ai/research/hy4-preview)**.
- **[2026.08.03]** $OMB has been adopted by **Alibaba [Qwen3.8-Max](https://qwen.ai/blog?id=qwen3.8)**.
- **[2026.06.23]** $OMB has been adopted by **ByteDance [Doubao-Seed-2.1](https://seed.bytedance.com/en/blog/seed2-1-officially-released-advancing-ai-productivity)**.
- **[2026.03.10]** $OMB has been widely reported by **[机器之心](https://mp.weixin.qq.com/s/eTCGafQFxAJ3XzvhVoL7Mw)** and launched in **[xbench](https://xbench.org/profession/onemillion)**.

**Table of contents**

* [Overview](#overview)
* [Dataset](#dataset)
* [Installation](#installation)
* [Quick start](#quick-start)
* [Using EvalScope](#using-evalscope)
* [Task format](#task-format)
* [Output format](#output-format)
* [Frequently asked questions](#frequently-asked-questions)
* [License](#license)
* [Citation](#citation)

## Overview

We maintains the $OneMillion-Bench evaluation toolkit and the latest leaderboard performance is available [here](https://xbench.org/profession/onemillion).

$OneMillion-Bench is a CLI tool (`omb`) that generates LLM agent responses, grades them against weighted rubrics using judge models, and produces reports.

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

| Domain | Directory | CN | EN | Total | Description |
| ------ | --------- | -- | -- | ----- | ----------- |
| Healthcare & Medicine | `healthcare_and_medicine` | 40 | 40 | 80 | Clinical medicine, oncology, pharma, gene & cell therapy |
| Economics & Finance | `economics_and_finance` | 40 | 40 | 80 | Investment, equities, financial analysis |
| Industry | `industry` | 40 | 40 | 80 | Systems engineering, embedded systems, robotics |
| Law | `law` | 40 | 40 | 80 | Corporate/commercial law, M&A |
| Natural Science | `natural_science` | 40 | 40 | 80 | Chemistry, materials science |

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
hf download humanlaya-data-lab/OneMillion-Bench --repo-type=dataset --local-dir datasets/OneMillion-Bench
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
omb eval --dataset datasets/OneMillion-Bench/healthcare_and_medicine --config my_config.yaml            # single domain
omb eval --dataset datasets/OneMillion-Bench --config my_config.yaml --recursive                       # all domains
omb eval --dataset datasets/OneMillion-Bench/law --config my_config.yaml --grade-only                  # grade only
```

### 5. Python API

```bash
python examples/auto_grading.py --dataset datasets/OneMillion-Bench/healthcare_and_medicine --config my_config.yaml
```

Results are written to `outputs/result_YYYYMMDD_HHMMSS/`.

## Using EvalScope

[EvalScope](https://github.com/modelscope/evalscope) now supports $OneMillion-Bench, providing a standardized evaluation workflow with OpenAI-compatible model endpoints, saved predictions, scoring, and report generation.

This may be useful for users who want a quick path to evaluate hosted or locally served models.

### Example

```bash
evalscope eval \
  --model YOUR_MODEL \
  --api-url OPENAI_API_COMPAT_URL \
  --api-key YOUR_API_KEY \
  --datasets one_million_bench \
  --limit 10
```

### Documentation

For detailed setup, configuration, and usage instructions, see the [EvalScope $OneMillion-Bench documentation](https://evalscope.readthedocs.io/en/latest/benchmarks/one_million_bench.html).

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

## Frequently asked questions

**What models are supported?** 50+ models through 6 providers. Specified as `provider/model` (e.g., `openai/gpt-5.4`). See `src/omb/config/default.yaml` for the full list.

**Can I add a new LLM provider?** Yes. Extend `BaseLLMClient` in `src/omb/clients/` and implement the `call()` method.

**Can I use custom rubrics?** Yes. Create JSON files following the [task format](#task-format) schema.

**How does grading work?** The judge evaluates each rubric with a binary yes/no judgment and chain-of-thought justification. Scores are weighted by rubric weights. Multiple judges and repeated runs are supported.

**How is cost tracked?** Token usage is tracked per model per call. Costs are computed from the pricing table in the config and reported in both Excel and JSON outputs.

## Citation
```latex
@inproceedings{
    liu2026onemillionbench,
    title={\$OneMillion-Bench: How Far are Language Agents from Human Experts?},
    author={Liu, Yang and Li, Jiaqi and Bai, Jun and Yang, Qianyu and Hu, Xiaobo and Peng, Tao and Wang, Zaiyuan and Dong, Jiayun and Zhang, Chun and Jia, Zixia and Chen, Kaiyuan and Xiao, Yanglihong and Yin, Lingyue and Duan, Tiliang and Zhang, Ge and Yao, Gang and Chen, Hao and Jiao, Jianpeng and Zheng, Zilong},
    booktitle={The Fortieth Annual Conference on Neural Information Processing Systems Evaluations and Datasets Track},
    year={2026},
    url={https://openreview.net/forum?id=2gAr3pMVHH}
}
```

## License

[Apache License 2.0](LICENSE)
