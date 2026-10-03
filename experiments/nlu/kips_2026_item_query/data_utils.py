import json
import math
import random
from collections import Counter
from pathlib import Path

import torch
from sklearn.model_selection import train_test_split
from torch.utils.data import DataLoader, Dataset, WeightedRandomSampler

from .config import (
    BATCH_SIZE,
    INTENT_LABELS,
    MAX_ITEMS,
    MAX_LENGTH,
    MENU_LABELS,
    NUM_WORKERS,
    QUANTITY_LABELS,
    SPLIT_SEED,
    STATUS_LABELS,
    TEMPERATURE_LABELS,
    VALID_RATIO,
)


def make_maps(labels):
    label2id = {v: i for i, v in enumerate(labels)}
    id2label = {i: v for v, i in label2id.items()}
    return label2id, id2label


intent2id, id2intent = make_maps(INTENT_LABELS)
status2id, id2status = make_maps(STATUS_LABELS)
menu2id, id2menu = make_maps(MENU_LABELS)
temp2id, id2temp = make_maps(TEMPERATURE_LABELS)
qty2id, id2qty = make_maps(QUANTITY_LABELS)


def load_jsonl(path: Path):
    records = []
    with path.open('r', encoding='utf-8') as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f'{path}:{line_no}: {exc}') from exc
    return records


def normalize_menu(value):
    if value is None:
        return 'NONE'
    text = str(value).strip()
    aliases = {
        '라떼': '카페라떼',
        '카페라테': '카페라떼',
        '바닐라 라떼': '바닐라라떼',
        '바닐라라테': '바닐라라떼',
    }
    text = aliases.get(text, text)
    return text if text in menu2id else 'NONE'


def normalize_temperature(value):
    text = 'NONE' if value is None else str(value).strip().upper()
    return text if text in temp2id else 'NONE'


def normalize_quantity(value):
    if value is None or str(value).strip() == '':
        return 'NONE'
    try:
        text = str(int(float(value)))
    except (TypeError, ValueError):
        return 'NONE'
    return text if text in qty2id else 'NONE'


def normalize_status(record):
    if str(record.get('intent') or 'UNKNOWN') != 'ORDER':
        return 'NONE'
    status = str(record.get('order_status') or 'UNPARSABLE')
    return status if status in status2id else 'UNPARSABLE'


def item_count(record):
    if str(record.get('intent')) != 'ORDER':
        return 0
    return min(MAX_ITEMS, len(record.get('items') or []))


def _safe_split(records, strata):
    if len(records) < 2:
        return list(records), []
    counts = Counter(strata)
    stratify = strata if counts and len(counts) > 1 and min(counts.values()) >= 2 else None
    train, valid = train_test_split(
        records,
        test_size=VALID_RATIO,
        random_state=SPLIT_SEED,
        stratify=stratify,
    )
    return list(train), list(valid)


def split_train_valid(pool):
    single, multi, followup, other = [], [], [], []

    for record in pool:
        source = record.get('source') or {}
        kind = str(source.get('kind') or '').lower()
        count = item_count(record)

        if kind == 'followup':
            followup.append(record)
        elif kind == 'multi' or count >= 2:
            multi.append(record)
        elif kind == 'single' or (str(record.get('intent')) == 'ORDER' and count == 1):
            single.append(record)
        else:
            other.append(record)

    with_template = [
        r for r in single
        if (r.get('source') or {}).get('template_id') is not None
    ]
    without_template = [
        r for r in single
        if (r.get('source') or {}).get('template_id') is None
    ]

    single_train, single_valid = [], []
    if with_template:
        template_ids = sorted({
            str((r.get('source') or {}).get('template_id'))
            for r in with_template
        })
        rng = random.Random(SPLIT_SEED)
        rng.shuffle(template_ids)
        n_valid = max(1, int(round(len(template_ids) * VALID_RATIO))) if len(template_ids) > 1 else 0
        valid_ids = set(template_ids[:n_valid])
        single_valid.extend([
            r for r in with_template
            if str((r.get('source') or {}).get('template_id')) in valid_ids
        ])
        single_train.extend([
            r for r in with_template
            if str((r.get('source') or {}).get('template_id')) not in valid_ids
        ])

    if without_template:
        train_part, valid_part = _safe_split(
            without_template,
            [normalize_status(r) for r in without_template],
        )
        single_train.extend(train_part)
        single_valid.extend(valid_part)

    multi_train, multi_valid = _safe_split(
        multi,
        [
            f"{item_count(r)}:{(r.get('source') or {}).get('category', 'unknown')}"
            for r in multi
        ],
    )
    follow_train, follow_valid = _safe_split(
        followup,
        [str((r.get('source') or {}).get('category') or 'unknown') for r in followup],
    )
    other_train, other_valid = _safe_split(
        other,
        [str(r.get('intent') or 'UNKNOWN') for r in other],
    )

    train_records = single_train + multi_train + follow_train + other_train
    valid_records = single_valid + multi_valid + follow_valid + other_valid
    rng = random.Random(SPLIT_SEED)
    rng.shuffle(train_records)
    rng.shuffle(valid_records)
    return train_records, valid_records


class StructureBDataset(Dataset):
    def __init__(self, records, tokenizer):
        self.records = records
        self.tokenizer = tokenizer

    def __len__(self):
        return len(self.records)

    def __getitem__(self, index):
        record = self.records[index]
        text = str(record.get('text') or '').strip()
        encoded = self.tokenizer(
            text,
            truncation=True,
            max_length=MAX_LENGTH,
            padding='max_length',
            return_tensors='pt',
        )

        active = [0] * MAX_ITEMS
        menus = [menu2id['NONE']] * MAX_ITEMS
        temperatures = [temp2id['NONE']] * MAX_ITEMS
        quantities = [qty2id['NONE']] * MAX_ITEMS

        if str(record.get('intent')) == 'ORDER':
            items = sorted(
                (record.get('items') or [])[:MAX_ITEMS],
                key=lambda x: int(x.get('item_id', 0)),
            )
            for item_index, item in enumerate(items):
                active[item_index] = 1
                menus[item_index] = menu2id[normalize_menu(item.get('menu'))]
                temperatures[item_index] = temp2id[normalize_temperature(item.get('temperature'))]
                quantities[item_index] = qty2id[normalize_quantity(item.get('quantity'))]

        return {
            'input_ids': encoded['input_ids'].squeeze(0),
            'attention_mask': encoded['attention_mask'].squeeze(0),
            'intent_label': torch.tensor(
                intent2id.get(str(record.get('intent') or 'UNKNOWN'), intent2id['UNKNOWN'])
            ),
            'status_label': torch.tensor(status2id[normalize_status(record)]),
            'item_active': torch.tensor(active),
            'menu_labels': torch.tensor(menus),
            'temperature_labels': torch.tensor(temperatures),
            'quantity_labels': torch.tensor(quantities),
            'text': text,
        }


def build_loader(records, tokenizer, config, train=False, amp_enabled=False):
    dataset = StructureBDataset(records, tokenizer)

    if train and config.oversample:
        sample_weights = []
        for record in records:
            count = item_count(record)
            sample_weights.append(2.3 if count >= 3 else 1.7 if count == 2 else 1.0)
        sampler = WeightedRandomSampler(
            sample_weights,
            num_samples=len(sample_weights),
            replacement=True,
        )
        return DataLoader(
            dataset,
            batch_size=BATCH_SIZE,
            sampler=sampler,
            num_workers=NUM_WORKERS,
            pin_memory=amp_enabled,
        )

    return DataLoader(
        dataset,
        batch_size=BATCH_SIZE,
        shuffle=train,
        num_workers=NUM_WORKERS,
        pin_memory=amp_enabled,
    )


def build_class_weights(train_records, device):
    intent_counts = Counter(str(r.get('intent') or 'UNKNOWN') for r in train_records)
    raw = []
    for label in INTENT_LABELS:
        count = intent_counts.get(label, 0)
        raw.append(0.0 if count == 0 else 1 / math.sqrt(count))
    nonzero = [x for x in raw if x > 0]
    scale = len(nonzero) / sum(nonzero) if nonzero else 1.0
    intent_weights = torch.tensor(
        [x * scale if x > 0 else 0.0 for x in raw],
        dtype=torch.float32,
        device=device,
    )

    active_targets = []
    for record in train_records:
        count = item_count(record)
        active_targets.extend([1] * count + [0] * (MAX_ITEMS - count))
    active_counts = Counter(active_targets)
    active_raw = [1 / math.sqrt(max(active_counts.get(i, 1), 1)) for i in [0, 1]]
    active_scale = 2 / sum(active_raw)
    active_weights = torch.tensor(
        [x * active_scale for x in active_raw],
        dtype=torch.float32,
        device=device,
    )
    return intent_weights, active_weights
