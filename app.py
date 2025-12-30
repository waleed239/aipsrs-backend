"""
AIPSRS - Flask Backend (Render / Linux Production Ready)
ASYNC Replicate Prediction + Supabase + Stable Upload
"""

import os
import uuid
import logging
import tempfile
import threading
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.utils import secure_filename

import replicate
from supabase import create_client

# =========================================================
# Load ENV
# =========================================================
load_dotenv()

REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN")
REPLICATE_MODEL = os.getenv("REPLICATE_MODEL")
REPLICATE_VERSION = os.getenv("REPLICATE_VERSION")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")  # Service Role Key
SUPABASE_BUCKET = "videos"

if not all([REPLICATE_API_TOKEN, REPLICATE_MODEL, REPLICATE_VERSION]):
    raise ValueError("Replicate configuration missing")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Supabase credentials missing")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# =========================================================
# App & Logging
# =========================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 200 * 1024 * 1024  # 200MB
CORS(app)

# =========================================================
# Utils
# =========================================================
ALLOWED_EXTENSIONS = {"mp4", "mov", "avi", "mkv"}

def allowed_file(filename: str) -> bool:
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
    )

# =========================================================
# Background Prediction (ASYNC THREAD)
# =========================================================
def background_prediction(record_uuid: str, video_path: str):
    try:
        logging.info(f"Starting prediction: {record_uuid}")

        model = replicate.models.get(REPLICATE_MODEL)
        version = model.versions.get(REPLICATE_VERSION)

        with open(video_path, "rb") as vf:
            output = replicate.run(
                version,
                input={"video": vf},
                api_token=REPLICATE_API_TOKEN
            )

        prediction_text = (
            " ".join(output) if isinstance(output, list) else str(output)
        )

        supabase.table("predictions").update({
            "prediction": prediction_text,
            "status": "completed"
        }).eq("uuid", record_uuid).execute()

        supabase.table("user_videos").update({
            "status": "completed"
        }).eq("uuid", record_uuid).execute()

        logging.info(f"Prediction completed: {record_uuid}")

    except Exception as e:
        logging.exception("Prediction failed")

        supabase.table("predictions").update({
            "status": "failed",
            "prediction": ""
        }).eq("uuid", record_uuid).execute()

        supabase.table("user_videos").update({
            "status": "failed"
        }).eq("uuid", record_uuid).execute()

    finally:
        try:
            if os.path.exists(video_path):
                os.remove(video_path)
        except Exception:
            pass

# =========================================================
# Routes
# =========================================================
@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "time": datetime.utcnow().isoformat()
    })

# ---------------------------------------------------------
# Predict
# ---------------------------------------------------------
@app.route("/predict", methods=["POST"])
def predict():
    user_id = request.form.get("user_id")
    if not user_id:
        return jsonify({"error": "user_id required"}), 400

    if "video" not in request.files:
        return jsonify({"error": "video required"}), 400

    file = request.files["video"]
    if not file.filename or not allowed_file(file.filename):
        return jsonify({"error": "invalid file type"}), 400

    record_uuid = str(uuid.uuid4())
    filename = secure_filename(file.filename)
    storage_name = f"{record_uuid}_{filename}"

    # Save temp file
    with tempfile.NamedTemporaryFile(
        delete=False,
        suffix=os.path.splitext(filename)[1]
    ) as tmp:
        file.save(tmp.name)
        tmp_path = tmp.name

    # Upload to Supabase Storage
    with open(tmp_path, "rb") as vf:
        supabase.storage.from_(SUPABASE_BUCKET).upload(
            storage_name,
            vf,
            {"content-type": "video/mp4"}
        )

    # DB Records
    supabase.table("user_videos").insert({
        "uuid": record_uuid,
        "user_id": user_id,
        "video_url": storage_name,
        "video_name": filename,
        "status": "processing"
    }).execute()

    supabase.table("predictions").insert({
        "uuid": record_uuid,
        "user_id": user_id,
        "video_url": storage_name,
        "video_name": filename,
        "status": "processing",
        "prediction": ""
    }).execute()

    # Async prediction
    threading.Thread(
        target=background_prediction,
        args=(record_uuid, tmp_path),
        daemon=True
    ).start()

    return jsonify({
        "uuid": record_uuid,
        "status": "processing",
        "message": "Video uploaded. Prediction started."
    })

# ---------------------------------------------------------
# History
# ---------------------------------------------------------
@app.route("/history")
def history():
    res = (
        supabase.table("predictions")
        .select("uuid, video_name, prediction, status, created_at")
        .order("created_at", desc=True)
        .limit(200)
        .execute()
    )

    return jsonify([
        {
            "uuid": str(r.get("uuid", "")),
            "video_name": str(r.get("video_name", "")),
            "prediction": str(r.get("prediction", "")),
            "status": str(r.get("status", "")),
            "created_at": str(r.get("created_at", "")),
        }
        for r in (res.data or [])
    ])

# ---------------------------------------------------------
# Delete History
# ---------------------------------------------------------
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

# ---------------------------------------------------------
# Stats
# ---------------------------------------------------------
@app.route("/stats/<user_id>")
def stats(user_id):
    videos = supabase.table("user_videos").select(
        "id", count="exact"
    ).eq("user_id", user_id).execute()

    preds = supabase.table("predictions").select(
        "id", count="exact"
    ).eq("user_id", user_id).execute()

    return jsonify({
        "totalVideos": int(videos.count or 0),
        "historyCount": int(preds.count or 0)
    })

# =========================================================
# Run (Local Only)
# =========================================================
if __name__ == "__main__":
    logging.info("Starting AIPSRS backend (DEV)")
    app.run(host="0.0.0.0", port=5000, debug=True)
