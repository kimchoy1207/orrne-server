import os
import subprocess
from datetime import datetime

def git_commit_and_push(file_path, html_code, commit_message="auto: update index.html"):
    repo_dir = os.path.expanduser("~/orrne-server-clean")
    commit_time = datetime.utcnow().isoformat()

    try:
        os.chdir(repo_dir)

        # ✅ pull 먼저 수행
        subprocess.run(["git", "pull", "--rebase", "origin", "main"], check=True)

        # ✅ 그 다음에 파일 덮어쓰기
        with open(file_path, "w") as f:
            f.write(html_code)

        # 변경 사항이 없으면 커밋 안 함
        diff_result = subprocess.run(["git", "diff", "--quiet", file_path])
        if diff_result.returncode == 0:
            return {
                "success": False,
                "skipped": True,
                "message": "No changes detected in index.html",
                "timestamp": commit_time
            }

        subprocess.run(["git", "add", file_path], check=True)
        subprocess.run(["git", "commit", "-m", commit_message], check=True)
        subprocess.run(["git", "push", "origin", "main"], check=True)

        result = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True)
        commit_hash = result.stdout.strip()

        # 프리뷰 저장
        preview_path = os.path.join("static", "preview", f"{commit_hash}.html")
        os.makedirs(os.path.dirname(preview_path), exist_ok=True)
        with open(preview_path, "w") as dst:
            dst.write(html_code)

        return {
            "success": True,
            "commit_id": commit_hash,
            "timestamp": commit_time
        }

    except subprocess.CalledProcessError as e:
        return {
            "success": False,
            "error": str(e),
            "timestamp": commit_time
        }

