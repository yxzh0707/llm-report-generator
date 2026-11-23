"""BGE-M3 adapter with a local content-addressed vector cache."""
import hashlib
import json
import math
import os
from pathlib import Path
import urllib.request
from runtime_config import load_env_file


class CachedEmbeddings:
    model = 'BAAI/bge-m3'
    endpoint = 'https://api.siliconflow.cn/v1/embeddings'

    def __init__(self, cache_path, *, max_calls=20, max_input_chars=550000):
        if os.getenv('DISSERTATION_EMBEDDING_ENV_FILE'):
            load_env_file(os.environ['DISSERTATION_EMBEDDING_ENV_FILE'])
        self.key = os.environ.get('SILICONFLOW_API_KEY')
        if not self.key:
            raise ValueError('SILICONFLOW_API_KEY is not configured')
        self.path = Path(cache_path)
        self.cache = json.loads(self.path.read_text()) if self.path.exists() else {}
        self.calls = 0
        self.input_chars = 0
        self.max_calls = max_calls
        self.max_input_chars = max_input_chars
        self.usage = []

    def embed(self, texts):
        keys = [hashlib.sha256((self.endpoint + self.model + t).encode()).hexdigest() for t in texts]
        missing = dict((k, t) for k, t in zip(keys, texts) if k not in self.cache)
        items = list(missing.items())
        for start in range(0, len(items), 32):
            batch = items[start:start+32]
            chars = sum(len(t) for _, t in batch)
            if self.calls >= self.max_calls or self.input_chars + chars > self.max_input_chars:
                raise RuntimeError('Embedding development budget exhausted')
            req = urllib.request.Request(self.endpoint, data=json.dumps({
                'model': self.model, 'input': [t for _, t in batch]}).encode(),
                headers={'Authorization': 'Bearer ' + self.key, 'Content-Type': 'application/json'})
            self.calls += 1
            self.input_chars += chars
            with urllib.request.urlopen(req, timeout=60) as response:
                payload = json.load(response)
                data = sorted(payload['data'], key=lambda x: x['index'])
                self.usage.append(payload.get('usage'))
            if [d['index'] for d in data] != list(range(len(batch))):
                raise ValueError('Embedding response count/index mismatch')
            for (key, _), row in zip(batch, data):
                v = row['embedding']
                if len(v) != 1024 or not all(math.isfinite(x) for x in v) or not any(v):
                    raise ValueError('Invalid embedding vector')
                self.cache[key] = v
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temp = self.path.with_suffix('.tmp')
            temp.write_text(json.dumps(self.cache))
            temp.replace(self.path)
        return [self.cache[k] for k in keys]
