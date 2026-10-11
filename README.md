AIPSRS — Flask Backend
Python/Flask backend for AI-Powered Silent Speech Recognition System (AIPSRS), a final-year project that converts uploaded silent-speech videos into predicted text using a third-party visual speech recognition model.
The service connects the Flutter client to a model hosted on Replicate. This repository integrates a pre-existing model; it does not train one.
Responsibilities
- Receive or process requests from the Flutter client
- Coordinate video-based inference requests
- Communicate with the Replicate API
- Return inference status/results for display in the app
- Support deployment on Render
Stack
- Python and Flask
- Replicate API (external model inference)
- Render (deployment)
- Flutter frontend and Supabase services in the wider project
Repository files
- app.py — application/server implementation
- requirements.txt — Python dependencies
- start.sh — startup script
- FYP_Demo_video.mp4 — project demonstration video
Local setup
git clone https://github.com/waleed239/aipsrs-backend.git
cd aipsrs-backend
python -m venv .venv
Activate the environment:
# Linux / macOS
source .venv/bin/activate

# Windows PowerShell
.venv\Scripts\Activate.ps1
Install dependencies:
pip install -r requirements.txt
Set the credentials required by app.py in your local environment. For example, if the implementation reads REPLICATE_API_TOKEN:
# Linux / macOS
export REPLICATE_API_TOKEN="your_token_here"
Then start the application using the command supported by the current app.py or start.sh. Check those files for the actual port, Flask application name, and environment variables before deployment.
System flow
Flutter mobile app
       |
       v
Flask API (this repository)
       |
       v
Replicate visual speech recognition model
       |
       v
Prediction result -> Flutter app
The wider project uses Supabase for authentication, data storage, and user history.
API documentation
Endpoint paths, methods, request payloads, and response schemas should be documented from app.py. They are intentionally not invented here. Add a table of the implemented routes and a tested request/response example before presenting this as a public API.
Security and deployment notes
- Keep API tokens in environment variables, never in committed source code.
- Restrict access to stored videos and personal data appropriately.
- Validate video types, sizes, and remote URLs before processing.
- Add timeouts, error handling, and request limits for production use.
- Do not treat the academic prototype as a production-ready service.
Known limitations
Inference accuracy and latency depend on the external model and infrastructure. Long-running requests can delay responses. The current project targets English and uploaded videos, not real-time camera transcription.
Frontend
AIPSRS Flutter app
Authors
Muhammad Waleed Wazir and Mohammad Adil — Final-year project.
