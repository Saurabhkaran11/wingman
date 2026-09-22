"""Run rendering code inside a throwaway, locked-down Docker container.

The dossier is built from LLM output and scraped web text, and the render
script may itself be edited by the agent. None of that should be able to touch
the host or the network, so it runs in a container with:
  - no network
  - a read-only root filesystem
  - no Linux capabilities
  - capped memory, CPU and process count
  - exactly one mounted directory (a per-run staging folder)
"""

import json
import shutil
import subprocess
import uuid
from pathlib import Path

from wingman import config

IMAGE = "wingman-sandbox"
TEMPLATE = config.ROOT / "sandbox" / "render_template.py"
# Stage under the project (inside /Users), which Docker Desktop always shares.
STAGING = config.OUT_DIR / ".sandbox"


class SandboxError(RuntimeError):
    pass


def ensure_image() -> None:
    # Build the image on first use so `wingman brief` works on a fresh clone.
    # Example: first run prints "building sandbox image..." once, later runs skip it.
    found = subprocess.run(["docker", "image", "inspect", IMAGE], capture_output=True)
    if found.returncode != 0:
        print("building sandbox image (first run only)...")
        subprocess.run(["docker", "build", "-q", "-t", IMAGE, str(config.ROOT / "sandbox")], check=True)


def run_in_sandbox(dossier: dict, script: str | None = None, timeout_s: int = 90) -> Path:
    """Render `dossier` to a PDF inside the sandbox and return the PDF path.

    Args:
        dossier: a Dossier as a plain dict (Dossier.model_dump()).
        script:  Python source to run. Defaults to the known-good template.

    Example:
        run_in_sandbox({"person": "Priya Shah", ...})
        -> PosixPath(".../out/.sandbox/3f9a1c/out/dossier.pdf")
    """
    ensure_image()
    work = STAGING / uuid.uuid4().hex[:6]
    (work / "out").mkdir(parents=True)
    (work / "main.py").write_text(script or TEMPLATE.read_text())
    (work / "dossier.json").write_text(json.dumps(dossier))
    # The container runs as a non-root user, so the output dir must be writable by "other".
    (work / "out").chmod(0o777)

    cmd = [
        "docker", "run", "--rm",
        "--network", "none",                     # generated code cannot call out
        "--read-only",                           # root filesystem is immutable
        "--tmpfs", "/tmp",                       # scratch space for matplotlib's cache
        "--cap-drop", "ALL",                     # no Linux capabilities
        "--security-opt", "no-new-privileges",
        "--memory", "512m", "--cpus", "1", "--pids-limit", "128",
        "-v", f"{work}:/work",                   # the ONLY host path the code can see
        IMAGE, "python", "/work/main.py",
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s)
    except subprocess.TimeoutExpired as exc:
        raise SandboxError(f"sandbox timed out after {timeout_s}s") from exc
    if proc.returncode != 0:
        raise SandboxError(proc.stderr.strip()[-800:])

    pdf = work / "out" / "dossier.pdf"
    if not pdf.exists():
        raise SandboxError("script finished but did not write out/dossier.pdf")
    return pdf


def collect(pdf: Path, dest: Path) -> Path:
    """Copy the rendered PDF out of staging and delete the staging folder."""
    shutil.copy(pdf, dest)
    shutil.rmtree(pdf.parents[1], ignore_errors=True)
    return dest
