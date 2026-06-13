import json
import os
import re
from dataclasses import dataclass
from importlib import resources
from typing import Iterable, List, Optional
from urllib.request import urlopen


DEFAULT_REGISTRY_URL = (
    "https://raw.githubusercontent.com/npu/models/main/registry.json"
)
DEFAULT_HF_COLLECTION = "llmware/npu-openvino"


@dataclass(frozen=True)
class RegistryModel:
    name: str
    repo: str
    description: str = ""
    family: str = "llm"
    npu: str = "intel"
    size: str = "unknown"
    format: str = "openvino"


def _bundled_registry() -> List[dict]:
    text = resources.files("npu.data").joinpath("registry.json").read_text(encoding="utf-8")
    return json.loads(text)["models"]


def _remote_registry() -> Optional[List[dict]]:
    url = os.getenv("NPU_REGISTRY_URL", DEFAULT_REGISTRY_URL)
    try:
        with urlopen(url, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))["models"]
    except Exception:
        return None


def _collection_registry() -> Optional[List[dict]]:
    collection_slug = os.getenv("NPU_HF_COLLECTION", DEFAULT_HF_COLLECTION)
    try:
        from huggingface_hub import HfApi

        collection = HfApi().get_collection(collection_slug, token=False)
    except Exception:
        return None

    rows = []
    for item in collection.items:
        item_type = getattr(item, "item_type", "")
        item_id = getattr(item, "item_id", "")
        if item_type != "model" or not item_id:
            continue
        rows.append(_registry_record_from_repo_id(item_id))
    return rows


def _registry_record_from_repo_id(repo_id: str) -> dict:
    repo_name = repo_id.split("/")[-1]
    return {
        "name": repo_name,
        "repo": f"https://huggingface.co/{repo_id}",
        "description": f"{repo_id} from the llmware NPU OpenVINO collection.",
        "family": _infer_family(repo_name),
        "npu": "intel",
        "size": _infer_size(repo_name),
        "format": "openvino",
    }


def _infer_family(name: str) -> str:
    lowered = name.lower()
    for family in ("llama", "phi", "mistral", "qwen", "yi", "bling", "slim"):
        if family in lowered:
            return family
    return "llm"


def _infer_size(name: str) -> str:
    match = re.search(r"(\d+(?:\.\d+)?b)", name, flags=re.IGNORECASE)
    if match:
        return match.group(1).upper()
    if "tiny" in name.lower():
        return "tiny"
    return "unknown"


def load_registry(allow_remote: bool = True) -> List[RegistryModel]:
    records = None
    if allow_remote:
        records = _collection_registry()
        if not records:
            records = _remote_registry()
    if not records:
        records = _bundled_registry()
    return [RegistryModel(**record) for record in records]


def find_model(name: str, allow_remote: bool = True) -> RegistryModel:
    normalized = name.lower()
    for model in load_registry(allow_remote=allow_remote):
        repo_id = model.repo.removeprefix("https://huggingface.co/").removesuffix(".git")
        if model.name.lower() == normalized or repo_id.lower() == normalized:
            return model
    available = ", ".join(model.name for model in load_registry(allow_remote=False))
    raise ValueError(f"Unknown model '{name}'. Bundled models: {available}")


def model_rows(models: Iterable[RegistryModel]) -> List[dict]:
    return [model.__dict__.copy() for model in models]
