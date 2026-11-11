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
