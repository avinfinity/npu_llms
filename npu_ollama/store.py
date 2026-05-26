import json
import shutil
import subprocess
import zipfile
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List
from urllib.request import urlretrieve

from .paths import ensure_dirs, models_dir
from .registry import RegistryModel, find_model


MANIFEST = "npu-ollama-model.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def model_path(name: str) -> Path:
    return models_dir() / name


def installed_models() -> List[Dict[str, object]]:
    ensure_dirs()
    rows = []
    for path in sorted(models_dir().iterdir()):
        if not path.is_dir():
            continue
        manifest_path = path / MANIFEST
        if manifest_path.exists():
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
        else:
            data = {"name": path.name, "format": "openvino", "repo": "", "installed_at": ""}
        data["path"] = str(path)
        data["size"] = directory_size(path)
        rows.append(data)
    return rows


def directory_size(path: Path) -> int:
    total = 0
    for file_path in path.rglob("*"):
        if file_path.is_file():
            total += file_path.stat().st_size
    return total


def remove_model(name: str) -> Path:
    path = model_path(name)
    if not path.exists():
        raise FileNotFoundError(f"Model '{name}' is not installed")
    shutil.rmtree(path)
    return path


def pull_model(name: str) -> Path:
    ensure_dirs()
    model = find_model(name)
    target = model_path(model.name)
    if target.exists():
        return target

    tmp = target.with_suffix(".tmp")
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)

    try:
        if model.repo.startswith("https://huggingface.co/"):
            _download_hugging_face(model, tmp)
        elif _can_use_git(model.repo):
            subprocess.run(["git", "clone", "--depth", "1", model.repo, str(tmp)], check=True)
            git_dir = tmp / ".git"
            if git_dir.exists():
                shutil.rmtree(git_dir)
        else:
            _download_github_zip(model, tmp)
        _write_manifest(tmp, model)
        tmp.rename(target)
    except Exception:
        if tmp.exists():
            shutil.rmtree(tmp)
        raise
    return target


def _can_use_git(repo: str) -> bool:
    if not repo.startswith("https://github.com/"):
        return False
    return shutil.which("git") is not None


def _download_hugging_face(model: RegistryModel, target: Path) -> None:
    from huggingface_hub import snapshot_download

    repo_id = model.repo.removeprefix("https://huggingface.co/").strip("/")
    snapshot_download(
        repo_id=repo_id,
        local_dir=target,
        local_dir_use_symlinks=False,
        allow_patterns=[
            "*.json",
            "*.jinja",
            "*.txt",
            "*.model",
            "*.xml",
            "*.bin",
            "*.safetensors",
        ],
    )


def _download_github_zip(model: RegistryModel, target: Path) -> None:
    repo = model.repo.removesuffix(".git")
    if not repo.startswith("https://github.com/"):
        raise RuntimeError("Model repo requires git because it is not a GitHub HTTPS repo")
    archive = target.with_suffix(".zip")
    url = f"{repo}/archive/refs/heads/main.zip"
    try:
        urlretrieve(url, archive)
        with zipfile.ZipFile(archive) as zip_file:
            members = zip_file.namelist()
            root = members[0].split("/")[0] + "/"
            zip_file.extractall(target)
        extracted = target / root.rstrip("/")
        for child in extracted.iterdir():
            shutil.move(str(child), target / child.name)
        shutil.rmtree(extracted)
    finally:
        if archive.exists():
            archive.unlink()


def _write_manifest(path: Path, model: RegistryModel) -> None:
    data = asdict(model)
    data["installed_at"] = _now()
    (path / MANIFEST).write_text(json.dumps(data, indent=2), encoding="utf-8")
