# EqGuard

EqGuard studies graph neural network detection of hardware Trojans across functionally equivalent gate-level netlist implementations. The research snapshot covers netlist transformation and label provenance, node and endpoint-cone supervision, matched benign controls, SAT and CEC evidence, and robustness under synthesis recipe and keep-attribute changes.

## Layout

| Path | Contents |
| --- | --- |
| `10.15/` | Experiment assets organized by research task |
| `phase2/`, `generate_trans/` | Netlist transformations, graph preparation and functional evidence workflows |
| `models/`, `utils/` | Model and graph utilities |
| `_p0pilot/` | Experiment scripts, including unified N/NC supervision, no-keep evaluation and held-out recipe analysis |
| `requirements/` | Observed dependency versions |

Code is tracked in Git. The matching GitHub Release contains data such as benchmark and transformed netlists, graph arrays, labels and split indices, checkpoints, predictions, tables, logs and function certificates. Use the code commit and data manifest recorded for the same release tag. Historical research assets retain their original relative paths.

## Restore the research snapshot

Clone this repository at the release tag. Download the listed ZIP volumes and machine-readable asset manifest from that release. Use the SHA-256 recorded for each ZIP.

```text
python tools/restore_eqguard_volume.py PATH_TO_VOLUME.zip PATH_TO_CHECKOUT SHA256_FROM_MANIFEST
```

Run the command for each volume. The tool verifies the archive and each restored file and accepts an already restored file only if its hash matches. Ensure the destination has space for the uncompressed data. Keep the original release manifest to identify the exact experiment snapshot.

## Runtime and experiment entry points

GPU experiments used the local `ginvenv_gpu` environment with Python 3.12. Use `requirements/runtime-observed.txt` for observed direct dependency versions and install PyTorch with CUDA support for your system before installing compatible PyTorch Geometric packages. Netlist preparation and functional checks also use Yosys and the applicable standard-cell models. The research scripts include historical configurations and may require setting the project or data root for the selected workflow.

- Unified node-only and node-plus-cone supervision lives under `_p0pilot/seed42_nc_ablation_20261109/`.
- Held-out `abc`, `aig` and `nand` evaluations live under `_p0pilot/heldout_recipe_v5_20261109/` and `_p0pilot/heldout_v5_endpoint_replay_20261112/`.
- The no-keep paired evaluation uses `_p0pilot/evaluate_task2_nokeep_20261113.py` and the corresponding graph and proof assets.

N denotes node-only supervision and NC adds cone supervision. Unresolved function or label bindings are recorded as unknown. Evaluation distinguishes node average precision, endpoint recall under a 512-gate inspection budget, confirmed false alarms and the cost of inspecting unknown endpoints.

## Follow-up release: three main experiments and benign controls

The [2026-11-15 follow-up release](https://github.com/90ICEDA/EqGuard/releases/tag/eqguard-10-15-20261115) is a data delta on top of the [2026-11-13 base release](https://github.com/90ICEDA/EqGuard/releases/tag/eqguard-10-15-20261113). Check out the follow-up tag. Restore the base ZIPs according to the base manifest, then restore the follow-up ZIPs according to the follow-up manifest into the same checkout. The separate archives add distinct data paths. The restore tool verifies the archive hash and every restored member.

- Run `python tools/audit_main_20261115.py` from the populated checkout to verify the main ledgers, clean-pair hash bindings and selected report figures without training or synthesis.
- The primary G0 N/NC comparison remains in `_p0pilot/seed42_nc_ablation_20261109/`. The separate fixed historical H/H+D comparison is in `_p0pilot/legacy_h_cone_20261115/`. G0 and historical H use different node sampling budgets.
- The keep/no-keep extension and clean-pair data are in `_p0pilot/task2_nokeep_audit_20261113/`, with one fully unseen circuit family. The official held-out recipe runs remain in `_p0pilot/heldout_recipe_v5_20261109/`.
- The five-group benign-control results remain in `_p0pilot/control_five_multiseed_20261107/`. Later benign-control and native false-positive analyses are under `_p0pilot/live_control_20261114/`, `_p0pilot/native_hard_fpr_20261113/` and related directories. The A/B/C/C2/D/E variants are exploratory and do not replace the fixed baselines.

Historical proof and run artifacts retain original paths for provenance. When rerunning a historical Yosys or shell recipe on a different machine, work on a copy and rebase those paths to the checkout. Checkpoints are research artifacts; use them only in a trusted environment.

The independent D/PO cone AP supplement uses only certified positive and negative endpoints and the frozen N/NC and H/H+D scores. Unknown endpoints remain in the inspection-budget metrics, but not in this AP calculation. The follow-up Release also includes `endpoint-ap-manifest-20261115.json` and its ZIP with the per-view and aggregate tables. The supplement manifest identifies the code commit that includes `_p0pilot/main_endpoint_ap_20261115/evaluate.py`.
