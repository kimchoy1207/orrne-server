import os
import json
from datetime import datetime

def log_commit(prompt, commit_id, html_excerpt, extra_info=None):
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "commits.json")

    log_data = {
        "timestamp": datetime.utcnow().isoformat(),
        "prompt": prompt,
        "commit_id": commit_id,
        "preview": html_excerpt[:300]  # 일부만 기록
    }

    if extra_info:
        log_data["extra_info"] = extra_info

    if os.path.exists(log_file):
        with open(log_file, "r", encoding="utf-8") as f:
            logs = json.load(f)
    else:
        logs = []

    logs.append(log_data)

    with open(log_file, "w", encoding="utf-8") as f:
        json.dump(logs, f, indent=2, ensure_ascii=False)

