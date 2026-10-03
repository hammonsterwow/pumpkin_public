"""Train koELECTRA order slot classifiers.

This script trains three sentence-level classifiers using ORDER rows only:
- menu
- temperature
- quantity

Usage:
    python -m nlu.train_order_slots --data data/intent_dataset.csv
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
DEFAULT_OUTPUT_DIR = "nlu/saved_models"
SLOT_NAMES = ["menu", "temperature", "quantity"]


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def normalize_quantity(value: Any) -> str:
    if pd.isna(value):
        return "NONE"
    text = str(value).strip()
    if text == "" or text.lower() == "nan":
        return "NONE"
    try:
        number = float(text)
        if number.is_integer():
            return str(int(number))
    except ValueError:
        pass
    return text


def normalize_slot_value(slot_name: str, value: Any) -> str:
    if slot_name == "quantity":
        return normalize_quantity(value)

    if pd.isna(value):
        return "NONE"
    text = str(value).strip()
    if text == "" or text.lower() == "nan":
        return "NONE"
    return text


def load_order_data(csv_path: str | Path) -> pd.DataFrame:
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"Dataset not found: {path}")

    df = pd.read_csv(path)
    required_columns = {"text", "label", *SLOT_NAMES}
    missing = required_columns - set(df.columns)
    if missing:
        raise ValueError(f"Dataset must contain columns {sorted(required_columns)}. Missing: {sorted(missing)}")

    order_df = df[df["label"].astype(str).str.strip() == "ORDER"].copy()
    order_df["text"] = order_df["text"].astype(str).str.strip()
    order_df = order_df[order_df["text"] != ""]

    if order_df.empty:
        raise ValueError("No ORDER rows found in dataset.")

    for slot_name in SLOT_NAMES:
        order_df[slot_name] = order_df[slot_name].apply(lambda value: normalize_slot_value(slot_name, value))

    return order_df


def compute_metrics(eval_pred):
    logits, labels = eval_pred
    preds = np.argmax(logits, axis=-1)
    return {
        "accuracy": accuracy_score(labels, preds),
        "macro_f1": f1_score(labels, preds, average="macro", zero_division=0),
    }


def make_training_args(args: argparse.Namespace, slot_output_dir: Path) -> TrainingArguments:
    kwargs = dict(
        output_dir=str(slot_output_dir / "checkpoints"),
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
    return TrainingArguments(**kwargs)


def train_slot_model(slot_name: str, order_df: pd.DataFrame, tokenizer: AutoTokenizer, args: argparse.Namespace) -> None:
    print(f"\n=== Training {slot_name} classifier ===")

    data = order_df[["text", slot_name]].copy()
    data = data.rename(columns={slot_name: "slot_label"})

    label_encoder = LabelEncoder()
    data["labels"] = label_encoder.fit_transform(data["slot_label"])

    id2label = {int(idx): label for idx, label in enumerate(label_encoder.classes_)}
    label2id = {label: int(idx) for idx, label in id2label.items()}

    if len(label2id) < 2:
        print(f"Skipping {slot_name}: only one label exists: {label2id}")
        return

    stratify = data["labels"] if data["labels"].value_counts().min() >= 2 else None
    train_df, valid_df = train_test_split(
        data[["text", "labels"]],
        test_size=args.test_size,
        random_state=args.seed,
        stratify=stratify,
    )

    def tokenize(batch: dict[str, list[Any]]) -> dict[str, Any]:
        return tokenizer(batch["text"], truncation=True, max_length=args.max_length)

    train_dataset = Dataset.from_pandas(train_df, preserve_index=False).map(tokenize, batched=True)
    valid_dataset = Dataset.from_pandas(valid_df, preserve_index=False).map(tokenize, batched=True)

    model = AutoModelForSequenceClassification.from_pretrained(
        args.model_name,
        num_labels=len(label2id),
        id2label=id2label,
        label2id=label2id,
    )

    slot_output_dir = Path(args.output_dir) / f"{slot_name}_model"
    slot_output_dir.mkdir(parents=True, exist_ok=True)

    training_args = make_training_args(args, slot_output_dir)

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

    trainer.save_model(str(slot_output_dir))
    tokenizer.save_pretrained(str(slot_output_dir))

    with (slot_output_dir / "label_map.json").open("w", encoding="utf-8") as f:
        json.dump({"id2label": id2label, "label2id": label2id}, f, ensure_ascii=False, indent=2)

    with (slot_output_dir / "eval_metrics.json").open("w", encoding="utf-8") as f:
        json.dump({k: float(v) for k, v in metrics.items()}, f, ensure_ascii=False, indent=2)

    print(f"Saved {slot_name} model to: {slot_output_dir}")
    print(json.dumps(metrics, ensure_ascii=False, indent=2))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train koELECTRA order slot classifiers.")
    parser.add_argument("--data", default=DEFAULT_DATA_PATH, help="CSV path with text,label,menu,temperature,quantity columns.")
    parser.add_argument("--model-name", default=DEFAULT_MODEL_NAME, help="Hugging Face model name.")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR, help="Directory to save trained slot models.")
    parser.add_argument("--epochs", type=float, default=15, help="Number of training epochs.")
    parser.add_argument("--batch-size", type=int, default=4, help="Per-device train/eval batch size.")
    parser.add_argument("--learning-rate", type=float, default=3e-5, help="Learning rate.")
    parser.add_argument("--weight-decay", type=float, default=0.01, help="Weight decay.")
    parser.add_argument("--test-size", type=float, default=0.2, help="Validation split ratio.")
    parser.add_argument("--max-length", type=int, default=64, help="Maximum token length.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    set_seed(args.seed)

    order_df = load_order_data(args.data)
    print("ORDER rows:", len(order_df))
    for slot_name in SLOT_NAMES:
        print(f"\n{slot_name} labels:")
        print(order_df[slot_name].value_counts())

    tokenizer = AutoTokenizer.from_pretrained(args.model_name)

    for slot_name in SLOT_NAMES:
        train_slot_model(slot_name, order_df, tokenizer, args)


if __name__ == "__main__":
    main()
