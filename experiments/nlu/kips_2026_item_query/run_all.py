import argparse
import json
import shutil
from collections import Counter
from dataclasses import asdict
from pathlib import Path

import pandas as pd
import torch
from transformers import AutoTokenizer

from .config import (
    ABLATION_CONFIGS,
    ABLATION_SEEDS,
    MAIN_CONFIGS,
    MAIN_SEEDS,
    MODEL_NAME,
    RDROP_CONFIG,
)
from .data_utils import item_count, load_jsonl, split_train_valid
from .train_eval import make_paper_table, run_suite, summarize


def project_root():
    return Path(__file__).resolve().parents[3]


def canonical_paths():
    root = project_root()
    return (
        root / 'data' / 'structure_b_train_valid.jsonl',
        root / 'data' / 'structure_b_test.jsonl',
    )


def upload_colab_data():
    try:
        from google.colab import files
    except ImportError as exc:
        raise RuntimeError('--upload is only available in Google Colab') from exc

    print('structure_b_train_valid.jsonl, structure_b_test.jsonl 두 파일을 선택하세요.')
    files.upload()
    train_valid = Path('/content/structure_b_train_valid.jsonl')
    test = Path('/content/structure_b_test.jsonl')
    missing = [str(p) for p in (train_valid, test) if not p.exists()]
    if missing:
        raise FileNotFoundError(f'업로드 파일 확인 필요: {missing}')
    return train_valid, test


def prepare_data(train_valid_path, test_path):
    pool = load_jsonl(Path(train_valid_path))
    test_records = load_jsonl(Path(test_path))

    if len(pool) != 22512:
        raise ValueError(
            f'canonical train/valid pool은 22,512개여야 합니다: {len(pool)}'
        )
    if len(test_records) != 1507:
        raise ValueError(
            f'canonical test는 1,507개여야 합니다: {len(test_records)}'
        )

    train_records, valid_records = split_train_valid(pool)
    print({
        'train': len(train_records),
        'valid': len(valid_records),
        'test': len(test_records),
    })
    print(
        'train intent:',
        Counter(str(r.get('intent') or 'UNKNOWN') for r in train_records),
    )
    print(
        'valid item count:',
        Counter(
            item_count(r)
            for r in valid_records
            if str(r.get('intent')) == 'ORDER'
        ),
    )
    print(
        'test item count:',
        Counter(
            item_count(r)
            for r in test_records
            if str(r.get('intent')) == 'ORDER'
        ),
    )
    return pool, train_records, valid_records, test_records


def save_manifest(
    result_root,
    train_valid_path,
    test_path,
    pool,
    train_records,
    valid_records,
    test_records,
):
    manifest = {
        'model': MODEL_NAME,
        'train_valid_file': Path(train_valid_path).name,
        'test_file': Path(test_path).name,
        'train_pool_size': len(pool),
        'train_size': len(train_records),
        'valid_size': len(valid_records),
        'test_size': len(test_records),
        'main_seeds': MAIN_SEEDS,
        'ablation_seeds_default': ABLATION_SEEDS,
        'main_configs': [asdict(x) for x in MAIN_CONFIGS],
        'ablation_configs': [asdict(x) for x in ABLATION_CONFIGS],
        'rdrop_config': asdict(RDROP_CONFIG),
    }
    with (result_root / 'experiment_manifest.json').open(
        'w',
        encoding='utf-8',
    ) as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)


def run_main(
    train_records,
    valid_records,
    test_records,
    tokenizer,
    result_root,
):
    runs = run_suite(
        MAIN_CONFIGS,
        MAIN_SEEDS,
        train_records,
        valid_records,
        test_records,
        tokenizer,
        result_root,
    )
    runs.to_csv(result_root / 'main_runs.csv', index=False)
    summary = summarize(runs)
    summary.to_csv(result_root / 'main_summary.csv', index=False)
    paper_table = make_paper_table(summary)
    paper_table.to_csv(result_root / 'paper_main_table.csv', index=False)
    print('\n=== Main paper table ===')
    print(paper_table.to_string(index=False))
    return runs, summary, paper_table


def run_ablation(
    train_records,
    valid_records,
    test_records,
    tokenizer,
    result_root,
    seeds=None,
    include_rdrop=False,
):
    seeds = list(seeds or ABLATION_SEEDS)
    configs = list(ABLATION_CONFIGS)
    if include_rdrop:
        configs.append(RDROP_CONFIG)

    runs = run_suite(
        configs,
        seeds,
        train_records,
        valid_records,
        test_records,
        tokenizer,
        result_root,
    )
    runs.to_csv(result_root / 'ablation_runs.csv', index=False)
    summary = summarize(runs)
    summary.to_csv(result_root / 'ablation_summary.csv', index=False)

    columns = [
        'experiment',
        'n_seeds',
        'multi_item_em_mean',
        'multi_item_em_std',
        'order_exact_match_mean',
        'order_exact_match_std',
    ]
    print('\n=== Ablation summary ===')
    print(summary[columns].to_string(index=False))
    return runs, summary


def zip_results(result_root):
    output = result_root.parent / f'{result_root.name}.zip'
    if output.exists():
        output.unlink()
    shutil.make_archive(
        str(output.with_suffix('')),
        'zip',
        result_root,
    )
    print('result zip:', output)
    return output


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--mode',
        choices=['main', 'ablation', 'all'],
        default='main',
    )
    parser.add_argument('--upload', action='store_true')
    parser.add_argument('--rdrop', action='store_true')
    parser.add_argument(
        '--ablation-seeds',
        default='42',
        help='comma-separated, e.g. 42 or 42,43,44',
    )
    parser.add_argument('--result-dir', default='kips_2026_results')
    args = parser.parse_args()

    if args.upload:
        train_valid_path, test_path = upload_colab_data()
    else:
        train_valid_path, test_path = canonical_paths()

    result_root = Path(args.result_dir).resolve()
    result_root.mkdir(parents=True, exist_ok=True)

    pool, train_records, valid_records, test_records = prepare_data(
        train_valid_path,
        test_path,
    )

    print('device:', 'cuda' if torch.cuda.is_available() else 'cpu')
    if torch.cuda.is_available():
        print('GPU:', torch.cuda.get_device_name(0))

    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    tokenizer.save_pretrained(result_root / 'tokenizer')
    save_manifest(
        result_root,
        train_valid_path,
        test_path,
        pool,
        train_records,
        valid_records,
        test_records,
    )

    if args.mode in {'main', 'all'}:
        run_main(
            train_records,
            valid_records,
            test_records,
            tokenizer,
            result_root,
        )

    if args.mode in {'ablation', 'all'}:
        seeds = [
            int(x.strip())
            for x in args.ablation_seeds.split(',')
            if x.strip()
        ]
        run_ablation(
            train_records,
            valid_records,
            test_records,
            tokenizer,
            result_root,
            seeds=seeds,
            include_rdrop=args.rdrop,
        )

    zip_results(result_root)


if __name__ == '__main__':
    main()
