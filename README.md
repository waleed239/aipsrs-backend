# AIPSRS Backend — Flask REST API

The backend service for the **AI-Powered Silent Speech Recognition System (AIPSRS)**, a Final Year Project developed at Iqra University, Islamabad.

This Flask API connects the Flutter mobile application with a pretrained lip-reading model hosted on Replicate. It handles video submissions, prediction processing, and communication with Supabase services.

> **Important:** This project integrates a pretrained AI model. The model was not trained from scratch as part of this project.

## 🔗 Project Links

- **Complete Project Repository:** [AIPSRS](https://github.com/waleed239/AIPSRS)
- **Flutter Application:** [AIPSRS App](https://github.com/waleed239/aipsrs-app)
- **Backend Repository:** [aipsrs-backend](https://github.com/waleed239/aipsrs-backend)

## ✨ Features

- Flask REST API for the mobile application.
- Video upload and input validation.
- Integration with the pretrained lip-reading model through Replicate.
- Prediction processing using a background thread.
- Supabase Storage integration for uploaded videos.
- Supabase database integration for prediction records and history.
- Prediction status tracking.
- Health-check endpoint for deployment monitoring.
- Deployment support through Render.

## 🛠️ Technology Stack

| Component | Technology |
|---|---|
| Backend Language | Python |
| Web Framework | Flask |
| API Architecture | REST API |
| AI Inference | Replicate |
| Lip-Reading Model | `basord/lip-reading-ai-vsr` |
| Database | Supabase |
| File Storage | Supabase Storage |
| Deployment | Render |

## 🏗️ Architecture

```text
Flutter Mobile Application
           |
           | Video upload / REST API
           v
      Flask Backend
           |
           +------> Supabase Storage
           |        Uploaded videos
           |
           +------> Supabase Database
           |        Prediction records
           |
           +------> Replicate API
                    Pretrained lip-reading model
                           |
                           v
                    Predicted text
                           |
                           v
                    Supabase Database
```

## 🔄 Prediction Workflow

1. The user selects a video in the Flutter application.
2. The application sends the video to the Flask API.
3. The backend validates the uploaded file.
4. The video and prediction information are stored through Supabase.
5. The backend submits the video to the pretrained model through Replicate.
6. The prediction status is updated when processing completes or fails.
7. The application retrieves prediction information and displays the result.

Processing time and prediction quality depend on the external inference service and input video.

## 🔌 API Endpoints

The following endpoints are documented for this project. Request formats and authentication requirements should be verified against the current implementation in `app.py`.

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/health` | Check whether the API is running |
| `POST` | `/predict` | Submit a video for prediction |
| `GET` | `/history` | Retrieve prediction history |
| `DELETE` | `/history/<id>` | Delete a prediction record |
| `GET` | `/stats` | Retrieve video and prediction counts |

### Video Upload

The prediction endpoint accepts a video upload using multipart form data.

Documented accepted file extensions:

- MP4
- MOV
- AVI
- MKV

The documented maximum upload size is 200 MB. Actual model constraints may be more restrictive than the API's upload limit.

## 🚀 Run Locally

### Prerequisites

- Python
- pip
- A configured Supabase project
- A Replicate account and API token

### 1. Clone the repository

```bash
git clone https://github.com/waleed239/aipsrs-backend.git
cd aipsrs-backend
```

### 2. Create a virtual environment

**Windows:**

```bash
python -m venv .venv
.venv\Scripts\activate
```

**Linux/macOS:**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Create a local `.env` file using the variable names expected by `app.py`:

```env
REPLICATE_API_TOKEN=your_replicate_api_token
REPLICATE_MODEL=basord/lip-reading-ai-vsr
REPLICATE_VERSION=your_model_version
SUPABASE_URL=your_supabase_project_url
SUPABASE_KEY=your_server_side_supabase_key
```

Check `app.py` for the exact environment-variable names and required values. Do not commit your actual `.env` file.

**Security:** Keep the Supabase service-role key and Replicate API token private. Configure production secrets through Render's environment settings rather than placing them in source code.

### 5. Start the backend

Run the command configured for the project:

```bash
python app.py
```

If using the supplied startup script in a compatible environment:

```bash
bash start.sh
```

Check the script and application configuration for the actual listening port and startup requirements.

## ☁️ Render Deployment

This backend is deployed on Render.

For deployment:

1. Connect the backend GitHub repository to Render.
2. Configure the appropriate Python runtime and build command.
3. Set the start command according to `start.sh` or the Render service configuration.
4. Add the required environment variables in the Render Dashboard.
5. Deploy and inspect the service logs for errors.
6. Test the health-check endpoint if `/health` is enabled in the deployed version.

Do not publish private deployment credentials in this repository.

## ⚠️ Limitations

- The system processes uploaded videos; it does not provide real-time camera-based lip-reading.
- The current application focuses on English-language predictions.
- Prediction quality depends on the pretrained model and input video.
- Inference requires an internet connection and an available Replicate service.
- External API usage may incur charges.
- Authentication and authorization require further security hardening before production use.

### Security Considerations

The current implementation has documented authentication limitations. In particular, user identity must not be trusted solely from a request parameter or an unverified token.

Before production use:

- Verify Supabase access tokens using a trusted verification method.
- Derive the user ID from the verified identity rather than trusting a submitted `user_id`.
- Enforce authorization checks for prediction history and deletion.
- Configure appropriate Supabase Row Level Security (RLS) policies.
- Keep service-role keys and private API tokens exclusively on the server.
- Add appropriate request limits, error handling, and monitoring.

## 🔮 Future Improvements

- Stronger authentication and authorization.
- Better input validation and error reporting.
- Improved inference latency and processing reliability.
- More comprehensive prediction evaluation.
- Additional language support.
- Automated testing and deployment checks.

## 👨‍💻 Authors

**Muhammad Waleed Wazir** and **Mohammad Adil**

Final Year Project — BS Computer Science, Iqra University.

- GitHub: [@waleed239](https://github.com/waleed239)
- Portfolio: [Personal Portfolio](https://waleed239.github.io/portfolio-website/)

---

AIPSRS explores the integration of mobile development, backend services, cloud storage, and pretrained AI inference to support silent lip-reading from uploaded videos.
