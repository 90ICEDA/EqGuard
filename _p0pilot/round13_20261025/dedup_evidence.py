"""Round-13 offline evidence dedup and log-block audit (no SAT)."""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[2]))
from eqguard_paths import project_path as _eqguard_path

import hashlib
import json
import re
from pathlib import Path

import pandas as pd

ROOT = Path(_eqguard_path(''))
T11 = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/sat_pair_round11"
T12 = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/sat_pair_round12"
T13 = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/sat_pair_round13"


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def blocks(run_log: Path):
    out, cur = {}, None
    for line in run_log.read_text(encoding="utf-8", errors="replace").splitlines():
        if re.fullmatch(r"Q\d{4}", line):
            cur = int(line[1:])
            out[cur] = []
        elif cur is not None:
            out[cur].append(line)
    return out


def main() -> int:
    T13.mkdir(parents=True, exist_ok=True)
    r12 = pd.read_csv(T12 / "queries.csv", encoding="utf-8-sig", dtype={"pattern": str})
    r11 = pd.read_csv(T11 / "queries_batch3.csv", encoding="utf-8-sig",
                      dtype={"pattern": str})
    # Exact query identity: model bytes + exact SAT args. Same-bit aliases collapse
    # because native.emit resolves them to the same wire bits and identical model.
    r12["query_key"] = r12.model_sha + "|" + r12.args
    r11["query_key"] = r11.model_sha + "|" + r11.args
    r11u = r11.drop_duplicates("query_key")
    joined = r12.merge(r11u[["query_key", "status", "folder"]],
                       on="query_key", how="left", suffixes=("_12", "_11"))
    joined["historical"] = joined.folder_11.notna()
    joined.to_csv(T13 / "dedup_round12.csv", index=False, encoding="utf-8-sig")

    # Alias groups: same model/args but multiple executed folders.
    groups = []
    for key, g in r12.groupby("query_key"):
        if len(g) > 1:
            groups.append(dict(query_key=key, executions=len(g), status=g.status.iloc[0],
                               folders=";".join(g.folder), pair_index=int(g.pair_index.iloc[0]),
                               args=g.args.iloc[0]))
    pd.DataFrame(groups).to_csv(T13 / "alias_groups.csv", index=False,
                                encoding="utf-8-sig")

    # Per-folder log block audit; all round-12 folders plus historical pair folders
    # touched by the same four relations (no new solving).
    folders = set(r12.folder)
    for rid in ["r7|s38417t100__ctlmatchb_d1_s42__ys_abc.v|g24734",
                "r7|s38417t100__injalpha_d1_s42__ys_id.v|U6927.Q",
                "r5|rs232t1000__injzeta_d1_s42__ys_abc.v|U58.Y",
                "r6|rs232t1000__injzeta_d1_s42__ys_abc.v|U12.Y"]:
        out = pd.read_csv(T11 / "all_outcomes.csv", encoding="utf-8-sig")
        row = out[out.relation_id == rid].iloc[0]
        batch = int(row.batch_id)
        qf = T11 / ("queries.csv" if batch == 1 else f"queries_batch{batch}.csv")
        q = pd.read_csv(qf, encoding="utf-8-sig")
        q = q[(q.pair_index == int(row.pair_index))]
        if "batch_id" in q.columns:
            q = q[q.batch_id == batch]
        folders |= set(q.folder)
    log_rows = []
    for folder in sorted(folders):
        f = ROOT / folder
        if not (f / "run.log").exists():
            continue
        bs = blocks(f / "run.log")
        qlogs = sorted(f.glob("*.query.log"))
        ok = 0
        for ql in qlogs:
            qid = int(ql.name.split(".")[0])
            text = ql.read_text(encoding="utf-8", errors="replace").splitlines()
            ok += int(qid in bs and text[1:] == bs[qid])
        log_rows.append(dict(folder=folder, blocks=len(bs), query_logs=len(qlogs),
                             exact_matches=ok,
                             all_exact=int(len(qlogs) > 0 and ok == len(qlogs))))
    pd.DataFrame(log_rows).to_csv(T13 / "log_block_audit.csv", index=False,
                                  encoding="utf-8-sig")

    # Historical exact duplicate accounting.
    manifest = dict(
        round12_executions=len(r12),
        round12_distinct=len(r12.drop_duplicates("query_key")),
        round12_internal_duplicates=int(len(r12) - len(r12.drop_duplicates("query_key"))),
        round11_executions=len(r11),
        round11_distinct=len(r11u),
        round11_internal_duplicates=int(len(r11) - len(r11u)),
        cross_round_matches=int(joined.drop_duplicates("query_key").historical.sum()),
        cross_round_new_distinct=int(len(r12.drop_duplicates("query_key"))
                                     - joined.drop_duplicates("query_key").historical.sum()),
        combined_distinct=len(set(r11u.query_key) | set(r12.query_key)),
        combined_executions=len(r11) + len(r12),
        combined_duplicate_executions=int(len(r11) + len(r12)
                                          - len(set(r11u.query_key) | set(r12.query_key))),
        proved_executions=int((r12.status == "proved").sum()),
        proved_already_historical=int(((r12.status == "proved") & joined.historical).sum()),
        proved_first_new=int(((r12.status == "proved") & ~joined.historical).sum()),
        alias_groups=len(groups), alias_extra_executions=int(sum(g["executions"] - 1 for g in groups)),
        complete_pairs_added=0,
        log_folders=len(log_rows),
        log_folders_all_exact=int(sum(x["all_exact"] for x in log_rows)),
        note=("exact identity uses model bytes + SAT args, so same-bit aliases collapse; "
              "temporary names are never used as a cache key"))
    (T13 / "dedup_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False,
                                                        indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())