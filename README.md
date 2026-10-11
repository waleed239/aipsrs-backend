AIPSRS Backend

Flask backend for AIPSRS (AI Powered Silent Speech Recognition System), a final-year project at Iqra University (BS Computer Science, 2025). A Flutter app uploads a silent video, and the backend returns the lip-read text.

Mobile app (Flutter): https://github.com/waleed239/aipsrs-app

What this project is, and is not
Is: an end-to-end system: Flutter app, Flask API, Supabase storage, database and authentication, and an external lip-reading model.
Is not: a newly trained model. No model was trained in this project. Predictions come from the pre-trained model basord/lip-reading-ai-vsr hosted on Replicate, credited to its author. The contribution of this project is the integration, storage, validation and evaluation pipeline.
How it works
Flutter app --(video)--> Flask API --> Supabase Storage (video file)
                            |-------> Supabase tables: user_videos, predictions
                            |-------> Replicate: basord/lip-reading-ai-vsr
                                      (runs in a background thread)
The app sends a video to POST /predict.
The API checks the file type, stores the video in the Supabase bucket videos and creates records with status processing.
A background thread sends the video to the Replicate model and saves the text with status completed (or failed). The temporary file is deleted afterwards.
The app reads results from GET /history.
Endpoints
Method	Path	Input	Purpose
GET	/health	none	Health check
POST	/predict	multipart form: video (file), user_id	Upload a video and start a prediction
GET	/history	Authorization: Bearer <Supabase access token>	The user's last 200 predictions
DELETE	/history/<uuid>	Bearer token	Delete one prediction record
GET	/stats	Bearer token	Counts of videos and predictions

Accepted upload types: mp4, mov, avi, mkv. Maximum upload size: 200 MB.

Configuration

Create a .env file (see .env.example). It is never committed.

Variable	Purpose
REPLICATE_API_TOKEN	Replicate access token
REPLICATE_MODEL	Model name (basord/lip-reading-ai-vsr)
REPLICATE_VERSION	Model version id
SUPABASE_URL	Supabase project URL
SUPABASE_KEY	Supabase service-role key (server-side only)
Run locally
bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # then add your own values
python app.py

The deployed version runs on Render using start.sh.

Model constraints (from the model's Replicate page)
Formats: MP4, MOV, MKV, WebM; 2 to 40 seconds; at most 1080p
Exactly one visible face; best with good lighting and an unobstructed mouth
Evaluation

Results: to be added after the evaluation runs (number of clips, conditions, word error rate, character error rate, response time).

Known limitations
Accuracy and latency depend on an external model and on video quality.
Each prediction calls a paid external API, so an internet connection is required.
Authentication is basic: /history, /history/<uuid> and /stats read the user id from the Supabase token without verifying its signature, and /predict takes user_id from the request. This is acceptable for a prototype but not for production. Planned fix: verify tokens with Supabase and take the user id from the verified token.
English, uploaded videos only. There is no real-time camera input.
Authors

Muhammad Waleed Wazir and Mohammad Adil, final-year project, Iqra University.
