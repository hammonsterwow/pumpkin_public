"""Train a koELECTRA intent classifier for STT-generated Korean text.

Usage:
    python -m nlu.train_intent --data data/intent_dataset.csv

The trained model is saved to nlu/saved_models/intent_model by default.
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import torch
from sklearn.metrics import accuracy_score, f1_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    DataCollatorWithPadding,
    Trainer,
    TrainingArguments,
)

try:
    from datasets import Dataset
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "The 'datasets' package is required. Install dependencies with: "
        "pip install -r requirements.txt"
    ) from exc


DEFAULT_MODEL_NAME = "monologg/koelectra-small-v3-discriminator"
DEFAULT_DATA_PATH = "data/intent_dataset.csv"
DEFAULT_OUTPUT_DIR = "nlu/saved_models/intent_model"


REQUIRED_COLUMNS = {"text", "label"}


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def load_intent_data(csv_path: str | Path) -> pd.DataFrame:
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"Dataset not found: {path}")

    df = pd.read_csv(path)
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"Dataset must contain columns {sorted(REQUIRED_COLUMNS)}. Missing: {sorted(missing)}")

    df = df[["text", "label"]].dropna().copy()
    df["text"] = df["text"].astype(str).str.strip()
    df["label"] = df["label"].astype(str).str.strip()
    df = df[(df["text"] != "") & (df["label"] != "")]

    if df.empty:
        raise ValueError("Dataset is empty after removing blank text/label rows.")

    return df


def make_datasets(df: pd.DataFrame, tokenizer: AutoTokenizer, test_size: float, seed: int, max_length: int):
    label_encoder = LabelEncoder()
    df = df.copy()
    df["labels"] = label_encoder.fit_transform(df["label"])

    stratify = df["labels"] if df["labels"].value_counts().min() >= 2 else None
    train_df, valid_df = train_test_split(
        df[["text", "labels"]],
        test_size=test_size,
        random_state=seed,
        stratify=stratify,
    )

    def tokenize(batch: dict[str, list[Any]]) -> dict[str, Any]:
        return tokenizer(batch["text"], truncation=True, max_length=max_length)

    train_dataset = Dataset.from_pandas(train_df, preserve_index=False).map(tokenize, batched=True)
    valid_dataset = Dataset.from_pandas(valid_df, preserve_index=False).map(tokenize, batched=True)

    id2label = {int(idx): label for idx, label in enumerate(label_encoder.classes_)}
    label2id = {label: int(idx) for idx, label in id2label.items()}

    return train_dataset, valid_dataset, id2label, label2id


def compute_metrics(eval_pred):
    logits, labels = eval_pred
    preds = np.argmax(logits, axis=-1)
    return {
        "accuracy": accuracy_score(labels, preds),
        "macro_f1": f1_score(labels, preds, average="macro"),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train koELECTRA intent classifier.")
    parser.add_argument("--data", default=DEFAULT_DATA_PATH, help="CSV path with text,label columns.")
    parser.add_argument("--model-name", default=DEFAULT_MODEL_NAME, help="Hugging Face model name.")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR, help="Directory to save trained model.")
    parser.add_argument("--epochs", type=float, default=8, help="Number of training epochs.")
    parser.add_argument("--batch-size", type=int, default=8, help="Per-device train/eval batch size.")
    parser.add_argument("--learning-rate", type=float, default=3e-5, help="Learning rate.")
    parser.add_argument("--weight-decay", type=float, default=0.01, help="Weight decay.")
    parser.add_argument("--test-size", type=float, default=0.2, help="Validation split ratio.")
    parser.add_argument("--max-length", type=int, default=64, help="Maximum token length.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    set_seed(args.seed)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    df = load_intent_data(args.data)
    tokenizer = AutoTokenizer.from_pretrained(args.model_name)
    train_dataset, valid_dataset, id2label, label2id = make_datasets(
        df=df,
        tokenizer=tokenizer,
        test_size=args.test_size,
        seed=args.seed,
        max_length=args.max_length,
    )

    model = AutoModelForSequenceClassification.from_pretrained(
        args.model_name,
        num_labels=len(label2id),
        id2label=id2label,
        label2id=label2id,
    )

    training_args = TrainingArguments(
        output_dir=str(output_dir / "checkpoints"),
        evaluation_strategy="epoch",
        save_strategy="epoch",
        learning_rate=args.learning_rate,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.batch_size,
        num_train_epochs=args.epochs,
        weight_decay=args.weight_decay,
        logging_steps=10,
        load_best_model_at_end=True,
        metric_for_best_model="macro_f1",
        greater_is_better=True,
        report_to="none",
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=valid_dataset,
        tokenizer=tokenizer,
        data_collator=DataCollatorWithPadding(tokenizer=tokenizer),
        compute_metrics=compute_metrics,
    )

    trainer.train()
    metrics = trainer.evaluate()

    trainer.save_model(str(output_dir))
    tokenizer.save_pretrained(str(output_dir))

    label_map = {"id2label": id2label, "label2id": label2id}
    with (output_dir / "label_map.json").open("w", encoding="utf-8") as f:
        json.dump(label_map, f, ensure_ascii=False, indent=2)

    with (output_dir / "eval_metrics.json").open("w", encoding="utf-8") as f:
        json.dump({k: float(v) for k, v in metrics.items()}, f, ensure_ascii=False, indent=2)

    print(f"Saved intent model to: {output_dir}")
    print(json.dumps(metrics, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
