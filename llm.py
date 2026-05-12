from __future__ import annotations
import json
import os
import pathlib
import subprocess
import sys
import tempfile

BASE_PATH = pathlib.Path(__file__).parent
REQUEST_PATH = BASE_PATH / "request.txt"
RESPONSE_PATH = BASE_PATH / "response.txt"

LMS_HOSTS = ["http://localhost:1234", "http://192.168.16.31:1234"]

PROMPTS_DIR = BASE_PATH / "prompts"


def load_schema(role: str) -> dict:
    """Load JSON schema from prompts/ directory. Schemas are evolvable by self-improvement."""
    name_map = {"actor": "actor_schema.json", "planner": "planner_schema.json", "reflect": "reflect_schema.json"}
    path = PROMPTS_DIR / name_map[role]
    return json.loads(path.read_text(encoding="utf-8"))


def find_lms_host() -> str:
    for host in LMS_HOSTS:
        result = subprocess.run(
            ["curl.exe", "-s", "--max-time", "3", f"{host}/v1/models"],
            capture_output=True, timeout=50,
        )
        if result.returncode == 0 and result.stdout.strip():
            return host
    assert False, "no LM Studio host reachable"


def get_model(host: str) -> str:
    result = subprocess.run(["curl.exe", "-s", f"{host}/v1/models"], capture_output=True, timeout=100)
    return json.loads(result.stdout)["data"][0]["id"]


def call_lmstudio(system: str, user: str, schema: dict) -> str:
    host = find_lms_host()
    model = get_model(host)
    body = {
        "model": model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "response_format": schema,
        "temperature": 0.4,
        "top_p": 0.95,
        "max_tokens": 4000,
        "stream": False,
    }
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8")
    tmp.write(json.dumps(body))
    tmp.close()
    proc = subprocess.run(
        ["curl.exe", "-sN", "-X", "POST", f"{host}/v1/chat/completions",
         "-H", "Content-Type: application/json", "-d", f"@{tmp.name}", "--max-time", "9000"],
        capture_output=True, timeout=10000,
    )
    os.unlink(tmp.name)
    assert proc.returncode == 0, f"curl failed: {proc.stderr}"
    raw = proc.stdout.decode("utf-8")
    assert raw.strip(), "empty LLM response"
    return json.loads(raw)["choices"][0]["message"]["content"]


def call_acp(system: str, user: str) -> str:
    from acp_client import prompt_once
    text = system + "\n\n---\n\n" + user
    return prompt_once(text, timeout=120.0)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    backend = sys.argv[1] if len(sys.argv) > 1 else "lmstudio"
    role = sys.argv[2] if len(sys.argv) > 2 else "actor"
    request_text = REQUEST_PATH.read_text(encoding="utf-8")
    parts = request_text.split("\n\nUSER:\n", 1)
    system = parts[0].removeprefix("SYSTEM:\n")
    user = parts[1]
    schema = load_schema(role)
    match backend:
        case "lmstudio":
            response = call_lmstudio(system, user, schema)
        case "acp":
            response = call_acp(system, user)
        case _:
            assert False, f"unknown backend: {backend}"
    RESPONSE_PATH.write_text(response, encoding="utf-8")
    sys.stdout.write(response)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
