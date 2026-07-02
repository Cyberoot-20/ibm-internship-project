"""
IBM Watsonx.ai client — wraps ibm-watsonx-ai SDK with retry logic,
token caching, and structured idea parsing.
"""
import os, json, re, time, logging
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# ── lazy imports so app starts even if SDK is absent (demo mode) ──────────────
# Supports ibm-watsonx-ai >= 1.1.x and 1.5.x  (Python 3.14 compatible)
WATSONX_AVAILABLE = False
try:
    # SDK 1.5.x import paths
    from ibm_watsonx_ai import Credentials
    from ibm_watsonx_ai.foundation_models import ModelInference
    try:
        # 1.5.x path
        from ibm_watsonx_ai.foundation_models.schema import TextGenParameters as GenParams
    except ImportError:
        # 1.1.x fallback
        from ibm_watsonx_ai.metanames import GenTextParamsMetaNames as GenParams
    WATSONX_AVAILABLE = True
except ImportError:
    logger.warning("ibm-watsonx-ai not installed — running in DEMO mode.")


class WatsonxClient:
    """Thin wrapper around Watsonx.ai Granite model inference."""

    def __init__(self):
        self.api_key    = os.getenv("WATSONX_API_KEY", "")
        self.project_id = os.getenv("WATSONX_PROJECT_ID", "")
        self.url        = os.getenv("WATSONX_URL", "https://us-south.ml.cloud.ibm.com")
        self._model: Optional[object] = None
        self._auth_failed = False   # set True on first auth failure → skip future attempts

    # ── internal helpers ──────────────────────────────────────────────────────
    def _get_model(self):
        if self._model is not None:
            return self._model
        # If auth already failed once, go straight to demo mode
        if self._auth_failed:
            return None
        if not WATSONX_AVAILABLE:
            return None
        if not self.api_key or not self.project_id:
            logger.warning("WATSONX_API_KEY or WATSONX_PROJECT_ID missing — using demo mode.")
            return None

        from agent.agent_config import WATSONX_MODEL_ID, MODEL_PARAMETERS, CREATIVITY_SCORE
        params = dict(MODEL_PARAMETERS)
        # scale temperature with creativity score (0.3 – 0.95)
        params["temperature"] = round(0.3 + (CREATIVITY_SCORE - 1) * (0.65 / 9), 2)

        try:
            credentials = Credentials(url=self.url, api_key=self.api_key)
            # SDK 1.5.x — ModelInference accepts credentials directly
            self._model = ModelInference(
                model_id=WATSONX_MODEL_ID,
                credentials=credentials,
                project_id=self.project_id,
                params=params,
            )
            logger.info("Watsonx model initialised: %s", WATSONX_MODEL_ID)
        except TypeError:
            # SDK 1.1.x fallback — map param keys via GenParams metanames
            try:
                from ibm_watsonx_ai import APIClient
                credentials = Credentials(url=self.url, api_key=self.api_key)
                APIClient(credentials)
                mapped = {getattr(GenParams, k.upper(), k): v for k, v in params.items()}
                self._model = ModelInference(
                    model_id=WATSONX_MODEL_ID,
                    credentials=credentials,
                    project_id=self.project_id,
                    params=mapped,
                )
                logger.info("Watsonx model initialised (1.1.x compat): %s", WATSONX_MODEL_ID)
            except Exception as exc:
                # Auth failure in 1.1.x path
                self._auth_failed = True
                logger.warning("Watsonx auth failed (1.1.x): %s — switching to demo mode.", exc)
                return None
        except Exception as exc:
            # Catches InvalidCredentialsError, network errors, any other SDK exception
            self._auth_failed = True
            logger.warning("Watsonx auth/init failed: %s — switching to demo mode.", exc)
            return None

        return self._model

    # ── public API ────────────────────────────────────────────────────────────
    def generate(self, prompt: str) -> str:
        """Send prompt → return raw text response. NEVER raises — always returns a string."""
        try:
            model = self._get_model()
            if model is None:
                return self._demo_fallback(prompt)
            response = model.generate_text(prompt=prompt)
            return response if isinstance(response, str) else str(response)
        except Exception as exc:
            logger.error("Watsonx generate error: %s — falling back to demo.", exc)
            return self._demo_fallback(prompt)

    # ── demo / offline fallback ───────────────────────────────────────────────
    @staticmethod
    def _demo_fallback(prompt: str) -> str:
        """Return a realistic sample ideas JSON when API is unavailable."""
        sample_path = os.path.join(os.path.dirname(__file__),
                                   "..", "ideas_dataset.json")
        sample_path = os.path.normpath(sample_path)
        if os.path.exists(sample_path):
            with open(sample_path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
                ideas = data.get("sample_ideas", [])[:5]
                return "```json\n" + json.dumps(ideas, indent=2) + "\n```"
        return '```json\n[{"title":"Demo Idea","one_line_pitch":"Demo mode — connect API for live results","target_domain":"General","impact_score":5,"feasibility_score":5,"required_resources":["Internet","Creativity"],"next_step":"Add your WATSONX_API_KEY to .env","market_timing":"now"}]\n```'


# ── prompt builders ───────────────────────────────────────────────────────────
def build_idea_prompt(
    system_prompt: str,
    user_input: str,
    context: str = "",
    image_desc: str = "",
    voice_text: str = "",
    n_ideas: int = 5,
) -> str:
    parts = [system_prompt, "\n---\n"]

    if context:
        parts.append(f"BACKGROUND CONTEXT PROVIDED BY USER:\n{context}\n")
    if image_desc:
        parts.append(f"IMAGE/SKETCH DESCRIPTION:\n{image_desc}\n")
    if voice_text:
        parts.append(f"VOICE NOTE TRANSCRIPT:\n{voice_text}\n")

    parts.append(
        f"USER REQUEST:\n{user_input}\n\n"
        f"Generate exactly {n_ideas} distinct, high-quality business ideas in the required JSON array format."
    )
    return "\n".join(parts)


def build_followup_prompt(
    system_prompt: str,
    history: list,
    user_message: str,
    ideas_context: str = "",
) -> str:
    history_text = ""
    for turn in history[-6:]:  # last 6 turns for context window
        role = turn.get("role", "user")
        content = turn.get("content", "")
        history_text += f"{role.capitalize()}: {content}\n"

    ideas_section = f"\nCURRENT IDEAS IN SESSION:\n{ideas_context}\n" if ideas_context else ""

    return (
        f"{system_prompt}\n---\n"
        f"{ideas_section}"
        f"CONVERSATION SO FAR:\n{history_text}"
        f"User: {user_message}\n"
        f"Assistant:"
    )


def parse_ideas_from_response(text: str) -> list:
    """Extract JSON array of ideas from model output."""
    match = re.search(r"```json\s*(\[.*?\])\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    # fallback: try bare array
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    return []
