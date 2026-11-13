import argparse
import copy
import csv
import os
import random

import numpy as np
import torch
import torch.nn.functional as F
import yaml
from sklearn.metrics import confusion_matrix, f1_score, precision_score, recall_score

from data_loader import get_siamese_data
from models.gin_net import GINNodeClassifier
from train import siamese_loss


def seed_everything(seed):
    random.seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


def frange(start, stop, step=0.1):
    n = int(round((stop - start) / step))
    return [round(start + i * step, 1) for i in range(n + 1)]


def eval_split(logits, labels, threshold):
    probs = F.softmax(logits, dim=1)[:, 1]
    pred = (probs >= threshold).long().cpu().numpy()
    true = labels.cpu().numpy()
    tn, fp, fn, tp = confusion_matrix(true, pred, labels=[0, 1]).ravel()
    return {
        "macro_f1": f1_score(true, pred, average="macro", zero_division=0),
        "trojan_f1": f1_score(true, pred, pos_label=1, zero_division=0),
        "recall": recall_score(true, pred, pos_label=1, zero_division=0),
        "precision": precision_score(true, pred, pos_label=1, zero_division=0),
        "fpr": fp / (fp + tn + 1e-10),
        "tp": int(tp),
        "fp": int(fp),
        "tn": int(tn),
        "fn": int(fn),
    }


def combined_score(orig, trans):
    avg_macro = (orig["macro_f1"] + trans["macro_f1"]) / 2
    avg_trojan_f1 = (orig["trojan_f1"] + trans["trojan_f1"]) / 2
    avg_recall = (orig["recall"] + trans["recall"]) / 2
    avg_fpr = (orig["fpr"] + trans["fpr"]) / 2
    gap = abs(orig["macro_f1"] - trans["macro_f1"])
    score = 0.5 * avg_macro + avg_trojan_f1 + 0.3 * avg_recall - 0.3 * avg_fpr - 0.2 * gap
    if avg_recall < 0.5:
        score -= 2.0 * (0.5 - avg_recall)
    return score


def evaluate_thresholds(model, data_orig, data_trans, split, thresholds):
    model.eval()
    mask_o = getattr(data_orig, f"{split}_mask")
    mask_t = getattr(data_trans, f"{split}_mask")
    with torch.no_grad():
        logits_o = model(data_orig.x, data_orig.edge_index)[mask_o]
        logits_t = model(data_trans.x, data_trans.edge_index)[mask_t]

    best = None
    for threshold in thresholds:
        metrics_o = eval_split(logits_o, data_orig.y[mask_o], threshold)
        metrics_t = eval_split(logits_t, data_trans.y[mask_t], threshold)
        score = combined_score(metrics_o, metrics_t)
        row = {
            "threshold": threshold,
            "score": score,
            "orig": metrics_o,
            "trans": metrics_t,
            "avg_macro_f1": (metrics_o["macro_f1"] + metrics_t["macro_f1"]) / 2,
            "avg_trojan_f1": (metrics_o["trojan_f1"] + metrics_t["trojan_f1"]) / 2,
            "avg_recall": (metrics_o["recall"] + metrics_t["recall"]) / 2,
            "avg_precision": (metrics_o["precision"] + metrics_t["precision"]) / 2,
            "avg_fpr": (metrics_o["fpr"] + metrics_t["fpr"]) / 2,
            "gap": abs(metrics_o["macro_f1"] - metrics_t["macro_f1"]),
        }
        if best is None or score > best["score"]:
            best = row
    return best


def train_once(config, data_orig, data_trans, params, thresholds, seed, epochs):
    seed_everything(seed)
    device = data_orig.x.device
    model = GINNodeClassifier(
        in_channels=config["model"]["in_channels"],
        hidden_channels=config["model"]["hidden_channels"],
        out_channels=config["model"]["out_channels"],
        num_layers=config["model"]["num_layers"],
    ).to(device)
    optimizer = torch.optim.Adam(
        model.parameters(),
        lr=float(config["train"]["lr"]),
        weight_decay=float(config["train"]["weight_decay"]),
    )

    best = None
    best_state = None
    warmup_epochs = int(epochs * params["warmup_ratio"])
    for epoch in range(epochs):
        model.train()
        optimizer.zero_grad()
        preds_o = model(data_orig.x, data_orig.edge_index)
        preds_t = model(data_trans.x, data_trans.edge_index)
        lambda_const = 0.0 if epoch < warmup_epochs else params["lambda_const"]
        loss, *_ = siamese_loss(
            preds_o[data_orig.train_mask],
            preds_t[data_trans.train_mask],
            data_orig.y[data_orig.train_mask],
            data_trans.y[data_trans.train_mask],
            lambda_const=lambda_const,
            lambda_det=params["lambda_det"],
            lambda_nor=params["lambda_nor"],
            trojan_w=params["trojan_w"],
        )
        loss.backward()
        optimizer.step()

        if (epoch + 1) % 10 == 0 or epoch == epochs - 1:
            val = evaluate_thresholds(model, data_orig, data_trans, "val", thresholds)
            if best is None or val["score"] > best["score"]:
                best = copy.deepcopy(val)
                best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}

    model.load_state_dict(best_state)
    test = evaluate_thresholds(model, data_orig, data_trans, "test", [best["threshold"]])
    return best, test, best_state


def flatten_result(params, val, test):
    row = {
        **params,
        "val_threshold": val["threshold"],
        "val_score": val["score"],
        "val_avg_macro_f1": val["avg_macro_f1"],
        "val_avg_trojan_f1": val["avg_trojan_f1"],
        "val_avg_recall": val["avg_recall"],
        "val_avg_precision": val["avg_precision"],
        "val_avg_fpr": val["avg_fpr"],
        "val_gap": val["gap"],
        "test_score": test["score"],
        "test_avg_macro_f1": test["avg_macro_f1"],
        "test_avg_trojan_f1": test["avg_trojan_f1"],
        "test_avg_recall": test["avg_recall"],
        "test_avg_precision": test["avg_precision"],
        "test_avg_fpr": test["avg_fpr"],
        "test_gap": test["gap"],
    }
    for prefix, block in [("test_orig", test["orig"]), ("test_trans", test["trans"])]:
        for key, value in block.items():
            row[f"{prefix}_{key}"] = value
    return row


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--epochs", type=int, default=120)
    parser.add_argument("--seed", type=int, default=43)
    parser.add_argument("--out", default="sweep_results.csv")
    parser.add_argument("--best-model", default="pytorch_models/best_sweep_siamese_gin.pkl")
    parser.add_argument("--phase", choices=["trojan_w", "lambda_nor", "lambda_det", "lambda_const"])
    parser.add_argument("--single", action="store_true")
    parser.add_argument("--fixed-trojan-w", type=float, default=5.0)
    parser.add_argument("--fixed-lambda-nor", type=float, default=2.0)
    parser.add_argument("--fixed-lambda-det", type=float, default=0.3)
    parser.add_argument("--fixed-lambda-const", type=float, default=0.0)
    parser.add_argument("--warmup-ratio", type=float, default=0.3)
    args = parser.parse_args()

    with open("config.yaml", "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    data_orig, data_trans = get_siamese_data(config)
    thresholds = frange(0.1, 0.9, 0.1)
    if args.single:
        params = {
            "trojan_w": args.fixed_trojan_w,
            "lambda_nor": args.fixed_lambda_nor,
            "lambda_det": args.fixed_lambda_det,
            "lambda_const": args.fixed_lambda_const,
            "warmup_ratio": args.warmup_ratio,
        }
        val, test, state = train_once(config, data_orig, data_trans, params, thresholds, args.seed, args.epochs)
        row = flatten_result(params, val, test)
        os.makedirs(os.path.dirname(args.best_model), exist_ok=True)
        torch.save(state, args.best_model)
        with open(args.out, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(row.keys()))
            writer.writeheader()
            writer.writerow(row)
        print("SINGLE_RUN")
        for key, value in row.items():
            print(f"{key}: {value}")
        return

    if args.phase is None:
        raise ValueError("--phase is required unless --single is set")

    phase_ranges = {
        "trojan_w": frange(1.0, 8.0, 0.1),
        "lambda_nor": frange(0.0, 5.0, 0.1),
        "lambda_det": frange(0.0, 1.0, 0.1),
        "lambda_const": frange(0.0, 5.0, 0.1),
    }

    rows = []
    best_overall = None
    best_state = None
    values = phase_ranges[args.phase]
    os.makedirs(os.path.dirname(args.best_model), exist_ok=True)
    for idx, value in enumerate(values, 1):
        params = {
            "trojan_w": args.fixed_trojan_w,
            "lambda_nor": args.fixed_lambda_nor,
            "lambda_det": args.fixed_lambda_det,
            "lambda_const": args.fixed_lambda_const,
            "warmup_ratio": args.warmup_ratio,
        }
        params[args.phase] = value
        val, test, state = train_once(config, data_orig, data_trans, params, thresholds, args.seed, args.epochs)
        row = flatten_result(params, val, test)
        rows.append(row)
        if best_overall is None or val["score"] > best_overall["val_score"]:
            best_overall = row
            best_state = state
            torch.save(best_state, args.best_model)
        print(
            f"[{idx:03d}/{len(values):03d}] {args.phase}={value:.1f} "
            f"val_score={row['val_score']:.4f} test_macro={row['test_avg_macro_f1']:.4f} "
            f"thr={row['val_threshold']:.1f}"
        )

    with open(args.out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    print("BEST_BY_VAL")
    for key, value in best_overall.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
