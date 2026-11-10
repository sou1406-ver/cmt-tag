"""Read-only replay of the 80 selected IDs; no annotation fields are read."""
import hashlib
import json
import random
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent

def replay():
    manifest = json.loads((HERE/'random_pool_manifest.json').read_text(encoding='utf-8'))
    task = json.loads((HERE/'task.json').read_text(encoding='utf-8'))
    protocol = manifest['protocol']
    rows = manifest['rows']
    payload = json.dumps(sorted(r['id'] for r in rows)).encode()
    assert hashlib.sha256(payload).hexdigest() == protocol['pool_ids_sha256']
    assert len(rows) == protocol['pool_size']
    strata = defaultdict(list)
    for row in rows:
        strata[row['movie_id']].append(row)
    rng = random.Random(protocol['seed'])
    order = sorted(strata)
    rng.shuffle(order)
    quotas = {movie: 0 for movie in strata}
    while sum(quotas.values()) < 80:
        for movie in order:
            if sum(quotas.values()) == 80:
                break
            if quotas[movie] < len(strata[movie]):
                quotas[movie] += 1
    assert quotas == protocol['movie_quotas']
    selected = []
    for movie in sorted(strata):
        posts = defaultdict(list)
        for row in strata[movie]:
            posts[row['post_id']].append(row)
        order = sorted(posts)
        rng.shuffle(order)
        quota = {post: 0 for post in posts}
        while sum(quota.values()) < quotas[movie]:
            for post in order:
                if sum(quota.values()) == quotas[movie]:
                    break
                if quota[post] < len(posts[post]):
                    quota[post] += 1
        assert quota == protocol['post_quotas'][movie]
        for post in sorted(posts):
            selected.extend(rng.sample(sorted(posts[post],key=lambda row:row['id']),quota[post]))
    assert {r['id'] for r in selected} == {r['id'] for r in task['rows'] if r['cohort']=='random'}
    assert len(selected) == len({r['id'] for r in selected}) == 80
    return {'random_ids_reproduced':80,'seed':protocol['seed'],'sentiment_fields_read':False}

if __name__ == '__main__':
    print(json.dumps(replay()))
