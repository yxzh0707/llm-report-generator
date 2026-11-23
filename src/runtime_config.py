"""Load the local runtime convention without copying credentials into the repo."""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlsplit

KNOWN_KEYS = (
    "ROLLOUT_BASE_URL", "TOKENHUB_API_KEY", "SERPER_API_KEY", "SEC_USER_AGENT",
    "ALPHA_VANTAGE_API_KEY", "TUSHARE_TOKEN", "JUDGE_BASE_URL", "JUDGE_API_KEY",
    "VLLM_API_KEY", "DISSERTATION_MODEL", "SILICONFLOW_API_KEY",
    "TUSHARE_API_KEY", "ALPHAVANTAGE_API_KEY", "ALPHAVANTAGE_API_LEY",
    "DISSERTATION_PROVIDER", "DISSERTATION_API_KEY", "DISSERTATION_CREDENTIALS_FILE",
    "DISSERTATION_CREDENTIALS_KEY", "DISSERTATION_TOOL_ENV_FILE",
    "DISSERTATION_EMBEDDING_ENV_FILE", "DISSERTATION_THINKING",
    "JUDGE_PROVIDER", "JUDGE_MODEL", "JUDGE_THINKING", "JUDGE_CREDENTIALS_FILE", "JUDGE_CREDENTIALS_KEY",
)
TOOL_KEYS = frozenset({"SERPER_API_KEY", "SEC_USER_AGENT", "ALPHA_VANTAGE_API_KEY",
    "TUSHARE_TOKEN", "TUSHARE_API_KEY", "ALPHAVANTAGE_API_KEY", "ALPHAVANTAGE_API_LEY"})


def load_env_file(path: str | Path, *, allowed_keys=None) -> Path:
    """Load simple KEY=VALUE lines; existing process variables win."""
    env_path = Path(path).expanduser().resolve()
    if not env_path.is_file():
        raise FileNotFoundError(env_path)
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip()
        if key not in (KNOWN_KEYS if allowed_keys is None else allowed_keys) or key in os.environ:
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ[key] = value
    return env_path


def load_project_environment(*, role: str = 'generator') -> Path | None:
    """Use an explicit env file, then the local project convention if present."""
    candidate = os.getenv("DISSERTATION_ENV_FILE") or Path(__file__).resolve().parents[1] / ".env.local"
    path = Path(candidate).expanduser()
    if not path.is_file():
        return None
    load_env_file(path)
    tool_env = os.getenv("DISSERTATION_TOOL_ENV_FILE")
    if tool_env:
        load_env_file(tool_env, allowed_keys=TOOL_KEYS)
    if role not in {'generator', 'judge'}:
        raise ValueError('Unknown model role')
    prefix = 'JUDGE' if role == 'judge' else 'DISSERTATION'
    target_key = prefix + '_API_KEY'
    credential_file = os.getenv(prefix + '_CREDENTIALS_FILE')
    if credential_file and not os.getenv(target_key):
        selected = os.getenv(prefix + '_CREDENTIALS_KEY', "TOKENHUB_API_KEY")
        credential_path = Path(credential_file).expanduser()
        if not credential_path.is_absolute():
            credential_path = path.resolve().parent / credential_path
        for raw in credential_path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if line.startswith('#') or '=' not in line:
                continue
            key, value = line.split('=', 1)
            if key.strip() != selected:
                continue
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
                value = value[1:-1]
            if value:
                os.environ[target_key] = value
            break
        if not os.getenv(target_key):
            raise ValueError('Configured credential field is missing or empty')
    return path


def provider_settings(*, enable_thinking: bool | None = None, role: str = 'generator', model: str | None = None) -> dict:
    """Non-secret provider configuration shared by runtime and simple chat calls."""
    if role not in {'generator', 'judge'}:
        raise ValueError('Unknown model role')
    prefix = 'JUDGE' if role == 'judge' else 'DISSERTATION'
    kind = os.getenv(prefix + '_PROVIDER', 'tokenhub_openai' if role == 'judge' else 'vllm')
    if kind not in {'vllm', 'openai', 'tokenhub_openai'}:
        raise ValueError('Unsupported dissertation provider')
    model = model or os.getenv(prefix + '_MODEL', '' if role == 'judge' else 'Qwen3.8-27B')
    if not model:
        raise ValueError('Configure the model explicitly for this role')
    base = os.getenv('JUDGE_BASE_URL' if role == 'judge' else 'ROLLOUT_BASE_URL', '').rstrip('/').removesuffix('/chat/completions')
    parsed = urlsplit(base)
    if parsed.scheme not in {'http', 'https'} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError('Configure an HTTP(S) provider base URL without credentials or query')
    if enable_thinking is None:
        flag = os.getenv(prefix + '_THINKING', 'false').lower()
        if flag not in {'true', 'false'}:
            raise ValueError('DISSERTATION_THINKING must be true or false')
        enable_thinking = flag == 'true'
    if role == 'judge':
        key_env = 'JUDGE_API_KEY'
    elif kind == 'tokenhub_openai':
        key_env = 'DISSERTATION_API_KEY' if os.getenv('DISSERTATION_API_KEY') else 'TOKENHUB_API_KEY'
    else:
        key_env = ('DISSERTATION_API_KEY' if os.getenv('DISSERTATION_API_KEY') else
                   'VLLM_API_KEY' if os.getenv('VLLM_API_KEY') else 'TOKENHUB_API_KEY')
    if 'deepseek' in model.lower() or 'deespeek' in model.lower():
        # Gateway accepts DeepSeek's switch and forwards Bailian's equivalent.
        # https://api-docs.deepseek.com/guides/thinking_mode/
        # https://www.alibabacloud.com/help/en/model-studio/deepseek-api
        extra = {'thinking': {'type': 'enabled' if enable_thinking else 'disabled'}}
        if model.startswith('bailian/'):
            extra['enable_thinking'] = enable_thinking
    elif kind == 'vllm':
        extra = {'chat_template_kwargs': {'enable_thinking': enable_thinking}}
    else:
        extra = {}
    return {'kind': kind, 'model': model, 'base_url': base,
            'api_key_env': key_env, 'extra_body': extra}


def availability() -> dict[str, bool]:
    return {key: bool(os.getenv(key)) for key in KNOWN_KEYS}


if __name__ == "__main__":
    loaded = load_project_environment()
    print({"env_file_loaded": str(loaded) if loaded else None, "available": availability()})
