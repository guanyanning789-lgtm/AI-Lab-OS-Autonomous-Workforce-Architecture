from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request
from typing import Any

DEFAULT_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_PATH = "/task/windows/e2e"
SAFETY_TRUE = {"dry_run", "dryrun", "mock"}
SAFETY_FALSE = {"approved", "approve", "approval", "allow_real_actions"}


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
            target = target[part.replace("~1", "/").replace("~0", "~")]
        current = target
    return current


def request_schema(openapi: dict[str, Any], path: str) -> dict[str, Any]:
    operation = openapi.get("paths", {}).get(path, {}).get("post")
    if not isinstance(operation, dict):
        raise RuntimeError(f"POST {path} was not found in OpenAPI")
    body = resolve_ref(openapi, operation.get("requestBody", {}))
    content = body.get("content", {}) if isinstance(body, dict) else {}
    media = content.get("application/json", {})
    schema = resolve_ref(openapi, media.get("schema") if isinstance(media, dict) else None)
    if not isinstance(schema, dict):
        raise RuntimeError(f"POST {path} has no usable application/json request schema")
    return schema


def safe_scalar(name: str, schema: dict[str, Any]) -> Any:
    lowered = name.lower()
    if lowered in SAFETY_TRUE:
        return True
    if lowered in SAFETY_FALSE:
        return False
    if lowered in {"task_id", "id"}:
        return "v043-windows-e2e"
    if lowered in {"goal", "instruction", "task", "text", "description", "prompt"}:
        return "V0.4.3 harmless mock Windows E2E verification"
    if lowered in {"window_title", "title"}:
        return ""
    if "default" in schema:
        return schema["default"]
    enum = schema.get("enum")
    if isinstance(enum, list) and enum:
        # Prefer a no-op-ish enum when available.
        for candidate in ("noop", "none", "wait", "sleep", "mock"):
            if candidate in enum:
                return candidate
        return enum[0]
    kind = schema.get("type")
    if kind == "boolean": return False
    if kind in {"integer", "number"}: return 0
    return "V0.4.3 harmless mock step"


def build_object(openapi: dict[str, Any], raw_schema: Any) -> dict[str, Any]:
    schema = resolve_ref(openapi, raw_schema)
    if not isinstance(schema, dict):
        return {}
    properties = schema.get("properties", {})
    required = {str(x) for x in schema.get("required", []) if isinstance(x, str)}
    result: dict[str, Any] = {}
    if not isinstance(properties, dict):
        return result
    for name, raw_prop in properties.items():
        if not isinstance(name, str):
            continue
        prop = resolve_ref(openapi, raw_prop)
        if not isinstance(prop, dict):
            prop = {}
        lowered = name.lower()
        include = name in required or lowered in SAFETY_TRUE | SAFETY_FALSE | {
            "goal", "instruction", "task", "text", "description", "prompt", "task_id"
        }
        if not include:
            continue
        kind = prop.get("type")
        if kind == "array":
            minimum = int(prop.get("minItems", 0) or 0)
            items = prop.get("items", {})
            result[name] = [build_value(openapi, name, items) for _ in range(max(1, minimum))] if minimum else []
        elif kind == "object" or "properties" in prop:
            result[name] = build_object(openapi, prop)
        else:
            result[name] = safe_scalar(name, prop)
    return result


def build_value(openapi: dict[str, Any], name: str, raw_schema: Any) -> Any:
    schema = resolve_ref(openapi, raw_schema)
    if not isinstance(schema, dict):
        return "V0.4.3 harmless mock step"
    if schema.get("type") == "object" or "properties" in schema:
        return build_object(openapi, schema)
    if schema.get("type") == "array":
        minimum = int(schema.get("minItems", 0) or 0)
        return [build_value(openapi, name, schema.get("items", {})) for _ in range(max(1, minimum))] if minimum else []
    return safe_scalar(name, schema)


def build_payload(openapi: dict[str, Any], schema: dict[str, Any]) -> tuple[dict[str, Any], set[str]]:
    payload = build_object(openapi, schema)
    safety = {name.lower() for name in payload if name.lower() in SAFETY_TRUE | SAFETY_FALSE}
    return payload, safety


def post_json(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    request = urllib.request.Request(url, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"), headers={"Content-Type": "application/json; charset=utf-8"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            raw = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')}") from exc
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise RuntimeError("Windows E2E response must be a JSON object")
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description="Schema-aware safe Windows E2E runner for V0.4.3")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--path", default=DEFAULT_PATH)
    parser.add_argument("--send-dry-run", action="store_true")
    args = parser.parse_args()
    base = args.base_url.rstrip("/")
    print(f"OPENAPI = {base}/openapi.json")
    print(f"TARGET  = POST {args.path}")
    try:
        openapi = fetch_json(base + "/openapi.json")
        schema = request_schema(openapi, args.path)
        payload, safety = build_payload(openapi, schema)
    except Exception as exc:
        print("RESULT  = FAILED"); print(f"ERROR   = {exc}"); return 1
    print("PAYLOAD ="); print(json.dumps(payload, ensure_ascii=False, indent=2))
    if not args.send_dry_run:
        print(f"SAFETY  = {', '.join(sorted(safety)) or 'NONE'}")
        print("RESULT  = SCHEMA_READY")
        print("NEXT    = Re-run with --send-dry-run only when mock=true / allow_real_actions=false is visible.")
        return 0
    if not safety or not ({"mock", "dry_run", "dryrun"} & safety):
        print("RESULT  = REFUSED"); print("ERROR   = No explicit non-executing safety gate was found; request not sent."); return 2
    if payload.get("mock") is not True or payload.get("allow_real_actions") is True:
        print("RESULT  = REFUSED"); print("ERROR   = Safe Brain contract requires mock=true and allow_real_actions!=true."); return 2
    print(f"SAFETY  = {', '.join(sorted(safety))}")
    try:
        response = post_json(base + args.path, payload)
    except Exception as exc:
        print("RESULT  = FAILED"); print(f"ERROR   = {exc}"); return 1
    print("RESPONSE="); print(json.dumps(response, ensure_ascii=False, indent=2))
    print("RESULT  = DONE")
    print("MESSAGE = Mock Windows E2E completed with real actions disabled.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
