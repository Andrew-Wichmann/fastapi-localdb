#!/usr/bin/env python3
"""Dev tooling CLI for the margin calculator project.

Install deps:  pip install -r requirements-dev.txt
Usage:         python dev.py --help
"""

import io
import subprocess
import urllib.request
import zipfile
from pathlib import Path

import typer

app = typer.Typer(help="Margin calculator dev tools.", no_args_is_help=True)

REMOTE_HOST = "74.208.55.55"
REMOTE_USER = "root"
REMOTE_DIR = "/opt/margin-calculator"
REMOTE_APP_URL = f"http://{REMOTE_HOST}:8000"
LOCAL_APP_URL = "http://localhost:8000"
PROJECT_ROOT = Path(__file__).parent


def _password() -> str:
    secrets = PROJECT_ROOT / ".secrets"
    if not secrets.exists():
        typer.echo("error: .secrets not found", err=True)
        raise typer.Exit(1)
    return secrets.read_text().strip()


def _ssh(cmd: str) -> None:
    subprocess.run(
        [
            "sshpass", "-p", _password(),
            "ssh", "-o", "StrictHostKeyChecking=no",
            f"{REMOTE_USER}@{REMOTE_HOST}", cmd,
        ],
        check=True,
    )


def _run(*cmd: str) -> None:
    subprocess.run(list(cmd), check=True)


@app.command()
def deploy():
    """Sync code to the remote server and restart the stack."""
    typer.echo("==> syncing files")
    subprocess.run(
        [
            "sshpass", "-p", _password(),
            "rsync", "-az", "--delete", "--progress",
            "-e", "ssh -o StrictHostKeyChecking=no",
            "--exclude=.venv/",
            "--exclude=__pycache__/",
            "--exclude=*.pyc",
            "--exclude=.git/",
            "--exclude=.claude/",
            "--exclude=.secrets",
            "--exclude=dbs/",
            "--exclude=scripts/",
            "--exclude=locustfile.py",
            str(PROJECT_ROOT) + "/",
            f"{REMOTE_USER}@{REMOTE_HOST}:{REMOTE_DIR}/",
        ],
        check=True,
    )

    typer.echo("==> restarting stack")
    _ssh(
        f"cd {REMOTE_DIR} && "
        "(docker compose down 2>/dev/null || docker-compose down 2>/dev/null || true) && "
        "(docker compose up --build -d || docker-compose up --build -d)"
    )

    typer.echo(f"app    → http://{REMOTE_HOST}:8000")
    typer.echo(f"jaeger → http://{REMOTE_HOST}:16686")


@app.command()
def pull(
    cob_date: str = typer.Argument(..., help="Partition date to download (YYYY-MM-DD)"),
    host: str = typer.Option(REMOTE_APP_URL, help="App host to pull from"),
):
    """Download a partition from the app for local debugging."""
    url = f"{host}/debug/partition/{cob_date}"
    typer.echo(f"==> downloading {cob_date} from {host}")

    with urllib.request.urlopen(url) as resp:
        data = resp.read()

    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        zf.extractall(PROJECT_ROOT)

    dest = PROJECT_ROOT / "dbs" / f"cob_date={cob_date}" / "sqlite.db"
    typer.echo(f"==> extracted to {dest}")


@app.command()
def restart(
    remote: bool = typer.Option(False, "--remote", help="Restart the remote stack"),
    clean: bool = typer.Option(False, "--clean", help="Remove volumes before restart (local only)"),
):
    """Restart the Docker stack locally or on the remote server."""
    if remote:
        typer.echo("==> restarting remote stack")
        _ssh(f"cd {REMOTE_DIR} && (docker compose restart || docker-compose restart)")
    else:
        typer.echo("==> restarting local stack")
        if clean:
            _run("docker", "compose", "down", "-v")
        else:
            _run("docker", "compose", "down")
        _run("docker", "compose", "up", "-d")


@app.command()
def locust(
    host: str = typer.Option(REMOTE_APP_URL, help="Target app host"),
):
    """Start Locust pointed at the given host."""
    typer.echo(f"locust UI  → http://localhost:8089")
    typer.echo(f"target app → {host}")
    _run("locust", "--host", host)


if __name__ == "__main__":
    app()
