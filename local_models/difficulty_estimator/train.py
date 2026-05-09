"""Train a TF-IDF + Ridge regressor for the difficulty_estimation task.

Why this v0:
  * CPU-only, < 30 s on the full 1k-row corpus.
  * Pure scikit-learn — no GPU, no torch, no Hugging Face download.
  * Saves a single joblib artefact that the `local_classifier` provider
    can load at process start.

This is the *floor* model — the one the router uses while we train a
DistilBERT v1 in the background. Beating it is the bar a transformer
must clear before it ships.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

import joblib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.pipeline import Pipeline


def deterministic_split(content: str, *, train: float = 0.80, val: float = 0.10) -> str:
    """Same split rule as `ai_training.services.dataset_exporter.assign_split`."""
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
            ngram_range=(1, 2),       # unigrams + bigrams
            min_df=2,                 # drop hapaxes (low signal in 1k corpus)
            max_features=20000,
            lowercase=True,
            sublinear_tf=True,
        )),
        ("ridge", Ridge(alpha=1.0)),
    ])
    X = [r["text"] for r in train_rows]
    y = [float(r["label"]) for r in train_rows]
    pipe.fit(X, y)
    return pipe


def evaluate(pipe: Pipeline, rows: list[dict], *, label: str) -> dict:
    if not rows:
        return {"label": label, "n": 0, "mae": None, "r2": None}
    X = [r["text"] for r in rows]
    y = np.array([float(r["label"]) for r in rows])
    yhat = np.clip(pipe.predict(X), 0.0, 1.0)   # difficulty is bounded
    mae = mean_absolute_error(y, yhat)
    r2 = r2_score(y, yhat) if len(set(y)) > 1 else float("nan")
    return {"label": label, "n": len(rows), "mae": float(mae),
            "r2": float(r2),
            "mean_actual": float(y.mean()),
            "mean_pred": float(yhat.mean())}


def baseline_metrics(rows: list[dict], train_mean: float) -> dict:
    """Score a constant 'predict the train mean' baseline so we know what
    the Ridge model has to beat."""
    if not rows:
        return {"n": 0, "mae": None}
    y = np.array([float(r["label"]) for r in rows])
    mae = float(np.mean(np.abs(y - train_mean)))
    return {"n": len(rows), "mae": mae, "constant_pred": train_mean}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True,
                        help="Path to JSONL with {text, label} rows.")
    parser.add_argument("--out", required=True,
                        help="Directory to write the trained artefact + report.")
    parser.add_argument("--max-train-mae", type=float, default=0.20,
                        help="Sanity check — fail loudly if train MAE blows up.")
    args = parser.parse_args()

    data_path = Path(args.data)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = load_jsonl(data_path)
    print(f"Loaded {len(rows)} rows from {data_path}")
    splits = split_rows(rows)
    print(f"Splits: train={len(splits['train'])} "
          f"val={len(splits['validation'])} "
          f"test={len(splits['test'])}")

    pipe = train_model(splits["train"])
    print("Trained.")

    # Constant-mean baseline — what we have to beat.
    train_mean = float(np.mean([r["label"] for r in splits["train"]]))
    baseline = {sp: baseline_metrics(splits[sp], train_mean)
                for sp in ("train", "validation", "test")}

    metrics = {sp: evaluate(pipe, splits[sp], label=sp)
               for sp in ("train", "validation", "test")}

    print("\n=== Metrics ===")
    for sp in ("train", "validation", "test"):
        m = metrics[sp]
        b = baseline[sp]
        print(f"  {sp:11}  n={m['n']:>4}  "
              f"MAE={m['mae']:.4f}  baseline_MAE={b['mae']:.4f}  "
              f"Δ={(b['mae'] - m['mae']):+.4f}  "
              f"R²={m['r2']:.3f}")

    if metrics["train"]["mae"] > args.max_train_mae:
        print(f"\nABORT: train MAE {metrics['train']['mae']:.4f} > "
              f"max_train_mae {args.max_train_mae:.4f} — model failed to fit.",
              file=sys.stderr)
        sys.exit(2)

    # Persist artefact + manifest.
    artefact_path = out_dir / "model.joblib"
    joblib.dump(pipe, artefact_path)
    manifest = {
        "name": "difficulty_estimator",
        "version": "v0-ridge",
        "framework": "scikit-learn",
        "framework_version": __import__("sklearn").__version__,
        "trained_on": str(data_path.resolve()),
        "rows_seen": len(rows),
        "metrics": metrics,
        "baseline": baseline,
        "tfidf_max_features": 20000,
        "ridge_alpha": 1.0,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"\nSaved → {artefact_path}")
    print(f"Saved → {out_dir / 'manifest.json'}")


if __name__ == "__main__":
    main()
