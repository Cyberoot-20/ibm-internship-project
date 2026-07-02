"""
Smart Business Idea Generator — Flask Backend
IBM Watsonx.ai + Granite | Multimodal | Chat | Dashboard
"""
import os, json, uuid, logging
from pathlib import Path
from flask import (Flask, render_template, request, jsonify, session)
from flask_cors import CORS
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

# ── optional: Pillow (no pre-built wheel for Python 3.14 on Windows yet) ─────
try:
    from PIL import Image as PILImage
    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False

# ── load env vars ─────────────────────────────────────────────────────────────
load_dotenv()

# ── logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ── agent imports ─────────────────────────────────────────────────────────────
from agent.agent_config import (
    AGENT_NAME, AGENT_VERSION, IDEAS_PER_GENERATION,
    TRENDING_DOMAINS, IDEA_SCHEMA_FIELDS, DOMAIN_FOCUS,
    AGENT_TONE, CREATIVITY_SCORE, build_system_prompt,
)
from agent.watsonx_client import (
    WatsonxClient, build_idea_prompt, build_followup_prompt,
    parse_ideas_from_response,
)

# ── Flask app ─────────────────────────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-key")
app.config["MAX_CONTENT_LENGTH"] = int(os.getenv("MAX_CONTENT_LENGTH", 16 * 1024 * 1024))
UPLOAD_FOLDER = Path(os.getenv("UPLOAD_FOLDER", "static/uploads"))
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
ALLOWED_IMG = {"png", "jpg", "jpeg", "gif", "webp"}
ALLOWED_AUDIO = {"wav", "mp3", "ogg", "m4a", "webm"}

CORS(app, resources={r"/api/*": {"origins": "*"}})

# ── singleton Watsonx client ──────────────────────────────────────────────────
watsonx = WatsonxClient()

# ── global JSON error handlers (prevents HTML 500 pages reaching the browser) ─
@app.errorhandler(400)
def bad_request(e):
    return jsonify(error=str(e), status=400), 400

@app.errorhandler(404)
def not_found(e):
    return jsonify(error="Not found", status=404), 404

@app.errorhandler(405)
def method_not_allowed(e):
    return jsonify(error="Method not allowed", status=405), 405

@app.errorhandler(500)
def internal_error(e):
    logger.error("Unhandled 500: %s", e)
    return jsonify(error="Internal server error — check server logs.", status=500), 500

@app.errorhandler(Exception)
def unhandled_exception(e):
    logger.exception("Unhandled exception: %s", e)
    return jsonify(error=f"Unexpected error: {type(e).__name__}: {e}", status=500), 500

# ── helpers ───────────────────────────────────────────────────────────────────
def allowed_file(filename: str, allowed: set) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed

def describe_image(image_path: str) -> str:
    """
    Placeholder for vision model integration.
    Returns a textual description heuristic from filename / size.
    Replace with actual vision API call if available.
    """
    name = Path(image_path).stem.replace("-", " ").replace("_", " ")
    return (
        f"The uploaded image appears to be related to '{name}'. "
        "The image shows what could be a product concept or business sketch. "
        "Please incorporate any visual elements (shapes, text, diagrams) as inspiration."
    )

def transcribe_voice(audio_path: str) -> str:
    """
    Attempt speech-to-text via SpeechRecognition.
    Falls back gracefully if unavailable.
    """
    try:
        import speech_recognition as sr
        recognizer = sr.Recognizer()
        with sr.AudioFile(audio_path) as source:
            audio_data = recognizer.record(source)
            return recognizer.recognize_google(audio_data)
    except Exception as exc:
        logger.warning("Voice transcription failed: %s", exc)
        return "[Voice note received — transcription unavailable in demo mode. Please describe your idea in text.]"

# ══════════════════════════════════════════════════════════════════════════════
#  ROUTES
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/")
def index():
    return render_template("index.html",
        agent_name=AGENT_NAME,
        agent_version=AGENT_VERSION,
        trending_domains=TRENDING_DOMAINS,
        domain_focus=DOMAIN_FOCUS,
        agent_tone=AGENT_TONE,
        creativity_score=CREATIVITY_SCORE,
    )


# ── /api/generate — main idea generation endpoint ────────────────────────────
@app.route("/api/generate", methods=["POST"])
def generate_ideas():
    """
    Body (multipart/form-data or JSON):
      prompt   — user text prompt (required)
      context  — optional pasted article / trend data
      n_ideas  — number of ideas (default: IDEAS_PER_GENERATION)
    Files (optional):
      image    — product sketch or reference image
      audio    — voice note
    """
    # ── parse inputs ──────────────────────────────────────────────────────────
    if request.content_type and "multipart" in request.content_type:
        prompt  = request.form.get("prompt", "").strip()
        context = request.form.get("context", "").strip()
        n_ideas = int(request.form.get("n_ideas", IDEAS_PER_GENERATION))
    else:
        data    = request.get_json(silent=True) or {}
        prompt  = data.get("prompt", "").strip()
        context = data.get("context", "").strip()
        n_ideas = int(data.get("n_ideas", IDEAS_PER_GENERATION))

    if not prompt:
        return jsonify({"error": "prompt is required"}), 400

    image_desc = ""
    voice_text = ""

    # ── handle image upload ───────────────────────────────────────────────────
    if "image" in request.files:
        img = request.files["image"]
        if img and allowed_file(img.filename, ALLOWED_IMG):
            fname = secure_filename(f"{uuid.uuid4().hex}_{img.filename}")
            img_path = UPLOAD_FOLDER / fname
            img.save(img_path)
            image_desc = describe_image(str(img_path))

    # ── handle audio upload ───────────────────────────────────────────────────
    if "audio" in request.files:
        aud = request.files["audio"]
        if aud and allowed_file(aud.filename, ALLOWED_AUDIO):
            fname = secure_filename(f"{uuid.uuid4().hex}_{aud.filename}")
            aud_path = UPLOAD_FOLDER / fname
            aud.save(aud_path)
            voice_text = transcribe_voice(str(aud_path))

    # ── build prompt & call model ─────────────────────────────────────────────
    system_prompt = build_system_prompt()
    full_prompt   = build_idea_prompt(
        system_prompt=system_prompt,
        user_input=prompt,
        context=context,
        image_desc=image_desc,
        voice_text=voice_text,
        n_ideas=n_ideas,
    )

    logger.info("Generating %d ideas for prompt: %s…", n_ideas, prompt[:60])
    raw_response = watsonx.generate(full_prompt)
    ideas        = parse_ideas_from_response(raw_response)

    # ── attach IDs & store in session ─────────────────────────────────────────
    for i, idea in enumerate(ideas):
        idea["id"] = i + 1
    session["last_ideas"] = ideas
    session["chat_history"] = []

    return jsonify({
        "ideas":         ideas,
        "raw_response":  raw_response,
        "voice_text":    voice_text,
        "image_desc":    image_desc,
        "ideas_count":   len(ideas),
        "prompt_used":   prompt,
    })


# ── /api/chat — conversational follow-up ─────────────────────────────────────
@app.route("/api/chat", methods=["POST"])
def chat():
    """
    Body (JSON):
      message  — user follow-up message
    Session holds chat_history and last_ideas.
    """
    data    = request.get_json(silent=True) or {}
    message = data.get("message", "").strip()
    if not message:
        return jsonify({"error": "message is required"}), 400

    history = session.get("chat_history", [])
    ideas   = session.get("last_ideas", [])

    ideas_context = ""
    if ideas:
        lines = []
        for idea in ideas:
            lines.append(
                f"Idea {idea.get('id','?')}: {idea.get('title','')} — "
                f"{idea.get('one_line_pitch','')} "
                f"(Impact: {idea.get('impact_score','?')}/10, "
                f"Feasibility: {idea.get('feasibility_score','?')}/10)"
            )
        ideas_context = "\n".join(lines)

    system_prompt = build_system_prompt()
    full_prompt   = build_followup_prompt(
        system_prompt=system_prompt,
        history=history,
        user_message=message,
        ideas_context=ideas_context,
    )

    raw_response = watsonx.generate(full_prompt)

    # ── update history ─────────────────────────────────────────────────────────
    history.append({"role": "user",      "content": message})
    history.append({"role": "assistant", "content": raw_response})
    session["chat_history"] = history[-20:]  # keep last 20 turns

    # check if response contains new ideas
    new_ideas = parse_ideas_from_response(raw_response)
    if new_ideas:
        for i, idea in enumerate(new_ideas):
            idea["id"] = i + 1
        session["last_ideas"] = new_ideas

    return jsonify({
        "reply":     raw_response,
        "new_ideas": new_ideas if new_ideas else None,
    })


# ── /api/config — agent configuration info ───────────────────────────────────
@app.route("/api/config", methods=["GET"])
def get_config():
    return jsonify({
        "agent_name":       AGENT_NAME,
        "agent_version":    AGENT_VERSION,
        "domain_focus":     DOMAIN_FOCUS,
        "agent_tone":       AGENT_TONE,
        "creativity_score": CREATIVITY_SCORE,
        "trending_domains": TRENDING_DOMAINS,
        "ideas_schema":     IDEA_SCHEMA_FIELDS,
        "model_id":         os.getenv("WATSONX_MODEL_ID", "ibm/granite-13b-instruct-v2"),
        "api_connected":    bool(os.getenv("WATSONX_API_KEY")) and not watsonx._auth_failed,
    })


# ── /api/trending — trending domain data ─────────────────────────────────────
@app.route("/api/trending", methods=["GET"])
def get_trending():
    dataset_path = Path("ideas_dataset.json")
    if dataset_path.exists():
        with open(dataset_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
            return jsonify(data.get("trending_domains", []))
    return jsonify([])


# ── /api/sample — return sample ideas for testing ────────────────────────────
@app.route("/api/sample", methods=["GET"])
def get_sample():
    dataset_path = Path("ideas_dataset.json")
    if dataset_path.exists():
        with open(dataset_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
            ideas = data.get("sample_ideas", [])
            for i, idea in enumerate(ideas):
                idea["id"] = i + 1
            session["last_ideas"] = ideas
            return jsonify({"ideas": ideas, "source": "sample_dataset"})
    return jsonify({"ideas": [], "source": "empty"})


# ── /api/health ───────────────────────────────────────────────────────────────
@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({
        "status":  "ok",
        "agent":   AGENT_NAME,
        "version": AGENT_VERSION,
    })


# ── run ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    port  = int(os.getenv("FLASK_PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "False").lower() == "true"
    logger.info("Starting %s v%s on port %d", AGENT_NAME, AGENT_VERSION, port)

    if debug:
        # Development: Flask built-in server
        app.run(host="0.0.0.0", port=port, debug=True)
    else:
        # Production: use waitress (cross-platform, works on Windows)
        try:
            from waitress import serve
            logger.info("Using waitress WSGI server (Windows/production mode)")
            serve(app, host="0.0.0.0", port=port, threads=4)
        except ImportError:
            # Fallback to Flask dev server if waitress not installed
            logger.warning("waitress not installed, falling back to Flask dev server")
            app.run(host="0.0.0.0", port=port, debug=False)
