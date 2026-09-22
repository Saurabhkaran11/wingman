"""Environment and path configuration for Wingman.

Import this module BEFORE importing cognee: it sets the env vars Cognee reads
at import time (log level and where local databases live).
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Project root = two levels above src/wingman/.
ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

# A blank line in .env ("AWS_ACCESS_KEY_ID=") becomes an empty env var, which
# boto3 and Cognee read as "configured but wrong". Remove blanks so their own
# fallbacks (AWS profile, defaults) still work.
# Example: AWS_SESSION_TOKEN="" -> variable removed from os.environ.
for _key in [k for k, v in os.environ.items() if v == ""]:
    del os.environ[_key]

OUT_DIR = ROOT / "out"
OUT_DIR.mkdir(exist_ok=True)

# Keep Cognee quiet so the demo terminal shows only Wingman's own narration.
os.environ.setdefault("LOG_LEVEL", "ERROR")
# In local (non-cloud) mode, keep Cognee's databases inside the project
# instead of inside site-packages, so `rm -rf .cognee_system` resets the brain.
os.environ.setdefault("SYSTEM_ROOT_DIRECTORY", str(ROOT / ".cognee_system"))
os.environ.setdefault("DATA_ROOT_DIRECTORY", str(ROOT / ".data_storage"))


def env(name: str, default: str = "") -> str:
    # Treat empty strings in .env the same as "not set".
    # Example: env("AWS_REGION", "us-west-2") -> "us-west-2" when the line is blank.
    return os.environ.get(name, "").strip() or default


# All Cognee data for this project lives in one named dataset.
DATASET = env("WINGMAN_DATASET", "wingman")

# Who "me" is. Used to tell my side of a thread from theirs, and it is the
# only address Wingman is allowed to send email to.
ME_EMAIL = env("WINGMAN_ME", "alex@example.com")
ME_NAME = env("WINGMAN_ME_NAME", "Alex Rivera")

COGNEE_CLOUD_URL = env("COGNEE_CLOUD_URL")
COGNEE_API_KEY = env("COGNEE_API_KEY")

# Bright Data: the MCP server reads API_TOKEN from the environment.
BRIGHT_DATA_TOKEN = env("API_TOKEN")

# Model provider: "bedrock" (Strands default) or "anthropic".
# Example: with only ANTHROPIC_API_KEY set, provider resolves to "anthropic".
ANTHROPIC_API_KEY = env("ANTHROPIC_API_KEY")
MODEL_PROVIDER = env("WINGMAN_MODEL_PROVIDER", "anthropic" if ANTHROPIC_API_KEY else "bedrock")
MODEL_ID = env("WINGMAN_MODEL_ID")  # blank = provider default

SMTP_USER = env("SMTP_USER")
SMTP_APP_PASSWORD = env("SMTP_APP_PASSWORD")
SMTP_HOST = env("SMTP_HOST", "smtp.gmail.com")


def show(path: Path) -> str:
    """Path for printing: relative to the project when inside it, absolute otherwise.

    Example: show(ROOT / "out/x.pdf") -> "out/x.pdf";  show(Path("/tmp/x.pdf")) -> "/tmp/x.pdf"
    """
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)
