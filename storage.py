import json
from pathlib import Path
from typing import Dict, Any

DATA_FILE = Path("data.json")

# group_id -> { "source_channel": int, "last_msg": int }
GROUP_CONFIG: Dict[int, Dict[str, Any]] = {}

# group_id -> { "topic_name": thread_id }
TOPIC_MAP: Dict[int, Dict[str, int]] = {}

# group_id -> set(user_ids)
GROUP_AUTH: Dict[int, set[int]] = {}


def load_data():
    if not DATA_FILE.exists():
        return
    data = json.loads(DATA_FILE.read_text("utf-8"))
    global GROUP_CONFIG, TOPIC_MAP, GROUP_AUTH
    GROUP_CONFIG = {int(k): v for k, v in data.get("group_config", {}).items()}
    TOPIC_MAP = {
        int(g): {t: int(i) for t, i in m.items()}
        for g, m in data.get("topic_map", {}).items()
    }
    GROUP_AUTH = {int(g): set(v) for g, v in data.get("group_auth", {}).items()}


def save_data():
    data = {
        "group_config": GROUP_CONFIG,
        "topic_map": TOPIC_MAP,
        "group_auth": {g: list(v) for g, v in GROUP_AUTH.items()},
    }
    DATA_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
