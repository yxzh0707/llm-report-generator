# RQ2 InFoBench-inspired pilot

Completed on 2026-10-25, without human rating. This is a local adaptation of Qin et al., *InFoBench: Evaluating Instruction Following Ability in Large Language Models*, Findings of ACL 2024, [publisher record](https://aclanthology.org/2024.findings-acl.772/). It does not run the official 500-prompt dataset and must not be described as an official InFoBench score. The upstream source commit and hashes are in `upstream.json`; upstream files are reference material, not executed dependencies.

## Design and execution

Six previously generated reports cover the three existing customization pairs: T2/C_structure, T4/C_style and T3/C_depth, repetition 1. These were selected for requirement coverage, not observed evaluation scores. Decomposed questions come from task text and original style instructions. Mechanical constraints are checked separately. The original depth request mostly specifies word ranges, so the added semantic-depth question is a diagnostic operationalization excluded from explicit instruction-following aggregates.

The frozen protocol and all report/evidence inputs were hashed before evaluation. Each report is evaluated in a fresh context, with questions batched within that report. This differs from upstream sequential question conversations. Prior human/model labels and report group identities are excluded from judge input. Exact source and report quotations are required as an additional traceability check. This extra check is our adaptation, not an original InFoBench requirement.

The only configured remote service was Qwen3.8-27B, also the historical generation deployment name. The pilot uses temperature 0, thinking disabled, 4,000 output-token ceiling per call, a 120-second timeout and no retries. Server weight revisions are unavailable. No new report generation, retrieval, embedding, human rating, or direct-generation baseline was run.

12 real calls comprised six original reports, repeats of the three customized reports, and three negative controls retaining headings and Sources but removing the body. The latter is an intentionally easy omission test, not evidence of subtle semantic accuracy. Service-reported usage totals 92,423 prompt tokens and 12,619 completion tokens, 105,042 total. These counts are not a monetary cost calculation.

## Results and an explicitly recorded analysis change

The original frozen validator rejected an entire response if any quotation was not a literal substring of the report/source. Six of 12 responses passed, including two of the six original-report responses. All transport calls completed; the six failures were quotation-validation failures, not provider outages. The original aggregate retains 32 INVALID and 15 YES across 47 explicit semantic requirements, so its lower/upper satisfaction bounds are 31.9–100%. These wide bounds are not a useful quality estimate.

After observing this technical failure mode, a separate deterministic analysis isolated invalid items instead of discarding valid neighboring items. This is a **post-hoc analysis change**, not the initially frozen scoring rule. It made zero model calls, changed no raw labels, accepted no approximate quotes, and retained the original analysis. Both results remain linked in the delivered report.

| Itemwise secondary analysis | Result |
|---|---|
| Explicit semantic requirements | 47 |
| YES / NO / INVALID | 36 / 1 / 10 |
| Micro satisfaction bounds | 76.6–97.9% |
| Equal-report macro bounds | 78.0–98.1% |
| Content requirements | 26 YES, 1 NO, 9 INVALID / 36 |
| Style requirements | 10 YES, 1 INVALID / 11 |
| Negative-control content items | 18/18 NO |
| Repeated labels, including depth diagnostic | 22/22 agree among valid pairs; 4/26 pairs have invalid judgments |

Bounds count INVALID/UNKNOWN as unsatisfied at the lower end and potentially satisfied at the upper end; they are not statistical confidence intervals. Valid quotation matching does not establish correctness of a judgment. Agreement and easy negative controls do not establish validity or human agreement. Ten invalid requirements (21.3%) are substantial, so the high observed YES count is not a reliable success-rate conclusion.

Mechanical checks independently identify two overlength reports: T3 brief has 806 words against 250–500; T4 standard has 1,691 against 650–1,400. All three customized reports satisfy the programmatic checks used here. These checks do not include every original runtime gate and cannot replace the historical strict-success measure.

## Deliverables and reproduction

- [Readable secondary report](../../artifacts/rq2_infobench/pilot_v1/itemwise/report.html)
- [Original whole-response validation report](../../artifacts/rq2_infobench/pilot_v1/report.html)
- [Original protocol](protocol.json)
- [Frozen session and input hashes](../../artifacts/rq2_infobench/pilot_v1/manifest.json)
- [Secondary summary](../../artifacts/rq2_infobench/pilot_v1/itemwise/summary.json)
- [All secondary item judgments](../../artifacts/rq2_infobench/pilot_v1/itemwise/items.json)

Run from the repository root:

```sh
.venv-runtime/bin/python -m unittest analysis.test_rq2_infobench_pilot
.venv-runtime/bin/python analysis/rq2_infobench_pilot.py verify --out artifacts/rq2_infobench/pilot_v1
```

For a new explicitly labeled replication, choose an unused output directory. `prepare` rejects existing directories; `run` never resubmits a recorded attempt. The environment-file path follows the existing project setup in the root README, and credentials are never stored in artifacts.

```sh
.venv-runtime/bin/python analysis/rq2_infobench_pilot.py prepare --out artifacts/rq2_infobench/replication_02
DISSERTATION_ENV_FILE=/private/path/to/runtime.env .venv-runtime/bin/python analysis/rq2_infobench_pilot.py run --out artifacts/rq2_infobench/replication_02
.venv-runtime/bin/python -m analysis.rq2_infobench_itemwise --session artifacts/rq2_infobench/replication_02 --out artifacts/rq2_infobench/replication_02/itemwise
```

Seven offline tests check missing/duplicate IDs, unsupported quotes, UNKNOWN handling, YES evidence requirements, content removal, diagnostic separation and item-level failure containment. Original report/request/evidence/input/manifests were rehashed after execution and after secondary analysis: all 30 tracked original files are unchanged.

## Implication for the dissertation

This pilot adds a concrete RQ2 evaluation-method investigation: instruction decomposition, mechanical/semantic separation, traceable automated judgments, missing-result handling, repeated assessment and negative controls. It is suitable as an exploratory method experiment, not evidence that the report system outperforms direct generation. Before a larger comparison, fix itemwise handling prospectively and use a separately configured judge model; the current same-model evaluator and quoted-evidence failures limit interpretation. All old human-review records retain their original identities. No manuscript results or DOCX/PDF files were changed.
