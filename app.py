from flask import Flask, request, jsonify, send_file
from openai import OpenAI
import os
from dotenv import load_dotenv
from generate.git_handler import git_commit_and_push
from generate.logger import log_commit
import json

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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

