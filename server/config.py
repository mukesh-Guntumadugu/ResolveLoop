"""Runtime configuration. Everything comes from environment variables with safe demo defaults."""
import os

DB_PATH = os.environ.get("RESOLVELOOP_DB", os.path.join(os.path.dirname(__file__), "..", "resolveloop.db"))
# Optional shared secret. When set, mutating endpoints (tools, resolve, approvals, reset) require X-API-Key.
API_KEY = os.environ.get("RESOLVELOOP_API_KEY", "")
DEFAULT_TENANT = os.environ.get("RESOLVELOOP_TENANT", "demo")
# Path prefix when served behind a reverse proxy, e.g. "/resolveloop".
ROOT_PATH = os.environ.get("RESOLVELOOP_ROOT_PATH", "")
# Optional Claude API key for LLM-assisted paraphrase suggestions in the extractor. Never required.
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
MATCH_THRESHOLD = float(os.environ.get("RESOLVELOOP_MATCH_THRESHOLD", "0.45"))
ABSTAIN_THRESHOLD = float(os.environ.get("RESOLVELOOP_ABSTAIN_THRESHOLD", "0.25"))
# Knowledge base root: manifest-<domain>.json files plus the markdown/PDF documents they point at.
KNOWLEDGE_DIR = os.environ.get("RESOLVELOOP_KNOWLEDGE_DIR", os.path.join(os.path.dirname(__file__), "..", "knowledge"))
# OpenAI-compatible chat-completions endpoint used for LLM-drafted playbooks (Ollama by default). Never required.
LLM_BASE_URL = os.environ.get("RESOLVELOOP_LLM_BASE_URL", "http://127.0.0.1:11434/v1").rstrip("/")
LLM_MODEL = os.environ.get("RESOLVELOOP_LLM_MODEL", "qwen3:8b")
LLM_API_KEY = os.environ.get("RESOLVELOOP_LLM_API_KEY", "")
LLM_TIMEOUT = float(os.environ.get("RESOLVELOOP_LLM_TIMEOUT", "120"))
# Confirmed successful supervised runs an LLM-drafted playbook needs before it is APPROVED.
SUPERVISED_RUNS = int(os.environ.get("RESOLVELOOP_SUPERVISED_RUNS", "3"))
# Salt for the synthetic per-account identity code a specialist must present before a high-risk action.
IDENTITY_SALT = os.environ.get("RESOLVELOOP_IDENTITY_SALT", "resolveloop-demo-identity")
