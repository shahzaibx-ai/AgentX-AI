import os
import sys
from pathlib import Path

import pytest

# Tests import the agent modules (voice_agent, app_llm, settings) from the project root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# voice_agent.py loads agent/.env into the environment on import. Settings read the
# environment even with _env_file=None, so clear the agent's own settings for each
# test: the suite must pass whatever a developer puts in their .env.
_AGENT_ENV_PREFIXES = ("VOICE_", "API_URL", "API_TIMEOUT")


@pytest.fixture(autouse=True)
def _isolated_env(monkeypatch):
    for key in list(os.environ):
        if key.startswith(_AGENT_ENV_PREFIXES):
            monkeypatch.delenv(key)
