import os
import subprocess
from datetime import datetime

def git_commit_and_push(file_path, html_code, commit_message="auto: update index.html"):
    repo_dir = os.path.expanduser("~/orrne-server-clean")
    commit_time = datetime.utcnow().isoformat()
    abs_path = os.path.join(repo_dir, file_path)

    try:
        # 1.Git 저장소로 이동
        os.chdir(repo_dir)


        # 2. 최신 상태로 Pull
        pull_result = subprocess.run(
            ["git", "pull", "--rebase", "origin", "main"],
            capture_output=True,
            text=True
        )
        if pull_result.returncode != 0:
            return {
                "success": False,
                "message": "Git pull failed",
                "stdout": pull_result.stdout,
                "stderr": pull_result.stderr,
                "timestamp": commit_time
            }

        # 3. 파일 덮어쓰기
        with open(abs_path, "w") as f:
            f.write(html_code)


        # 4. 변경 사항 있는 경우 Staging Area에 추가
        subprocess.run(["git", "add", file_path], check=True, capture_output=True, text=True)

        # 5. 변경 사항 확인
        diff_result = subprocess.run(
            ["git", "diff", "--cached", "--quiet", file_path],
            capture_output=True,
            text=True
        )
        if diff_result.returncode == 0:
            return {
                "success": False,
                "skipped": True,
                "message": "No changes detected in index.html",
                "timestamp": commit_time
            }

        # 6. 커밋
        subprocess.run(["git", "commit", "-m", commit_message], check=True, capture_output=True, text=True)

        # 7. Push
        push_result = subprocess.run(
            ["git", "push", "origin", "main"],
            capture_output=True,
            text=True
        )

        # 8. "Everything up-to-date"도 정상 처리
        if "Everything up-to-date" in (push_result.stdout or ""):
            return {
                "success": True,
                "message": "변경 사항 없어서 push 생략됨 (Everything up-to-date)",
                "timestamp": commit_time
            }

        # 9. Push 실패 시 에러 처리
        if push_result.returncode != 0:
            return {
                "success": False,
                "message": "Git push failed",
                "stdout": push_result.stdout or "No stdout",
                "stderr": push_result.stderr or "No stderr",
                "details": f"exit code {push_result.returncode}",
                "timestamp": commit_time
            }

        # 10. Commit ID 추출
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True
        )
        commit_hash = result.stdout.strip()

        # 11. 프리뷰 저장
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
        #  예외 발생 시 stdout/stderr 수집
        stdout = e.stdout if isinstance(e.stdout, str) else e.stdout.decode("utf-8") if e.stdout else ""
        stderr = e.stderr if isinstance(e.stderr, str) else e.stderr.decode("utf-8") if e.stderr else ""

        return {
            "success": False,
            "error": str(e),
            "stdout": stdout,
            "stderr": stderr,
            "message": "HTML generated but Git push failed",
            "timestamp": commit_time
        }
    except Exception as e:
        # 기타 예외 처리
        return {
            "success": False,
            "error": str(e),
            "message": "HTML generated but Git push failed",
            "details": "Unexpected error occurred",
            "timestamp": commit_time
            }
