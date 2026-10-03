import gc
import json
import math
import os
import random
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.metrics import accuracy_score, f1_score
from tqdm.auto import tqdm
from transformers import get_linear_schedule_with_warmup

from .config import (
    BASE_LR,
    EPOCHS,
    GRAD_CLIP_NORM,
    HEAD_LR,
    INTENT_LABELS,
    MAX_ITEMS,
    MENU_LABELS,
    MODEL_NAME,
    PATIENCE,
    QUANTITY_LABELS,
    RDROP_ALPHA,
    STATUS_LABELS,
    TEMPERATURE_LABELS,
    WARMUP_RATIO,
    WEIGHT_DECAY,
)
from .data_utils import (
    build_class_weights,
    build_loader,
    id2intent,
    id2menu,
    id2qty,
    id2status,
    id2temp,
    intent2id,
)
from .models import build_model


def set_seed(seed):
    random.seed(seed)
    np.random.seed(seed)
    os.environ['PYTHONHASHSEED'] = str(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


def build_optimizer(model, config):
    if config.differential_lr:
        encoder_ids = {id(p) for p in model.encoder.parameters()}
        non_encoder = [p for p in model.parameters() if id(p) not in encoder_ids]
        return torch.optim.AdamW(
            [
                {'params': model.encoder.parameters(), 'lr': BASE_LR},
                {'params': non_encoder, 'lr': HEAD_LR},
            ],
            weight_decay=WEIGHT_DECAY,
        )

    return torch.optim.AdamW(
        model.parameters(),
        lr=BASE_LR,
        weight_decay=WEIGHT_DECAY,
    )


def compute_task_loss(outputs, batch, intent_weights=None, active_weights=None):
    intent_ce = nn.CrossEntropyLoss(weight=intent_weights)
    active_ce = nn.CrossEntropyLoss(weight=active_weights)
    ce = nn.CrossEntropyLoss()

    intent_loss = intent_ce(outputs['intent_logits'], batch['intent_label'])
    status_loss = ce(outputs['status_logits'], batch['status_label'])
    active_loss = active_ce(
        outputs['active_logits'].reshape(-1, 2),
        batch['item_active'].reshape(-1),
    )

    active_mask = batch['item_active'].reshape(-1).bool()
    zero = intent_loss.new_tensor(0.0)

    if active_mask.any():
        menu_loss = ce(
            outputs['menu_logits'].reshape(-1, len(MENU_LABELS))[active_mask],
            batch['menu_labels'].reshape(-1)[active_mask],
        )
        temperature_loss = ce(
            outputs['temperature_logits'].reshape(-1, len(TEMPERATURE_LABELS))[active_mask],
            batch['temperature_labels'].reshape(-1)[active_mask],
        )
        quantity_loss = ce(
            outputs['quantity_logits'].reshape(-1, len(QUANTITY_LABELS))[active_mask],
            batch['quantity_labels'].reshape(-1)[active_mask],
        )
    else:
        menu_loss = zero
        temperature_loss = zero
        quantity_loss = zero

    return (
        intent_loss
        + status_loss
        + active_loss
        + 1.3 * menu_loss
        + temperature_loss
        + quantity_loss
    )


def symmetric_kl(logits_a, logits_b):
    log_a = torch.log_softmax(logits_a, dim=-1)
    log_b = torch.log_softmax(logits_b, dim=-1)
    prob_a = torch.softmax(logits_a, dim=-1)
    prob_b = torch.softmax(logits_b, dim=-1)
    return 0.5 * (
        nn.functional.kl_div(log_a, prob_b, reduction='batchmean')
        + nn.functional.kl_div(log_b, prob_a, reduction='batchmean')
    )


def rdrop_kl(outputs_a, outputs_b):
    total = 0.0
    keys = [
        'intent_logits',
        'status_logits',
        'active_logits',
        'menu_logits',
        'temperature_logits',
        'quantity_logits',
    ]
    for key in keys:
        a = outputs_a[key].reshape(-1, outputs_a[key].shape[-1])
        b = outputs_b[key].reshape(-1, outputs_b[key].shape[-1])
        total = total + symmetric_kl(a, b)
    return total / len(keys)


def to_device(batch, device):
    return {
        key: value.to(device, non_blocking=True) if torch.is_tensor(value) else value
        for key, value in batch.items()
    }


def evaluate(model, loader, device, collect_predictions=False):
    model.eval()
    true_intent, pred_intent = [], []
    true_status, pred_status = [], []
    true_active, pred_active = [], []
    true_menu, pred_menu = [], []
    true_temp, pred_temp = [], []
    true_qty, pred_qty = [], []
    order_matches, order_counts = [], []
    frame_matches = []
    rows = []

    with torch.inference_mode():
        for batch in loader:
            texts = batch['text']
            batch = to_device(batch, device)
            outputs = model(batch['input_ids'], batch['attention_mask'])

            pi = outputs['intent_logits'].argmax(-1)
            ps = outputs['status_logits'].argmax(-1)
            pa = outputs['active_logits'].argmax(-1)
            pm = outputs['menu_logits'].argmax(-1)
            pt = outputs['temperature_logits'].argmax(-1)
            pq = outputs['quantity_logits'].argmax(-1)

            yi = batch['intent_label']
            ys = batch['status_label']
            ya = batch['item_active']
            ym = batch['menu_labels']
            yt = batch['temperature_labels']
            yq = batch['quantity_labels']

            true_intent.extend(yi.cpu().tolist())
            pred_intent.extend(pi.cpu().tolist())
            true_status.extend(ys.cpu().tolist())
            pred_status.extend(ps.cpu().tolist())
            true_active.extend(ya.reshape(-1).cpu().tolist())
            pred_active.extend(pa.reshape(-1).cpu().tolist())

            active_mask = ya.bool()
            true_menu.extend(ym[active_mask].cpu().tolist())
            pred_menu.extend(pm[active_mask].cpu().tolist())
            true_temp.extend(yt[active_mask].cpu().tolist())
            pred_temp.extend(pt[active_mask].cpu().tolist())
            true_qty.extend(yq[active_mask].cpu().tolist())
            pred_qty.extend(pq[active_mask].cpu().tolist())

            for index in range(yi.size(0)):
                item_ok = bool(torch.equal(ya[index], pa[index]))
                for item_index in range(MAX_ITEMS):
                    if int(ya[index, item_index]) == 1:
                        item_ok = (
                            item_ok
                            and int(ym[index, item_index]) == int(pm[index, item_index])
                            and int(yt[index, item_index]) == int(pt[index, item_index])
                            and int(yq[index, item_index]) == int(pq[index, item_index])
                        )

                frame_ok = (
                    int(yi[index]) == int(pi[index])
                    and int(ys[index]) == int(ps[index])
                    and item_ok
                )
                frame_matches.append(frame_ok)

                is_order = int(yi[index]) == intent2id['ORDER']
                order_exact_match = None
                count = 0
                if is_order:
                    count = int(ya[index].sum().item())
                    order_exact_match = (
                        int(pi[index]) == intent2id['ORDER']
                        and item_ok
                    )
                    order_matches.append(bool(order_exact_match))
                    order_counts.append(count)

                if collect_predictions:
                    rows.append({
                        'text': texts[index],
                        'true_intent': id2intent[int(yi[index])],
                        'pred_intent': id2intent[int(pi[index])],
                        'true_status': id2status[int(ys[index])],
                        'pred_status': id2status[int(ps[index])],
                        'item_count': count,
                        'order_exact_match': order_exact_match,
                        'frame_correct': frame_ok,
                        'true_menu': [id2menu[int(x)] for x in ym[index].cpu().tolist()],
                        'pred_menu': [id2menu[int(x)] for x in pm[index].cpu().tolist()],
                        'true_temperature': [id2temp[int(x)] for x in yt[index].cpu().tolist()],
                        'pred_temperature': [id2temp[int(x)] for x in pt[index].cpu().tolist()],
                        'true_quantity': [id2qty[int(x)] for x in yq[index].cpu().tolist()],
                        'pred_quantity': [id2qty[int(x)] for x in pq[index].cpu().tolist()],
                    })

    def accuracy(y_true, y_pred):
        return float(accuracy_score(y_true, y_pred)) if y_true else float('nan')

    def subset_em(valid_counts):
        values = [
            match
            for match, count in zip(order_matches, order_counts)
            if count in valid_counts
        ]
        return float(np.mean(values)) if values else float('nan')

    metrics = {
        'intent_accuracy': accuracy(true_intent, pred_intent),
        'intent_macro_f1': float(f1_score(
            true_intent,
            pred_intent,
            average='macro',
            zero_division=0,
        )),
        'status_accuracy': accuracy(true_status, pred_status),
        'status_macro_f1': float(f1_score(
            true_status,
            pred_status,
            average='macro',
            zero_division=0,
        )),
        'item_active_accuracy': accuracy(true_active, pred_active),
        'menu_accuracy': accuracy(true_menu, pred_menu),
        'temperature_accuracy': accuracy(true_temp, pred_temp),
        'quantity_accuracy': accuracy(true_qty, pred_qty),
        'frame_accuracy': float(np.mean(frame_matches)),
        'order_exact_match': float(np.mean(order_matches)) if order_matches else float('nan'),
        'single_item_em': subset_em({1}),
        'two_item_em': subset_em({2}),
        'three_item_em': subset_em({3}),
        'multi_item_em': subset_em({2, 3}),
    }
    return metrics, pd.DataFrame(rows)


def train_and_test(
    config,
    seed,
    train_records,
    valid_records,
    test_records,
    tokenizer,
    result_root: Path,
):
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    amp_enabled = device.type == 'cuda'
    run_dir = result_root / 'runs' / f'{config.name}_seed{seed}'
    run_dir.mkdir(parents=True, exist_ok=True)
    result_path = run_dir / 'result.json'

    if result_path.exists():
        with result_path.open('r', encoding='utf-8') as f:
            return json.load(f)

    set_seed(seed)
    model = build_model(config).to(device)
    train_loader = build_loader(
        train_records,
        tokenizer,
        config,
        train=True,
        amp_enabled=amp_enabled,
    )
    valid_loader = build_loader(
        valid_records,
        tokenizer,
        config,
        train=False,
        amp_enabled=amp_enabled,
    )
    test_loader = build_loader(
        test_records,
        tokenizer,
        config,
        train=False,
        amp_enabled=amp_enabled,
    )

    intent_weights, active_weights = build_class_weights(train_records, device)
    if not config.weighted_loss:
        intent_weights = None
        active_weights = None

    optimizer = build_optimizer(model, config)
    total_steps = len(train_loader) * EPOCHS
    scheduler = get_linear_schedule_with_warmup(
        optimizer,
        num_warmup_steps=int(total_steps * WARMUP_RATIO),
        num_training_steps=total_steps,
    )
    scaler = torch.cuda.amp.GradScaler(enabled=amp_enabled)

    best_score = -1.0
    bad_epochs = 0
    history = []
    best_path = run_dir / 'best_model.pt'

    for epoch in range(1, EPOCHS + 1):
        model.train()
        losses = []

        for batch in tqdm(
            train_loader,
            desc=f'{config.name} seed={seed} epoch={epoch}',
            leave=False,
        ):
            batch = to_device(batch, device)
            optimizer.zero_grad(set_to_none=True)

            with torch.cuda.amp.autocast(enabled=amp_enabled):
                first = model(batch['input_ids'], batch['attention_mask'])
                loss = compute_task_loss(
                    first,
                    batch,
                    intent_weights,
                    active_weights,
                )

                if config.rdrop:
                    second = model(batch['input_ids'], batch['attention_mask'])
                    second_loss = compute_task_loss(
                        second,
                        batch,
                        intent_weights,
                        active_weights,
                    )
                    loss = (
                        0.5 * (loss + second_loss)
                        + RDROP_ALPHA * rdrop_kl(first, second)
                    )

            scaler.scale(loss).backward()
            scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(model.parameters(), GRAD_CLIP_NORM)
            scaler.step(optimizer)
            scaler.update()
            scheduler.step()
            losses.append(float(loss.detach().cpu()))

        valid_metrics, _ = evaluate(model, valid_loader, device)
        selection_score = valid_metrics['frame_accuracy']
        history.append({
            'epoch': epoch,
            'train_loss': float(np.mean(losses)),
            **{f'valid_{k}': v for k, v in valid_metrics.items()},
        })
        print(
            f'{config.name} seed={seed} epoch={epoch} '
            f'loss={np.mean(losses):.4f} '
            f'valid_frame={selection_score:.4f} '
            f'valid_multi={valid_metrics["multi_item_em"]:.4f}'
        )

        if selection_score > best_score + 1e-8:
            best_score = selection_score
            bad_epochs = 0
            torch.save({
                'model_state_dict': model.state_dict(),
                'config': asdict(config),
                'seed': seed,
                'model_name': MODEL_NAME,
            }, best_path)
        else:
            bad_epochs += 1
            if bad_epochs >= PATIENCE:
                break

    pd.DataFrame(history).to_csv(run_dir / 'history.csv', index=False)

    checkpoint = torch.load(best_path, map_location=device)
    model.load_state_dict(checkpoint['model_state_dict'])
    test_metrics, predictions = evaluate(
        model,
        test_loader,
        device,
        collect_predictions=True,
    )
    predictions.to_csv(run_dir / 'test_predictions.csv', index=False)
    predictions[
        predictions['frame_correct'] == False
    ].to_csv(run_dir / 'test_errors.csv', index=False)

    result = {
        'experiment': config.name,
        'seed': seed,
        **asdict(config),
        **test_metrics,
        'best_valid_frame_accuracy': best_score,
    }
    with result_path.open('w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    del model, optimizer, scheduler, scaler
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    return result


def run_suite(
    configs,
    seeds,
    train_records,
    valid_records,
    test_records,
    tokenizer,
    result_root,
):
    rows = []
    for config in configs:
        for seed in seeds:
            rows.append(train_and_test(
                config,
                seed,
                train_records,
                valid_records,
                test_records,
                tokenizer,
                result_root,
            ))
    return pd.DataFrame(rows)


def summarize(runs):
    metrics = [
        'intent_macro_f1',
        'frame_accuracy',
        'order_exact_match',
        'single_item_em',
        'two_item_em',
        'three_item_em',
        'multi_item_em',
        'menu_accuracy',
        'temperature_accuracy',
        'quantity_accuracy',
        'item_active_accuracy',
    ]
    rows = []

    for experiment, group in runs.groupby('experiment', sort=False):
        row = {'experiment': experiment, 'n_seeds': len(group)}
        for metric in metrics:
            values = pd.to_numeric(group[metric], errors='coerce')
            row[f'{metric}_mean'] = values.mean()
            row[f'{metric}_std'] = (
                values.std(ddof=1) if len(values) > 1 else 0.0
            )
        rows.append(row)
    return pd.DataFrame(rows)


def _fmt(mean, std):
    return f'{100 * mean:.2f}±{100 * std:.2f}'


def make_paper_table(summary):
    rows = []
    for _, row in summary.iterrows():
        rows.append({
            'Model': row['experiment'],
            '1-item EM': _fmt(
                row['single_item_em_mean'],
                row['single_item_em_std'],
            ),
            '2-item EM': _fmt(
                row['two_item_em_mean'],
                row['two_item_em_std'],
            ),
            '3-item EM': _fmt(
                row['three_item_em_mean'],
                row['three_item_em_std'],
            ),
            'Multi EM': _fmt(
                row['multi_item_em_mean'],
                row['multi_item_em_std'],
            ),
            'Overall Order EM': _fmt(
                row['order_exact_match_mean'],
                row['order_exact_match_std'],
            ),
            'Intent Macro F1': _fmt(
                row['intent_macro_f1_mean'],
                row['intent_macro_f1_std'],
            ),
        })
    return pd.DataFrame(rows)
