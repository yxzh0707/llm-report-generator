# Reproduction and verification

## Offline verification

```sh
python3 scripts/verify_results.py --check-manifest --output /tmp/main_results.csv
```

This reaggregates **saved adjudicated decisions** and checks package file identities.
It does not independently re-judge semantic truth, recreate a model response or prove
that each archived source supports its report. Public candidates contain decisions
and source URLs, not full third-party documents or raw trajectories.

In a local reference checkout, also validate all 24 evaluated-report hashes:

```sh
python3 scripts/verify_results.py --reference-root . --check-manifest
```

## Exact main metric

The final required-content-and-constraints pass is:

```
recorded combined_completion
AND all derived[].supported_calculation
AND all growth[].passed
```

Older final_summary.json retains a narrower combined_completion counter (Hermes
7/12). Use heldout_summary.json and the above final conjunction for the thesis's
12/12 versus 4/12. The legacy file is preserved rather than silently overwritten.
First-run results use repetition == 1. Repeats and facts are not independent companies.

## Regeneration

Full generation requires an independently authorised runtime, provider/model access,
pinned dependencies and the correct frozen source and input bytes. The main study
protocol fixes Qwen3.8-27B, temperature 0.2, thinking off, 900 seconds and distinct
16-model-call versus 16-native-iteration limits. A native Hermes checkout must match
commit 7d568293f97a8640467303e786583efc19cecd20. Set HERMES_SOURCE in the public
portability version. Historical frozen workers retain their original local path.

Do not run historical experiment entry points against completed data: several use
existence and fingerprint guards intentionally. Restore the protocol's code snapshot
into a fresh isolated directory for any authorised regeneration. Keep new outputs
separate; do not substitute them into sealed results. Stochastic outputs may differ.

Main reference path: artifacts/report_study/heldout_comparison_14/.
Read protocol.json, tasks.json, source_gold.json, evaluated reports, final_results.json,
heldout_summary.json, symmetric_source_audit.json and analysis_manifest.json in that order.
Original absolute paths in immutable provenance describe the historical host; resolve
by relative project paths after relocation. Hashes cover original bytes.
