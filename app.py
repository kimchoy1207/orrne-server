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
     level=logging.DEBUG,
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
    logging.debug("Starting rollback request")
    logging.debug(f"Received data: {request.get_json()}")
    auth_header = request.headers.get("Authorization")
    if not auth_header or "Bearer admin-secret-token-here" not in auth_header:
        logging.error("Unauthorized access attempt")
        return jsonify({"error": "Unauthorized"}), 401

    try:
        data = request.get_json() or {}
        commit_id = data.get("commit_id")
        logging.debug(f"Requested commit_id: {commit_id}")

        # logs/commits.json 로드
        try:
            with open("logs/commits.json", "r", encoding="utf-8") as f:
                commits = json.load(f)
            logging.debug(f"Commits count: {len(commits)}")
            logging.debug(f"Available commit IDs: {[c['commit_id'] for c in commits]}")
        except FileNotFoundError:
            logging.error("Commit log file not found")
            return jsonify({"error": "Commit log file not found"}), 500

        # 롤백 대상 커밋 결정
        if commit_id:
            rollback_target = next((c for c in commits if c["commit_id"] == commit_id), None)
            if not rollback_target:
                logging.error(f"Commit ID {commit_id} not found")
                return jsonify({"error": "Commit ID not found"}), 404
        else:
            if len(commits) < 2:
                logging.error("No rollback target available")
                return jsonify({"error": "No rollback target available"}), 400
            rollback_target = commits[-2]

        commit_id = rollback_target["commit_id"]
        logging.debug(f"Selected rollback commit_id: {commit_id}")

        # Git에서 index.html 내용 복원
        try:
            restored_html = subprocess.check_output(
                ["git", "show", f"{commit_id}:index.html"],
                stderr=subprocess.STDOUT
            ).decode("utf-8")
            logging.debug("Successfully restored HTML from Git")
        except subprocess.CalledProcessError as e:
            stdout = e.stdout.decode("utf-8") if isinstance(e.stdout, bytes) else e.stdout
            stderr = e.stderr.decode("utf-8") if isinstance(e.stderr, bytes) else e.stderr
            logging.error(f"Failed to restore HTML: {str(e)}")
            return jsonify({
                "status": "error",
                "message": "Failed to restore HTML from Git",
                "details": {
                    "error": str(e),
                    "stdout": stdout,
                    "stderr": stderr,
                    "exit_code": e.returncode
                }
            }), 500

        # index.html 덮어쓰기
        with open("index.html", "w") as f:
            f.write(restored_html)
        logging.debug("index.html overwritten")

        # Git 자동 커밋 + 푸시
        result = git_commit_and_push("index.html", restored_html, commit_message=f"Rollback to {commit_id}")
        logging.debug(f"git_commit_and_push result: {result}")

        if result.get("success"):
            log_commit(
                f"[Rollback] to {commit_id}",
                result["commit_id"],
                restored_html[:10000],
                extra_info={"rollback_from": commit_id}
            )
            logging.info(f"Rollback successful to {commit_id}")
            return jsonify({
                "status": "success",
                "rolled_back_to": commit_id,
                "new_commit_id": result["commit_id"]
            })
        elif result.get("skipped"):
            logging.info("No changes to rollback")
            return jsonify({"status": "skipped", "message": "No changes to rollback"})
        else:
            logging.error(f"Git operation failed: {result}")
            return jsonify({
                "status": "error",
                "message": result.get("message", "Git operation failed"),
                "details": {
                    "error": result.get("error", "No specific error provided"),
                    "stdout": result.get("stdout", "No stdout"),
                    "stderr": result.get("stderr", "No stderr"),
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
    app.run(host="0.0.0.0", port=5000)

