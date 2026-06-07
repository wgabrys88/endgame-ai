from __future__ import annotations

from config import ZERO_INT, ONE_INT
import hashlib
import json
import re
from typing import Any, cast

from config import (
    ARTIFACTS_DIR, BASE_DIR, ARTIFACT_INLINE_CHAR_LIMIT,
    ARTIFACT_CHUNK_CHAR_LIMIT, ARTIFACT_SHA_PREFIX_LENGTH,
    ARTIFACT_PATH_PART_LIMIT, MAX_RUNTIME_ARTIFACT_ENTRIES,
)


def materialize(value: Any, agent_id: str, sequence: int, phase: str) -> Any:
    return _materialize(value, agent_id, sequence, phase, ())


def materialize_text(text: str, agent_id: str, sequence: int, phase: str, path: tuple[str, ...]) -> dict[str, Any]:
    return _write_text(text, "text", agent_id, sequence, phase, path)


def _materialize(value: Any, agent_id: str, sequence: int, phase: str, path: tuple[str, ...]) -> Any:
    if isinstance(value, str):
        if len(value) > ARTIFACT_INLINE_CHAR_LIMIT:
            return _write_text(value, "text", agent_id, sequence, phase, path)
        return value
    if isinstance(value, dict):
        dict_value = cast(dict[str, Any], value)
        mapped = {k: _materialize(v, agent_id, sequence, phase, path + (_safe(k),)) for k, v in dict_value.items()}
        text = json.dumps(mapped, ensure_ascii=False, separators=(",", ":"))
        if len(text) > ARTIFACT_INLINE_CHAR_LIMIT:
            return _write_text(text, "json", agent_id, sequence, phase, path)
        return mapped
    if isinstance(value, list):
        list_value = cast(list[Any], value)
        mapped_list = [_materialize(v, agent_id, sequence, phase, path + (str(i),)) for i, v in enumerate(list_value)]
        text = json.dumps(mapped_list, ensure_ascii=False, separators=(",", ":"))
        if len(text) > ARTIFACT_INLINE_CHAR_LIMIT:
            return _write_text(text, "json", agent_id, sequence, phase, path)
        return mapped_list
    return value


def _write_text(text: str, kind: str, agent_id: str, sequence: int, phase: str, path: tuple[str, ...]) -> dict[str, Any]:
    digest = hashlib.sha256(text.encode("utf-8", errors="surrogatepass")).hexdigest()
    target_dir = ARTIFACTS_DIR / _safe(agent_id) / digest[:ARTIFACT_SHA_PREFIX_LENGTH]
    files: list[str] = []
    part = ZERO_INT
    for start in range(ZERO_INT, len(text), ARTIFACT_CHUNK_CHAR_LIMIT):
        chunk = text[start:start + ARTIFACT_CHUNK_CHAR_LIMIT]
        file_path = target_dir / f"{part}.txt"
        if not file_path.exists():
            target_dir.mkdir(parents=True, exist_ok=True)
            file_path.write_text(chunk, encoding="utf-8")
        files.append(str(file_path.relative_to(BASE_DIR)))
        part += ONE_INT
    _prune_agent_artifacts(agent_id)
    return {
        "artifact_ref": True,
        "kind": kind,
        "sha256": digest,
        "chars": len(text),
        "lines": text.count("\n") + ONE_INT if text else ZERO_INT,
        "files": files,
    }


def _prune_agent_artifacts(agent_id: str) -> None:
    agent_dir = ARTIFACTS_DIR / _safe(agent_id)
    if not agent_dir.exists():
        return
    entries = [p for p in agent_dir.iterdir() if p.is_dir()]
    if len(entries) <= MAX_RUNTIME_ARTIFACT_ENTRIES:
        return
    entries.sort(key=lambda p: p.stat().st_mtime)
    for entry in entries[:len(entries) - MAX_RUNTIME_ARTIFACT_ENTRIES]:
        for child in entry.iterdir():
            child.unlink(missing_ok=True)
        entry.rmdir()


def _safe(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    if not cleaned:
        return "value"
    return cleaned[:ARTIFACT_PATH_PART_LIMIT]