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
import jwt  # PyJWT

# Added for video splitting
from moviepy.editor import VideoFileClip

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

def get_user_id_from_token():
    """Extract user_id from Supabase JWT token in Authorization header"""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    token = auth_header.replace("Bearer ", "")
    try:
        decoded = jwt.decode(token, options={"verify_signature": False})
        return decoded.get("sub")
    except Exception:
        return None


# =========================================================
# Video Splitting (23 sec chunks)
# =========================================================
def split_video_to_chunks(video_path, chunk_duration=23):
    clip = VideoFileClip(video_path)
    duration = int(clip.duration)
    chunks = []

    start = 0
    while start < duration:
        end = min(start + chunk_duration, duration)
        chunk_path = f"{video_path}_chunk_{start}.mp4"
        clip.subclip(start, end).write_videofile(
            chunk_path,
            codec="libx264",
            audio_codec="aac",
            verbose=False,
            logger=None
        )
        chunks.append(chunk_path)
        start += chunk_duration

    clip.close()
    return chunks


# =========================================================
# Background Prediction (ASYNC THREAD)
# =========================================================
def background_prediction(record_uuid: str, video_path: str):
    try:
        logging.info(f"Starting prediction: {record_uuid}")

        model = replicate.models.get(REPLICATE_MODEL)
        version = model.versions.get(REPLICATE_VERSION)

        # Split video into chunks of 23 sec
        chunks = split_video_to_chunks(video_path, chunk_duration=23)

        all_outputs = []

        for chunk in chunks:
            with open(chunk, "rb") as vf:
                output = replicate.run(
                    version,
                    input={"video": vf},
                    api_token=REPLICATE_API_TOKEN
                )

            if isinstance(output, list):
                all_outputs.extend(output)
            else:
                all_outputs.append(str(output))

            # delete chunk after prediction
            if os.path.exists(chunk):
                os.remove(chunk)

        prediction_text = " ".join(all_outputs)

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
# History (USER-SPECIFIC)
# ---------------------------------------------------------
@app.route("/history")
def history():
    user_id = get_user_id_from_token()
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    res = (
        supabase.table("predictions")
        .select("uuid, video_name, prediction, status, created_at")
        .eq("user_id", user_id)
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
# Delete History (USER-SPECIFIC)
# ---------------------------------------------------------
@app.route("/history/<record_uuid>", methods=["DELETE"])
def delete_history(record_uuid):
    user_id = get_user_id_from_token()
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    # Delete only if record belongs to logged-in user
    supabase.table("predictions") \
        .delete() \
        .eq("uuid", record_uuid) \
        .eq("user_id", user_id) \
        .execute()

    supabase.table("user_videos") \
        .delete() \
        .eq("uuid", record_uuid) \
        .eq("user_id", user_id) \
        .execute()

    logging.info(f"Deleted record: {record_uuid} (user: {user_id})")

    return jsonify({
        "status": "deleted",
        "uuid": record_uuid
    })


# ---------------------------------------------------------
# Stats
# ---------------------------------------------------------
@app.route("/stats")
def stats():
    user_id = get_user_id_from_token()
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    videos = supabase.table("user_videos").select("id", count="exact").eq("user_id", user_id).execute()
    preds = supabase.table("predictions").select("id", count="exact").eq("user_id", user_id).execute()

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
