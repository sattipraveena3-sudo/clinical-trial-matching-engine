r"""Create or repair a deterministic local development environment.

Run from the project root with Python 3.11 or 3.12:

    py -3.12 scripts\setup_local.py        # Windows
    python3.12 scripts/setup_local.py       # macOS/Linux

The script always invokes pip through the target virtual environment, so an
unrelated global ``pip`` executable cannot accidentally receive packages.
"""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VENV_DIR = PROJECT_ROOT / ".venv"
PYPI_INDEX = "https://pypi.org/simple"
PYTORCH_CPU_INDEX = "https://download.pytorch.org/whl/cpu"


def target_python(venv_dir: Path = VENV_DIR) -> Path:
    if os.name == "nt":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def run(command: list[str | Path], dry_run: bool = False) -> None:
    rendered = [str(part) for part in command]
    print("$", subprocess.list2cmdline(rendered))
    if not dry_run:
        subprocess.run(rendered, cwd=PROJECT_ROOT, check=True)


def ensure_supported_python() -> None:
    if sys.version_info < (3, 11) or sys.version_info >= (3, 13):
        raise SystemExit(
            "Python 3.11 or 3.12 is required. "
            f"Detected {platform.python_version()}."
        )
    if platform.architecture()[0] != "64bit":
        raise SystemExit("A 64-bit Python installation is required.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create or repair the Clinical Trial Matching Engine environment"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the commands without installing packages",
    )
    args = parser.parse_args()

    ensure_supported_python()
    python = target_python()

    if not python.exists():
        run([sys.executable, "-m", "venv", VENV_DIR], args.dry_run)

    # During a dry run the environment may not exist yet. Use the expected path
    # so the printed commands remain identical to a real installation.
    python_command = str(python)
    run(
        [python_command, "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"],
        args.dry_run,
    )

    if sys.platform == "darwin":
        torch_requirement = "torch==2.7.1"
        torch_index = PYPI_INDEX
    else:
        torch_requirement = "torch==2.7.1+cpu"
        torch_index = PYTORCH_CPU_INDEX

    run(
        [
            python_command,
            "-m",
            "pip",
            "install",
            "--upgrade",
            "--index-url",
            torch_index,
            torch_requirement,
        ],
        args.dry_run,
    )

    # Install the binary wheel that failed in the original Windows setup before
    # resolving the remaining dependency graph.
    run(
        [
            python_command,
            "-m",
            "pip",
            "install",
            "--upgrade",
            "--only-binary=:all:",
            "--index-url",
            PYPI_INDEX,
            "pydantic-core==2.27.2",
        ],
        args.dry_run,
    )
    run(
        [
            python_command,
            "-m",
            "pip",
            "install",
            "--upgrade",
            "--index-url",
            PYPI_INDEX,
            "-r",
            PROJECT_ROOT / "requirements.txt",
        ],
        args.dry_run,
    )

    env_path = PROJECT_ROOT / ".env"
    if not env_path.exists() and not args.dry_run:
        shutil.copyfile(PROJECT_ROOT / ".env.example", env_path)
        print("Created .env from .env.example")

    validation = (
        "import chromadb, fastapi, pydantic, pydantic_settings, "
        "sentence_transformers, torch, uvicorn; "
        "print('Environment ready'); "
        "print('Python:', __import__('sys').version.split()[0]); "
        "print('Torch:', torch.__version__, 'CPU build:', not torch.cuda.is_available())"
    )
    run([python_command, "-c", validation], args.dry_run)
    run([python_command, "-m", "pip", "check"], args.dry_run)

    if args.dry_run:
        return

    if os.name == "nt":
        refresh = r".venv\Scripts\python.exe scripts\refresh_trials.py --max-studies 50"
        serve = r".venv\Scripts\python.exe -m uvicorn app.main:app --reload"
    else:
        refresh = ".venv/bin/python scripts/refresh_trials.py --max-studies 50"
        serve = ".venv/bin/python -m uvicorn app.main:app --reload"

    print("\nSetup completed. Run these as two separate commands:\n")
    print(refresh)
    print(serve)


if __name__ == "__main__":
    main()
