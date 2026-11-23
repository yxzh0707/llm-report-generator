# LLM-Based Report Generator

[中文说明](README.zh-CN.md)

This repository contains the project source and recorded evaluation results for Zhang Yuxuan’s MSc dissertation. The system uses uploaded documents and web or API evidence to generate English reports with configurable structure, style and depth. It records citations, validates supported calculations and provides a local interface for inspecting and exporting reports.

## Verify the recorded results

The verification script uses the Python 3 standard library. It checks the repository’s file hashes and rebuilds the main results table from saved evaluation decisions.

```sh
python3 scripts/verify_results.py --check-manifest
```

The main comparison used the same Qwen3.8-27B deployment and the same available source texts for both systems. Across eight first-run tasks, the report generator met the required content and output constraints in **8/8** runs, compared with **3/8** for native Hermes. Including four prespecified repeats per system gives **12/12** versus **4/12**. Reports had no major narrative contradictions in **3/8** and **1/8** first runs, respectively.

These are descriptive results from four companies in two company-pair clusters. The comparison controlled evidence acquisition. Narrative evaluation used an anonymised model judge and an AI-assisted source audit without independent reader calibration. See [recorded results](results/main_results.csv) and the [reproduction notes](REPRODUCE.md).

## Repository layout

| Path | Contents |
| --- | --- |
| `src/` | Report requests, evidence retrieval, citations, calculations, checks and local UI |
| `configs/` and `.env.example` | Example requests and environment configuration |
| `experiments/` and `analysis/` | Study runners, analysis scripts and manuscript-building programs |
| `tests/` | Engineering regression tests and synthetic fixtures |
| `results/` | Main comparison decisions, summary tables and source inventory |

## Run with an authorised runtime

Generating reports requires Python 3.12, authorised access to a compatible AutoResearch runtime and a configured model provider. The runtime includes the `autoresearch_agent_core`, `autoresearch_agent_langchain` and `autoresearch_frontier_finance` packages.

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-runtime.lock.txt
.venv/bin/python -m pip install --no-deps -e /path/to/authorised-runtime
cp .env.example .env.local
# Configure your provider and private credential references in .env.local.
.venv/bin/python src/report_server.py --port 8767
```

The local interface is available at `http://127.0.0.1:8767`. Historical model names identify the deployments used in the study. Re-running historical experiments requires their frozen inputs and source snapshots. See the [publication scope](RELEASE_REVIEW.md).

## Licence

The source is publicly available for inspection. The author has not granted an open-source licence. See [NOTICE.md](NOTICE.md) for dependency and reuse information.
