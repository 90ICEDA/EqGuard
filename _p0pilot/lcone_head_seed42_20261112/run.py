"""Seed42 validation-only B/C exploration on frozen N-best encoder features."""
import csv
import hashlib
import json
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch
from torch.nn import functional as F

OUT = Path(__file__).resolve().parent
P = OUT.parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(P / "lcone_head_protocol_20261112"))
from eval_gate import evaluate_view, head, prefix, queues, validation_inputs
from gate import TRAIN, VAL, sha, training_inputs


def write(name, value):
    with (OUT / name).open("x", encoding="utf-8") as f:
        json.dump(value, f, indent=2, allow_nan=False)


def views(asset, rows, anchor):
    data = defaultdict(dict)
    for r in rows:
        assert r["feature_available"]
        i = r["feature_row"]
        mem = asset["members"][asset["ptr"][i]:asset["ptr"][i+1]]
        m = float(anchor[mem].max())
        assert m == float(asset["B"][i, 0])
        winner = int(mem[anchor[mem] == m].min())
        data[r["view"], r["kind"]][r["cone_id"]] = (r["status"], mem, i, winner)
    return data


def one_group(rr, scores):
    group = {cid: (r[0], r[1]) for cid, r in rr.items()}
    vals = {cid: float(scores[r[2]]) for cid, r in rr.items()}
    anchor_group = {cid: r[3] for cid, r in rr.items()}
    return group, vals, anchor_group


def validation_selection(data, scores):
    source = defaultdict(list)
    for (view, kind), rr in data.items():
        if kind != "D":
            continue
        group, values, fixed = one_group(rr, scores)
        npos = sum(label == "positive" for label, _ in group.values())
        if npos:
            # The main policy checks endpoints in score order and charges physical gate union.
            order = [[c] for c in sorted(values, key=lambda c: (-values[c], c))]
            checked = prefix(order, group, max_gates=512)
            source[view.rsplit("__ys_", 1)[0]].append(checked["positive"] / npos)
    assert len(source) == 5
    return st.mean(st.mean(v) for v in source.values())


def full_results(data, scores, arm, point, step):
    result = []
    for (view, kind), rr in sorted(data.items()):
        group, vals, fixed = one_group(rr, scores)
        caps = (128, 256, 512, 1024) if kind == "D" else (32, 64, 128, 256)
        pos = sum(x[0] == "positive" for x in group.values())
        neg = sum(x[0] == "negative" for x in group.values())
        source, recipe = view.rsplit("__ys_", 1)
        result_metrics = evaluate_view(group, vals, fixed, caps)
        if pos:
            for policy, queue in queues(vals, fixed).items():
                result_metrics[policy].update({f"top_{k}": prefix(queue, group, max_units=k) for k in (1, 5, 10)})
        for policy, metrics in result_metrics.items():
            for setting, m in metrics.items():
                result.append(dict(arm=arm, point=point, step=step, view=view, source=source, recipe=recipe,
                                   kind=kind, policy=policy, setting=setting, pos=pos, neg=neg,
                                   recall=m["positive"] / pos, fpr=m["negative"] / neg if neg else None, **m))
    return result


def macro(rows):
    groups = defaultdict(lambda: defaultdict(list))
    for r in rows:
        for rec in ("all", r["recipe"]):
            k = "|".join(str(r[n]) for n in ("arm", "point", "kind", "policy", "setting")) + "|" + rec
            groups[k][r["source"]].append(r)
    columns = ("recall", "fpr", "units", "endpoint_count", "gates", "positive", "negative", "unknown")
    result = {}
    for k, sources in groups.items():
        per = {s: {m: st.mean(r[m] for r in group if r[m] is not None) if any(r[m] is not None for r in group) else None
                   for m in columns} for s, group in sources.items()}
        result[k] = dict(sources=len(per), views=sum(map(len, sources.values())),
                         per_source=per, macro={m: st.mean(v[m] for v in per.values() if v[m] is not None)
                                                if any(v[m] is not None for v in per.values()) else None for m in columns})
    return result


def state_digest(state):
    h = hashlib.sha256()
    for name, v in state.items():
        h.update(name.encode())
        h.update(v.detach().cpu().contiguous().numpy().tobytes())
    return h.hexdigest()


def save_checkpoint(path, model, opt, step, selection, rng):
    with path.open("xb") as f:
        torch.save(dict(state=model.state_dict(), optimizer=opt.state_dict(), step=step,
                        selection=selection, rng=rng), f)


def main():
    assert torch.cuda.is_available() and "ginvenv_gpu" in sys.executable.lower()
    training, label, schedule = training_inputs()
    val, meta = validation_inputs("best")
    with np.load(P / "seed42_nc_ablation_20261109/N_scores.npz", allow_pickle=False) as f:
        data = views(val, meta, f["val_best"])
    assert schedule.shape == (50, 54)
    contract = dict(seed=42, encoder="frozen N seed42 best", updates_per_arm=50, optimization_dtype="float32",
                    optimizer="Adam", lr=0.001, weight_decay=0.001, loss="mean binary cross entropy on logits",
                    selection="validation D macro recall at 512 physical gates, endpoint queue, every 5 steps; earliest tie",
                    arm_B="8 common scalars with zero padding", arm_C="same scalars plus directed cone context",
                    confirmation_predictions_read=0, sat_calls=0, source_labels_changed=False,
                    assets={str(p.relative_to(P)): sha(p) for p in (
                        TRAIN / "BC_INPUT_SEED42_N_BEST.npz", TRAIN / "BC_BUDGET.json",
                        TRAIN / "COMMON_STEPS.npy", VAL / "VAL_BC_SEED42_N_BEST.npz",
                        VAL / "VAL_INVENTORY.json", P / "seed42_nc_ablation_20261109/N_best.pt")})
    write("RUN_CONTRACT.json", contract)
    torch.manual_seed(42)
    initial = head().cuda().state_dict()
    initial_digest = state_digest(initial)
    y = torch.as_tensor(label, device="cuda")
    logs = []
    results = full_results(data, val["B"][:, 0], "A", "frozen", 0)
    checkpoints = {}
    gate = json.loads((VAL / "NO_UPDATE_GATE.json").read_text(encoding="utf-8"))
    for arm in ("B", "C"):
        torch.manual_seed(42)
        model = head().cuda()
        model.load_state_dict(initial, strict=True)
        assert state_digest(model.state_dict()) == initial_digest
        opt = torch.optim.Adam(model.parameters(), lr=contract["lr"], weight_decay=contract["weight_decay"])
        tx = torch.as_tensor(training[arm], device="cuda")
        vx = torch.as_tensor(val[arm], device="cuda")
        folder = OUT / arm
        folder.mkdir(exist_ok=False)
        high, best_step = -1.0, None
        best_scores, best_state, best_optimizer, best_rng = None, None, None, None
        for step, r in enumerate(schedule, 1):
            model.train()
            opt.zero_grad(set_to_none=True)
            ids = torch.as_tensor(r, device="cuda")
            logits = model(tx[ids]).flatten()
            loss = F.binary_cross_entropy_with_logits(logits, y[ids])
            assert torch.isfinite(loss)
            loss.backward()
            grads = [p.grad for p in model.parameters()]
            assert all(g is not None and torch.isfinite(g).all() for g in grads)
            grad_norm = float(torch.sqrt(sum(g.square().sum() for g in grads)))
            assert grad_norm > 0
            if step == 1:
                assert abs(float(loss.detach()) - gate["arm"][arm]["loss"]) < 1e-6
                assert abs(grad_norm - gate["arm"][arm]["gradient_norm"]) < 1e-5
            opt.step()
            assert all(torch.isfinite(p).all() for p in model.parameters())
            entry = dict(arm=arm, step=step, loss=float(loss.detach()), grad_norm=grad_norm,
                         rows_sha256=hashlib.sha256(r.tobytes()).hexdigest(), positive=int(y[ids].sum()),
                         val_D_recall_512=None)
            if step % 5 == 0:
                model.eval()
                with torch.inference_mode():
                    pred = model(vx).flatten().cpu().numpy()
                assert np.isfinite(pred).all()
                selection = validation_selection(data, pred)
                entry["val_D_recall_512"] = selection
                print(f"{arm} step={step} D_recall_512={selection:.6f}", flush=True)
                if selection > high:
                    import copy
                    high, best_step, best_scores = selection, step, pred.copy()
                    best_state = {k: v.detach().clone() for k, v in model.state_dict().items()}
                    best_optimizer = copy.deepcopy(opt.state_dict())
                    best_rng = dict(cpu=torch.get_rng_state(), cuda=torch.cuda.get_rng_state())
            logs.append(entry)
        assert step == 50 and best_scores is not None
        last_scores = pred.copy()
        last_selection = selection
        save_checkpoint(folder / "last.pt", model, opt, step, last_selection,
                        dict(cpu=torch.get_rng_state(), cuda=torch.cuda.get_rng_state()))
        model.load_state_dict(best_state, strict=True)
        opt.load_state_dict(best_optimizer)
        save_checkpoint(folder / "best.pt", model, opt, best_step, high, best_rng)
        with (folder / "VAL_SCORES.npz").open("xb") as f:
            np.savez_compressed(f, keys=val["keys"], best=best_scores, last=last_scores)
        results.extend(full_results(data, best_scores, arm, "best", best_step))
        results.extend(full_results(data, last_scores, arm, "last", 50))
        checkpoints[arm] = dict(best_step=best_step, best_D_recall_512=high, last_D_recall_512=last_selection,
                                best_sha256=sha(folder / "best.pt"), last_sha256=sha(folder / "last.pt"),
                                predictions_sha256=sha(folder / "VAL_SCORES.npz"))
    assert len(logs) == 100
    for b, c in zip(logs[:50], logs[50:]):
        assert b["rows_sha256"] == c["rows_sha256"] and b["positive"] == c["positive"] == 27
    with (OUT / "VAL_BY_VIEW.csv").open("x", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(results[0]))
        w.writeheader()
        w.writerows(results)
    write("RUN_LOG.json", logs)
    write("VAL_SUMMARY.json", macro(results))
    write("RUN_STATUS.json", dict(steps={"B": 50, "C": 50}, init_sha256=initial_digest, validation_only=True,
                                 confirmation_prediction_reads=0, solver_calls=0, checkpoints=checkpoints))
    print(checkpoints)


if __name__ == "__main__":
    main()
