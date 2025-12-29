
"""
AIPSRS - Flask Backend (Linux/Render Ready)
ASYNC Replicate Prediction + Frontend-Safe JSON + Delete Support
"""

import os
import uuid
import logging
import tempfile
import subprocess
import threading
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.utils import secure_filename

import replicate
from supabase import create_client
import imageio_ffmpeg as ffmpeg  # ✅ Cross-platform ffmpeg/ffprobe

# =========================================================
# Load .env
# =========================================================
load_dotenv()

REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN")
REPLICATE_MODEL = os.getenv("REPLICATE_MODEL")
REPLICATE_VERSION = os.getenv("REPLICATE_VERSION")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")  # Service Role Key
SUPABASE_BUCKET = "videos"

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Supabase credentials missing")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# =========================================================
# App & Logging
# =========================================================
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 200 * 1024 * 1024
CORS(app)

# =========================================================
# Utils
# =========================================================
ALLOWED_EXTENSIONS = {"mp4", "mov", "avi", "mkv"}
MAX_VIDEO_SECONDS = 15

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def get_video_duration(path):
    """Get video duration in seconds using imageio-ffmpeg (cross-platform)."""
    ffprobe_path = ffmpeg.get_ffprobe_exe()
    cmd = [
        ffprobe_path,
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        path
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return float(result.stdout.strip())

# =========================================================
# Background Prediction (ASYNC)
# =========================================================
def background_prediction(record_uuid, video_path):
    try:
        model = replicate.models.get(REPLICATE_MODEL)
        version = model.versions.get(REPLICATE_VERSION)

        with open(video_path, "rb") as vf:
            output = replicate.run(
                version,
                input={"video": vf},
                api_token=REPLICATE_API_TOKEN
            )

        text = " ".join(output) if isinstance(output, list) else str(output)

        supabase.table("predictions").update({
            "prediction": text,
            "status": "completed"
        }).eq("uuid", record_uuid).execute()

        supabase.table("user_videos").update({
            "status": "completed"
        }).eq("uuid", record_uuid).execute()

        logging.info(f"Prediction completed: {record_uuid}")

    except Exception:
        logging.exception("Async prediction failed")

        supabase.table("predictions").update({
            "status": "failed",
            "prediction": ""
        }).eq("uuid", record_uuid).execute()

        supabase.table("user_videos").update({
            "status": "failed"
        }).eq("uuid", record_uuid).execute()

    finally:
        if os.path.exists(video_path):
            os.remove(video_path)

# =========================================================
# Routes
# =========================================================
@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "time": datetime.utcnow().isoformat()
    })

@app.route("/predict", methods=["POST"])
def predict():
    user_id = request.form.get("user_id")
    if not user_id:
        return jsonify({"error": "user_id required"}), 400

    if "video" not in request.files:
        return jsonify({"error": "video required"}), 400

    file = request.files["video"]
    if not allowed_file(file.filename):
        return jsonify({"error": "invalid file"}), 400

    record_uuid = str(uuid.uuid4())
    filename = secure_filename(file.filename)
    supabase_name = f"{record_uuid}_{filename}"

    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(filename)[1]) as tmp:
        file.save(tmp.name)
        tmp_path = tmp.name

    if get_video_duration(tmp_path) > MAX_VIDEO_SECONDS:
        os.remove(tmp_path)
        return jsonify({"error": f"Video exceeds {MAX_VIDEO_SECONDS}s"}), 400

    with open(tmp_path, "rb") as vf:
        supabase.storage.from_(SUPABASE_BUCKET).upload(
            supabase_name,
            vf,
            {"content-type": "video/mp4"}
        )

    supabase.table("user_videos").insert({
        "uuid": record_uuid,
        "user_id": user_id,
        "video_url": supabase_name,
        "video_name": filename,
        "status": "processing"
    }).execute()

    supabase.table("predictions").insert({
        "uuid": record_uuid,
        "user_id": user_id,
        "video_url": supabase_name,
        "video_name": filename,
        "status": "processing",
        "prediction": ""
    }).execute()

    threading.Thread(
        target=background_prediction,
        args=(record_uuid, tmp_path),
        daemon=True
    ).start()

    return jsonify({
        "uuid": record_uuid,
        "status": "processing",
        "message": "Video uploaded, prediction started"
    })

# =========================================================
# History
# =========================================================
@app.route("/history")
def history():
    res = supabase.table("predictions") \
        .select("uuid, video_name, prediction, status, created_at") \
        .order("created_at", desc=True) \
        .limit(200) \
        .execute()

    return jsonify([
        {
            "uuid": str(r.get("uuid", "")),
            "video_name": str(r.get("video_name", "")),
            "prediction": str(r.get("prediction", "")),
            "status": str(r.get("status", "")),
            "created_at": str(r.get("created_at", ""))
        }
        for r in res.data
    ])

# =========================================================
# DELETE History
# =========================================================
@app.route("/history/<record_uuid>", methods=["DELETE"])
def delete_history(record_uuid):
    if not record_uuid or record_uuid == "null":
        return jsonify({"error": "Invalid UUID"}), 400

    supabase.table("predictions").delete().eq("uuid", record_uuid).execute()
    supabase.table("user_videos").delete().eq("uuid", record_uuid).execute()

    logging.info(f"Deleted record: {record_uuid}")

    return jsonify({
        "status": "deleted",
        "uuid": record_uuid
    })

# =========================================================
# Stats
# =========================================================
@app.route("/stats/<user_id>")
def stats(user_id):
    videos = supabase.table("user_videos").select("id", count="exact").eq("user_id", user_id).execute()
    preds = supabase.table("predictions").select("id", count="exact").eq("user_id", user_id).execute()

    return jsonify({
        "totalVideos": int(videos.count or 0),
        "historyCount": int(preds.count or 0)
    })

# =========================================================
# Run
# =========================================================
if __name__ == "__main__":
    logging.info("Starting AIPSRS backend (ASYNC) on Linux/Render")
    app.run(host="0.0.0.0", port=5000, debug=True)
