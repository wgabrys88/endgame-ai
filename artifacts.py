from __future__ import annotations

from config import ZERO_INT, ONE_INT
import hashlib
import json
import re
from typing import Any, cast

from config import (
    ARTIFACTS_DIR, BASE_DIR, ARTIFACT_INLINE_CHAR_LIMIT,
    ARTIFACT_CHUNK_CHAR_LIMIT, ARTIFACT_SHA_PREFIX_LENGTH,
    ARTIFACT_PATH_PART_LIMIT,
)


def materialize(value: Any, agent_id: str, sequence: int, phase: str) -> Any:
    return _materialize(value, agent_id, sequence, phase, ())


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
    name = _artifact_name(sequence, phase, path, digest)
    target_dir = ARTIFACTS_DIR / _safe(agent_id) / name
    target_dir.mkdir(parents=True, exist_ok=True)
    files: list[str] = []
    part = ZERO_INT
    for start in range(ZERO_INT, len(text), ARTIFACT_CHUNK_CHAR_LIMIT):
        chunk = text[start:start + ARTIFACT_CHUNK_CHAR_LIMIT]
        file_path = target_dir / f"{part}.txt"
        file_path.write_text(chunk, encoding="utf-8")
        files.append(str(file_path.relative_to(BASE_DIR)))
        part += ONE_INT
    return {
        "artifact_ref": True,
        "kind": kind,
        "sha256": digest,
        "chars": len(text),
        "lines": text.count("\n") + ONE_INT if text else ZERO_INT,
        "files": files,
    }


def _artifact_name(sequence: int, phase: str, path: tuple[str, ...], digest: str) -> str:
    path_part = "-".join(p for p in path if p)
    if not path_part:
        path_part = "data"
    raw = f"{sequence}-{_safe(phase)}-{_safe(path_part)}-{digest[:ARTIFACT_SHA_PREFIX_LENGTH]}"
    return raw[:ARTIFACT_PATH_PART_LIMIT + ARTIFACT_SHA_PREFIX_LENGTH]


def _safe(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    if not cleaned:
        return "value"
    return cleaned[:ARTIFACT_PATH_PART_LIMIT]
