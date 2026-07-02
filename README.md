# IdeaForge AI — Smart Business Idea Generator
### Powered by IBM Watsonx.ai + Granite

> Generate, explore, and visualize breakthrough business ideas with AI — multimodal, context-aware, and actionable.

---

## 🏗️ Project Structure

```
smart-idea-generator/
├── app.py                       # Flask backend — all API routes
├── requirements.txt             # Python dependencies
├── ideas_dataset.json           # Sample ideas for offline/demo testing
├── agent/
│   ├── __init__.py
│   ├── agent_config.py          # ← AGENT INSTRUCTIONS — customize here
│   └── watsonx_client.py        # IBM Watsonx.ai integration client
├── templates/
│   └── index.html               # Main UI template (Jinja2)
├── static/
│   ├── css/style.css            # Complete stylesheet (dark/light theme)
│   ├── js/app.js                # Frontend logic (Chart.js, chat, uploads)
│   └── uploads/                 # Uploaded images/audio (auto-cleared)
```

---

## ⚡ Quick Start

### 1. Prerequisites
- Python 3.9+ 
- pip or pip3
- IBM Watsonx.ai account (or use Demo Mode without API key)

### 2. Install dependencies
```bash
cd smart-idea-generator
pip install -r requirements.txt
```

### 3. Configure credentials
Your `.env` file is pre-configured. Verify it contains:
```env
WATSONX_API_KEY=your_key_here
WATSONX_PROJECT_ID=your_project_id_here
WATSONX_URL=https://us-south.ml.cloud.ibm.com
```

### 4. Run the application
```bash
python app.py
```

Visit: **http://localhost:5000**

---

## 🤖 Customizing the Agent (AGENT_INSTRUCTIONS)

Open **`agent/agent_config.py`** to customize:

```python
# Domain specialization: "startups" | "research" | "content" | "product"
DOMAIN_FOCUS = "startups"

# Tone: "professional" | "casual" | "visionary" | "analytical" | "motivational"
AGENT_TONE = "visionary"

# Creativity vs Feasibility: 1 (pure feasibility) → 10 (moonshot creativity)
CREATIVITY_SCORE = 7

# IBM Watsonx Granite model
WATSONX_MODEL_ID = "ibm/granite-13b-instruct-v2"

# Ideas per generation
IDEAS_PER_GENERATION = 5
```

All changes take effect immediately on next request (no rebuild needed).

---

## 🎯 Features

| Feature | Description |
|---------|-------------|
| **Text Generation** | Free-form prompts grounded in user context |
| **Context Fusion** | Paste articles/trend data to inform generation |
| **Image Upload** | Upload product sketches for visual inspiration |
| **Voice Notes** | Record or upload audio; auto-transcribed |
| **Idea Cards** | Animated cards with impact/feasibility scores |
| **Idea Map** | Interactive Chart.js scatter plot (quadrant view) |
| **Table View** | Sortable table overview of all ideas |
| **Chat Refinement** | Follow-up questions, idea combination, pivots |
| **Dark/Light Mode** | Full theme toggle with localStorage persistence |
| **Trending Domains** | Live domain chips that inject into prompts |
| **Sample Dataset** | Works 100% offline with no API key needed |

---

## 🔌 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET`  | `/`      | Main UI |
| `POST` | `/api/generate` | Generate ideas (multipart/form-data) |
| `POST` | `/api/chat`     | Chat follow-up (JSON) |
| `GET`  | `/api/sample`   | Load sample ideas |
| `GET`  | `/api/config`   | Agent configuration |
| `GET`  | `/api/trending` | Trending domain data |
| `GET`  | `/api/health`   | Health check |

### Generate Ideas — Request
```
POST /api/generate
Content-Type: multipart/form-data

prompt    (required)  — User prompt string
context   (optional)  — Background article/trend text
n_ideas   (optional)  — Number of ideas (default: 5, max: 10)
image     (optional)  — Image file (PNG/JPG/WEBP)
audio     (optional)  — Audio file (WAV/MP3/M4A)
```

### Idea JSON Schema
```json
{
  "id": 1,
  "title": "MedSync AI",
  "one_line_pitch": "AI copilot that syncs patient records in real time.",
  "target_domain": "AI in Healthcare",
  "impact_score": 9,
  "feasibility_score": 6,
  "required_resources": ["FHIR API", "Cloud infra", "HIPAA team"],
  "next_step": "Partner with 2 hospitals for a 90-day pilot.",
  "market_timing": "now"
}
```

---

## 🚀 Deployment

### Option A: Local / Development
```bash
python app.py
# Runs on http://0.0.0.0:5000
```

### Option B: Production with Gunicorn
```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

### Option C: Docker
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
EXPOSE 5000
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "app:app"]
```

```bash
docker build -t ideaforge-ai .
docker run -p 5000:5000 --env-file .env ideaforge-ai
```

### Option D: IBM Code Engine
```bash
ibmcloud login
ibmcloud ce project create --name ideaforge-ai
ibmcloud ce app create \
  --name ideaforge-ai \
  --image icr.io/myrepo/ideaforge-ai \
  --port 5000 \
  --env-from-secret watsonx-credentials
```

### Environment Variables for Production
```env
WATSONX_API_KEY=<your_key>
WATSONX_PROJECT_ID=<your_project_id>
WATSONX_URL=https://us-south.ml.cloud.ibm.com
FLASK_SECRET_KEY=<random_64char_string>
FLASK_DEBUG=False
FLASK_PORT=5000
```

---

## 🔒 Security Notes

- **Never commit `.env`** to version control (already in `.gitignore`)
- Rotate `FLASK_SECRET_KEY` before production deployment
- Upload folder is not served as static files — paths are hashed
- Set `MAX_CONTENT_LENGTH` to limit upload size
- Use HTTPS in production (Nginx/reverse proxy)

---

## 🧪 Demo Mode (No API Key)

Click **"Load Sample Dataset"** to explore 10 pre-built ideas covering:
- AI in Healthcare, CleanTech, EdTech, FinTech
- Space Commerce, Quantum Computing, Web3
- Longevity/Biotech, AgriTech, Robotics

All UI features (Idea Map, Chat, Table, Modal) work with sample data.

---

## 🛠️ Troubleshooting

| Problem | Solution |
|---------|----------|
| `ibm-watsonx-ai not installed` | Run `pip install ibm-watsonx-ai` |
| `WATSONX_API_KEY missing` | Check `.env` file in project root |
| Ideas return empty | API key may be invalid; use Sample mode to verify UI |
| Voice transcription fails | Install `SpeechRecognition` and `pydub`; ensure ffmpeg is on PATH |
| Chart not rendering | Ensure Chart.js CDN is reachable or host locally |

---

*IdeaForge AI v2.0.0 — Built with IBM Watsonx.ai + Granite*
