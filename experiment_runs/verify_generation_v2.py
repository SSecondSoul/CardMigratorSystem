"""Offline replay of frozen generation requests; never imports a model client or database."""
import argparse
from collections import defaultdict
from hashlib import sha256
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'migration_system/src'))
from card_migration_system.prompts.migration import generation_messages
from card_migration_system.prompts.generation import compact_generation_context
from card_migration_system.reporting.identity import digest
from types import SimpleNamespace
from run_experiment import encode, inside, read_json, write_once

V1 = ROOT / 'experiment_runs/real_system_experiment70_v1_20261118'
OUTPUT = ROOT / 'experiment_runs/generation_context_v2_verification_20261118'


def verify_bundle(folder):
    count = 0
    for line in (folder / 'SHA256SUMS.txt').read_text(encoding='utf-8').splitlines():
        expected, relative = line.split('  ', 1)
        path = inside(folder / relative, folder)
        if sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError('saved_sample_hash_mismatch:' + relative)
        count += 1
    return count


def duplicate_strings(value):
    """Audit exact repetitions, without substituting references in model input."""
    found = defaultdict(list)
    def visit(node, path):
        if isinstance(node, dict):
            for key, child in node.items():
                visit(child, path + '/' + str(key).replace('~', '~0').replace('/', '~1'))
        elif isinstance(node, list):
            for index, child in enumerate(node):
                visit(child, path + '/' + str(index))
        elif isinstance(node, str) and len(node) >= 120:
            found[node].append(path)
    visit(value, '')
    result = [{'sha256': sha256(text.encode()).hexdigest(), 'chars_each': len(text),
               'occurrences': len(paths), 'paths': paths}
              for text, paths in found.items() if len(paths) > 1]
    return sorted(result, key=lambda row: row['chars_each'] * (row['occurrences'] - 1), reverse=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=OUTPUT)
    args = parser.parse_args()
    output = inside(args.output, ROOT / 'experiment_runs')
    checkpoint = read_json(V1 / 'checkpoint.json')
    samples = read_json(V1 / 'samples.json')
    rows = []
    settings = SimpleNamespace(repository_root=ROOT / 'migration_system/engine')
    for sample in samples:
        if sample['id'] not in checkpoint['results']:
            continue
        folder = V1 / 'samples' / sample['slug']
        verified = verify_bundle(folder)
        request_path = folder / 'artifacts/calls/0/request.json'
        if not request_path.is_file():
            continue  # A genuine preflight failure need not have a model request.
        recorded = read_json(request_path)
        ssm = read_json(folder / 'artifacts/ssm.json')['ssm']
        spec = read_json(folder / 'artifacts/request.json')['request']
        production, _ = generation_messages(settings, ssm, spec['few_shot_examples'], strategy=spec['strategy'])
        old = recorded['messages']
        # MySQL JSON normalizes object key order in the saved spec. Reconstructing
        # a demonstration from it need not reproduce its *string* byte order.
        # Verify values, then replay the actual frozen strings unchanged.
        assert old[0] == production[0]
        assert len(old) == len(production)
        for before, after in zip(old[1:-1], production[1:-1]):
            assert before['role'] == after['role']
            assert (json.loads(before['content']) == json.loads(after['content'])
                    if before['role'] == 'user' else before['content'] == after['content'])
        new, context = compact_generation_context(old, ssm)
        old_prefix, old_body = old[-1]['content'].rsplit('--- SSM ---\n', 1)
        new_prefix, new_body = new[-1]['content'].rsplit('--- SSM ---\n', 1)
        assert old[:-1] == new[:-1], 'few-shot or system instruction changed'
        assert old_prefix == new_prefix, 'semantic generation rules changed'
        assert digest(json.loads(old_body)) == digest(json.loads(new_body)) == digest(ssm)
        assert len(new[-1]['content']) <= len(old[-1]['content'])
        response = read_json(folder / 'artifacts/calls/0/response.json')
        receipt = read_json(folder / 'artifacts/calls/0/receipt.json')
        row = {'sample_id': sample['id'], 'verified_files': verified,
               'v1_input_tokens': (response.get('usage') or {}).get('prompt_tokens'),
               'v1_output_tokens': (response.get('usage') or {}).get('completion_tokens'),
               'v1_finish_reason': response.get('choices', [{}])[0].get('finish_reason'),
               **context}
        row['character_reduction_ratio'] = 1 - row['after_chars'] / row['before_chars']
        rows.append(row)
        if receipt.get('error') == 'model_output_incomplete':
            write_once(output / sample['id'] / 'messages.json', encode(new))
            write_once(output / sample['id'] / 'context.json', encode(context))
            write_once(output / sample['id'] / 'duplicates-audit.json', encode(duplicate_strings(ssm)))
    report = {'protocol': 'generation-lossless-json-v2', 'verified_requests': len(rows),
              'model_calls_triggered': 0, 'database_writes': 0,
              'v1_summary_sha256': sha256((V1 / 'summary.json').read_bytes()).hexdigest(),
              'quality_pass_claim': False, 'new_output_ceiling': 32768,
              'token_counts_after': 'not_measured_no_paid_call', 'samples': rows}
    write_once(output / 'report.json', encode(report))
    print(json.dumps({'verified_requests': len(rows), 'model_calls_triggered': 0,
                      'report': str(output / 'report.json')}, ensure_ascii=True))


if __name__ == '__main__':
    main()
