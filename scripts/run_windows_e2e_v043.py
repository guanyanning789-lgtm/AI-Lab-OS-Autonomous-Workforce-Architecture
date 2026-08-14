from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request
from typing import Any

DEFAULT_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_PATH = "/task/windows/e2e"
# Source of truth recovered from the local Brain implementation:
# allowed_actions = {"click", "type", "hotkey"}
KNOWN_BRAIN_ACTIONS = ("click", "type", "hotkey")
SAFE_MOCK_ACTION = "click"


def fetch_json(url: str) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=15) as response:
        data = json.loads(response.read().decode("utf-8"))
    if not isinstance(data, dict):
        raise RuntimeError(f"Expected JSON object from {url}")
    return data


def resolve_ref(document: dict[str, Any], node: Any) -> Any:
    seen: set[str] = set()
    current = node
    while isinstance(current, dict) and "$ref" in current:
        ref = current["$ref"]
        if not isinstance(ref, str) or not ref.startswith("#/"):
            raise RuntimeError(f"Unsupported schema ref: {ref!r}")
        if ref in seen:
            raise RuntimeError(f"Circular schema ref: {ref}")
        seen.add(ref)
        target: Any = document
        for part in ref[2:].split("/"):
            part = part.replace("~1", "/").replace("~0", "~")
            target = target[part]
        current = target
    return current


def request_schema(openapi: dict[str, Any], path: str) -> dict[str, Any]:
    operation = openapi.get("paths", {}).get(path, {}).get("post")
    if not isinstance(operation, dict):
        raise RuntimeError(f"POST {path} was not found in OpenAPI")
    body = resolve_ref(openapi, operation.get("requestBody", {}))
    content = body.get("content", {}) if isinstance(body, dict) else {}
    media = content.get("application/json", {}) if isinstance(content, dict) else {}
    schema = resolve_ref(openapi, media.get("schema"))
    if not isinstance(schema, dict):
        raise RuntimeError(f"POST {path} has no object request schema")
    return schema


def first_schema_choice(schema: dict[str, Any]) -> Any:
    if "const" in schema:
        return schema["const"]
    enum = schema.get("enum")
    if isinstance(enum, list) and enum:
        return enum[0]
    examples = schema.get("examples")
    if isinstance(examples, list) and examples:
        return examples[0]
    if "example" in schema:
        return schema["example"]
    if "default" in schema:
        return schema["default"]
    return None


def safe_scalar(name: str, schema: dict[str, Any]) -> Any:
    choice = first_schema_choice(schema)
    if choice is not None:
        return choice
    lowered = name.lower()
    if lowered in {"task_id", "id"}:
        return "v043-windows-e2e"
    if lowered in {"step_id", "index", "sequence"}:
        return 1
    if lowered in {"action", "action_type"}:
        # OpenAPI does not publish the action enum. The local Brain source does:
        # click / type / hotkey. Use click only in mock mode; real actions remain disabled.
        return SAFE_MOCK_ACTION
    if lowered in {"kind", "type"}:
        choice = first_schema_choice(schema)
        if choice is not None:
            return choice
        raise RuntimeError(f"No safe schema value for discriminator {name!r}")
    if lowered in {"text", "value", "content", "instruction", "description", "goal"}:
        return "V0.4.3 mock-only E2E"
    if lowered in {"x", "y", "duration", "delay_ms", "timeout_ms", "retries"}:
        return 0
    kind = schema.get("type")
    if kind == "boolean":
        return False
    if kind == "integer":
        return 0
    if kind == "number":
        return 0
    if kind == "string":
        return "V0.4.3 mock-only E2E"
    return None


def build_object(openapi: dict[str, Any], schema: dict[str, Any], *, context: str) -> dict[str, Any]:
    schema = resolve_ref(openapi, schema)
    if not isinstance(schema, dict):
        raise RuntimeError(f"{context} schema is not an object")
    properties = schema.get("properties", {})
    if not isinstance(properties, dict):
        properties = {}
    required_raw = schema.get("required", [])
    required = {str(item) for item in required_raw} if isinstance(required_raw, list) else set()

    result: dict[str, Any] = {}
    for name, raw in properties.items():
        if not isinstance(name, str):
            continue
        prop = resolve_ref(openapi, raw)
        if not isinstance(prop, dict):
            prop = {}
        lowered = name.lower()

        if context == "request" and lowered == "mock":
            result[name] = True
            continue
        if context == "request" and lowered == "allow_real_actions":
            result[name] = False
            continue

        include = name in required
        if context == "step" and lowered in {"action", "action_type", "kind", "type"}:
            include = True
        if not include:
            continue

        kind = prop.get("type")
        if kind == "object" or "properties" in prop:
            result[name] = build_object(openapi, prop, context=f"{context}.{name}")
        elif kind == "array":
            item_schema = resolve_ref(openapi, prop.get("items", {}))
            if name == "steps":
                if not isinstance(item_schema, dict):
                    raise RuntimeError("steps item schema is missing")
                result[name] = [build_object(openapi, item_schema, context="step")]
            else:
                result[name] = []
        else:
            value = safe_scalar(name, prop)
            if value is None and name in required:
                raise RuntimeError(f"Cannot safely synthesize required field {context}.{name}")
            if value is not None:
                result[name] = value
    return result


def build_payload(openapi: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
    payload = build_object(openapi, schema, context="request")
    if "task_id" not in payload:
        payload["task_id"] = "v043-windows-e2e"
    if "mock" in schema.get("properties", {}):
        payload["mock"] = True
    if "allow_real_actions" in schema.get("properties", {}):
        payload["allow_real_actions"] = False
    return payload


def assert_safe_payload(payload: dict[str, Any]) -> None:
    if payload.get("mock") is not True:
        raise RuntimeError("Safety refusal: payload must contain mock=true")
    if payload.get("allow_real_actions") is not False:
        raise RuntimeError("Safety refusal: payload must contain allow_real_actions=false")
    steps = payload.get("steps")
    if not isinstance(steps, list) or not steps:
        raise RuntimeError("Safety/semantic refusal: no valid Windows E2E step could be generated")
    for step in steps:
        if not isinstance(step, dict):
            raise RuntimeError("Safety/semantic refusal: invalid step object")
        action = str(step.get("action", ""))
        if action not in KNOWN_BRAIN_ACTIONS:
            raise RuntimeError(f"Safety refusal: action {action!r} is not in Brain's verified allowlist")


def post_json(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            raw = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise RuntimeError("Windows E2E response must be a JSON object")
    return data


def response_passed(response: dict[str, Any]) -> tuple[bool, str]:
    errors = response.get("errors")
    if isinstance(errors, list) and errors:
        return False, ", ".join(str(item) for item in errors)
    status = str(response.get("status", "")).strip().lower()
    if status in {"rejected", "failed", "error", "blocked"}:
        return False, status
    ok = response.get("ok")
    if ok is False:
        return False, str(response.get("message") or response.get("detail") or "ok=false")
    if ok is True or status in {"success", "complete", "completed", "passed", "mock_complete"}:
        return True, status or "ok=true"
    return False, f"unrecognized response status: {status or 'missing'}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Schema-aware safe Windows E2E runner for V0.4.3")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--path", default=DEFAULT_PATH)
    parser.add_argument("--send-dry-run", action="store_true")
    args = parser.parse_args()

    base = args.base_url.rstrip("/")
    openapi_url = base + "/openapi.json"
    print(f"OPENAPI = {openapi_url}")
    print(f"TARGET  = POST {args.path}")
    print(f"ALLOWLIST = {', '.join(KNOWN_BRAIN_ACTIONS)}")

    try:
        openapi = fetch_json(openapi_url)
        schema = request_schema(openapi, args.path)
        payload = build_payload(openapi, schema)
        assert_safe_payload(payload)
    except Exception as exc:
        print("RESULT  = FAILED")
        print(f"ERROR   = {exc}")
        return 1

    print("PAYLOAD =")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    print("SAFETY  = mock=true, allow_real_actions=false")

    if not args.send_dry_run:
        print("RESULT  = SCHEMA_READY")
        print("NEXT    = Re-run with --send-dry-run; the selected action is from Brain's verified allowlist.")
        return 0

    try:
        response = post_json(base + args.path, payload)
    except Exception as exc:
        print("RESULT  = FAILED")
        print(f"ERROR   = {exc}")
        return 1

    print("RESPONSE=")
    print(json.dumps(response, ensure_ascii=False, indent=2))
    passed, reason = response_passed(response)
    if not passed:
        print("RESULT  = FAILED")
        print(f"ERROR   = Brain rejected or failed the mock Windows E2E: {reason}")
        return 2

    print("RESULT  = DONE")
    print("MESSAGE = Brain accepted a verified legal Windows action in mock mode; real actions remained disabled.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
