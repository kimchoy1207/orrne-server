from flask import Flask, request, jsonify, send_file
from openai import OpenAI
import os
from dotenv import load_dotenv
from generate.git_handler import git_commit_and_push
from generate.logger import log_commit
import json
import subprocess
import logging

logging.basicConfig(
     level=logging.INFO,
     format='%(asctime)s %(levelname)s: %(message)s',
     handlers=[
         logging.FileHandler('flask.log'),
         logging.StreamHandler()
     ]
)


load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

app = Flask(__name__)

@app.route("/generate", methods=["POST"])
def generate():
    try:
        data = request.get_json()
        prompt = data.get("prompt", "")

        if not prompt:
            return jsonify({"error": "Prompt is required"}), 400

        # OpenAI 요청
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )

        html_code = response.choices[0].message.content.strip()

        if "<html" not in html_code.lower():
            return jsonify({"error": "OpenAI 응답이 HTML 형식이 아닙니다."}), 400

        file_path = "index.html"

        # git 커밋 + 푸시
        git_result = git_commit_and_push(file_path, html_code)

        if git_result.get("success"):
            log_commit(prompt, git_result["commit_id"], html_code[:10000])
            return jsonify({
                "status": "success",
                "message": "HTML generated and pushed to GitHub",
                "commit_id": git_result["commit_id"],
                "timestamp": git_result["timestamp"]
            })

        else:
            return jsonify({
                "status": "error",
                "message": "HTML generated but Git push failed",
                "error": git_result.get("error", "")
            }), 500

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/preview/<commit_id>", methods=["GET"])
def preview(commit_id):
    preview_file = os.path.join("static", "preview", f"{commit_id}.html")
    if not os.path.exists(preview_file):
        return jsonify({"error": "Preview file not found"}), 404
    return send_file(preview_file)

@app.route("/admin/logs", methods=["GET"])
def admin_logs():
    try:
        log_file = os.path.join("logs", "commits.json")
        if not os.path.exists(log_file):
            return jsonify({"logs": []})
        with open(log_file, "r", encoding="utf-8") as f:
            logs = json.load(f)
        return jsonify(logs=logs)
    except Exception as e:
        return jsonify({"error": str(e)}), 500




@app.route("/admin/rollback", methods=["POST"])
def rollback():
    try:
        # 1. Git 작업 디렉토리로 강제 이동
        repo_dir = os.path.expanduser("~/orrne-server-clean")
        os.chdir(repo_dir)
        logging.debug(f"[rollback] Changed working directory to: {repo_dir}")

        # 2. 인증 검사
        auth_header = request.headers.get("Authorization")
        if not auth_header or "Bearer admin-secret-token-here" not in auth_header:
            return jsonify({"error": "Unauthorized"}), 401

        # 3. 요청 데이터 및 rollback 대상 커밋 확인
        data = request.get_json() or {}
        requested_commit_id = data.get("commit_id")

        # 4. 커밋 로그 불러오기
        with open("logs/commits.json", "r", encoding="utf-8") as f:
            commits = json.load(f)

        if requested_commit_id:
            rollback_target = next((c for c in commits if c["commit_id"] == requested_commit_id), None)
            if not rollback_target:
                return jsonify({"error": "Commit ID not found"}), 404
        else:
            if len(commits) < 2:
                return jsonify({"error": "No rollback target available"}), 400
            rollback_target = commits[-2]

        commit_id = rollback_target["commit_id"]
        logging.info(f"[rollback] Targeting commit: {commit_id}")

        # 5. 작업 상태 stash → reset 으로 안전하게 롤백 전 상태 초기화
        subprocess.run(["git", "stash", "--include-untracked"], check=False, capture_output=True, text=True)
        subprocess.run(["git", "fetch", "origin"], check=True)
        subprocess.run(["git", "reset", "--hard", "origin/main"], check=True)

        # 6. Git에서 index.html 내용 추출
        restored_html = subprocess.check_output(
            ["git", "show", f"{commit_id}:index.html"],
            stderr=subprocess.STDOUT
        ).decode("utf-8")

        # 7. index.html 덮어쓰기
        with open("index.html", "w", encoding="utf-8") as f:
            f.write(restored_html)

        # 8. 자동 커밋 & 푸시
        result = git_commit_and_push("index.html", restored_html, commit_message=f"Rollback to {commit_id}")

        # 9. 결과 처리
        if result.get("success"):
            log_commit(
                f"[Rollback] to {commit_id}",
                result["commit_id"],
                restored_html[:10000],
                extra_info={"rollback_from": commit_id}
            )
            return jsonify({
                "status": "success",
                "rolled_back_to": commit_id,
                "new_commit_id": result["commit_id"]
            })

        elif result.get("skipped"):
            return jsonify({"status": "skipped", "message": "No changes to rollback"})

        else:
            return jsonify({
                "status": "error",
                "message": result.get("message", "Git operation failed"),
                "details": {
                    "error": result.get("error", "No specific error provided"),
                    "stdout": result.get("stdout", ""),
                    "stderr": result.get("stderr", ""),
                    "exit_code": result.get("details", "No exit code")
                }
            }), 500

    except subprocess.CalledProcessError as e:
        stdout = e.stdout.decode("utf-8") if isinstance(e.stdout, bytes) else e.stdout
        stderr = e.stderr.decode("utf-8") if isinstance(e.stderr, bytes) else e.stderr
        logging.error(f"Git command failed: {str(e)}")
        return jsonify({
            "status": "error",
            "message": "Git command failed",
            "details": {
                "error": str(e),
                "stdout": stdout,
                "stderr": stderr,
                "exit_code": e.returncode
            }
        }), 500
    except Exception as e:
        logging.error(f"Internal server error: {str(e)}")
        return jsonify({
            "status": "error",
            "message": "Internal server error",
            "details": str(e)
        }), 500



if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)

