# Findings

- Found references in research logs and screening reports for `amount_regime_transitions_full`.
- Existing summary in `research/EXPERIMENT-LOG.md` reports metrics: LS Sharpe 1.60, Long Excess Net Sharpe +1.14, IR 0.66, Mono 0.57/0.43, marked as Mono not meeting threshold.
- Formal evaluation path is `.claude-output/evaluations/volume_entropy/amount_regime_transitions_full/`.
- Pending rawdata is managed as per-feature directories under `research/pending-rawdata/`.
- Existing pending packages are directory-based: `research/pending-rawdata/{feature}/report.md`.
- Screening report confirms only failing metric for `amount_regime_transitions_full` is Mono: raw 0.57, neutral 0.43 vs threshold > 0.7.
- Coverage is 86.7%, LS Sharpe 1.60/1.22, IR 0.66, Long Excess Net Sharpe 1.14/0.90.
- Pending packages usually include `report.md`, `factor_values.pkl` symlink, and optionally `eval_charts/` images when present.
