"""Train a TF-IDF + multinomial Logistic Regression CEFR classifier.

Why this v0:
  * 7-class problem on a 1k-row corpus → multinomial LR with class
    rebalancing is the canonical first thing to try. CPU-only, ~10 s.
  * Comparable architecture to `difficulty_estimator/train.py` so the
    serving-side adapter (joblib + provider) is one shape, not two.
  * Saves probability calibration so the provider can report confidence.

Saves the same {model.joblib, manifest.json} pair the difficulty model
uses. The serving side discriminates on `task_type`, not on artefact
shape — so the registry stays uniform.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import joblib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score, classification_report, confusion_matrix, f1_score,
)
from sklearn.pipeline import Pipeline


CEFR_LABELS = ["A0", "A1", "A2", "B1", "B2", "C1", "C2"]


def deterministic_split(content: str, *, train: float = 0.80, val: float = 0.10) -> str:
    """Same split rule as the difficulty trainer + the dataset_exporter
    so test sets are stable across re-trainings."""
    bucket = int(hashlib.sha1(content.encode()).hexdigest()[:8], 16) % 100
    if bucket < int(train * 100):
        return "train"
    if bucket < int((train + val) * 100):
        return "validation"
    return "test"


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def split_rows(rows: list[dict]) -> dict[str, list[dict]]:
    out = {"train": [], "validation": [], "test": []}
    for r in rows:
        out[deterministic_split(r["text"])].append(r)
    return out


def train_model(train_rows: list[dict]) -> Pipeline:
    pipe = Pipeline([
        ("tfidf", TfidfVectorizer(
            ngram_range=(1, 2),
            min_df=2,
            max_features=20000,
            lowercase=True,
            sublinear_tf=True,
        )),
        ("clf", LogisticRegression(
            max_iter=2000,
            C=2.0,
            class_weight="balanced",   # critical — A0/A1 dominate the corpus
            n_jobs=-1,
        )),
    ])
    X = [r["text"] for r in train_rows]
    y = [r["label"] for r in train_rows]
    pipe.fit(X, y)
    return pipe


def per_class_report(y_true, y_pred, labels) -> dict:
    """Tidy dict version of classification_report for the manifest."""
    rep = classification_report(
        y_true, y_pred, labels=labels, zero_division=0, output_dict=True,
    )
    out = {}
    for k in labels:
        if k in rep:
            v = rep[k]
            out[k] = {
                "precision": round(v["precision"], 3),
                "recall":    round(v["recall"], 3),
                "f1":        round(v["f1-score"], 3),
                "support":   int(v["support"]),
            }
    return out


def evaluate(pipe: Pipeline, rows: list[dict], *, label: str) -> dict:
    if not rows:
        return {"label": label, "n": 0}
    X = [r["text"] for r in rows]
    y = [r["label"] for r in rows]
    yhat = list(pipe.predict(X))
    acc = accuracy_score(y, yhat)
    macro_f1 = f1_score(y, yhat, labels=CEFR_LABELS, average="macro", zero_division=0)
    cm = confusion_matrix(y, yhat, labels=CEFR_LABELS).tolist()
    return {
        "label": label, "n": len(rows),
        "accuracy": float(acc),
        "macro_f1": float(macro_f1),
        "per_class": per_class_report(y, yhat, CEFR_LABELS),
        "confusion": {"labels": CEFR_LABELS, "matrix": cm},
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--min-train-acc", type=float, default=0.85,
                        help="Sanity: abort if training accuracy is bad.")
    args = parser.parse_args()

    data_path = Path(args.data)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = load_jsonl(data_path)
    print(f"Loaded {len(rows)} rows from {data_path}")
    splits = split_rows(rows)
    print(f"Splits: train={len(splits['train'])} "
          f"val={len(splits['validation'])} test={len(splits['test'])}")

    pipe = train_model(splits["train"])
    print("Trained.")

    metrics = {sp: evaluate(pipe, splits[sp], label=sp)
               for sp in ("train", "validation", "test")}

    print("\n=== Metrics ===")
    for sp in ("train", "validation", "test"):
        m = metrics[sp]
        if not m.get("n"):
            print(f"  {sp:11}  empty")
            continue
        print(f"  {sp:11}  n={m['n']:>4}  "
              f"accuracy={m['accuracy']:.3f}  macro_F1={m['macro_f1']:.3f}")

    print("\n=== Per-class (test) ===")
    for k, v in metrics["test"]["per_class"].items():
        bar = "█" * int(v["f1"] * 20)
        print(f"  {k}  P={v['precision']:.2f}  R={v['recall']:.2f}  "
              f"F1={v['f1']:.2f}  n={v['support']:>3}  {bar}")

    if metrics["train"]["accuracy"] < args.min_train_acc:
        print(f"\nABORT: train accuracy {metrics['train']['accuracy']:.3f} "
              f"< min {args.min_train_acc:.3f} — model failed to fit.",
              file=sys.stderr)
        sys.exit(2)

    artefact_path = out_dir / "model.joblib"
    joblib.dump(pipe, artefact_path)
    manifest = {
        "name": "cefr_classifier",
        "version": "v0-logreg",
        "framework": "scikit-learn",
        "framework_version": __import__("sklearn").__version__,
        "trained_on": str(data_path.resolve()),
        "rows_seen": len(rows),
        "labels": CEFR_LABELS,
        "metrics": metrics,
        "tfidf_max_features": 20000,
        "C": 2.0,
        "class_weight": "balanced",
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"\nSaved → {artefact_path}")
    print(f"Saved → {out_dir / 'manifest.json'}")


if __name__ == "__main__":
    main()
