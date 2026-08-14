from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from typing import Any


DEFAULT_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_PATH = "/task/windows/e2e"


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
    paths = openapi.get("paths", {})
    operation = paths.get(path, {}).get("post")
    if not isinstance(operation, dict):
        raise RuntimeError(f"POST {path} was not found in OpenAPI")
    request_body = operation.get("requestBody", {})
    request_body = resolve_ref(openapi, request_body)
    content = request_body.get("content", {}) if isinstance(request_body, dict) else {}
    media = content.get("application/json", {})
    schema = media.get("schema") if isinstance(media, dict) else None
    if schema is None:
        raise RuntimeError(f"POST {path} has no application/json request schema")
    schema = resolve_ref(openapi, schema)
    if not isinstance(schema, dict):
        raise RuntimeError("Request schema is not an object")
    return schema


def schema_property(openapi: dict[str, Any], prop: Any) -> dict[str, Any]:
    resolved = resolve_ref(openapi, prop)
    return resolved if isinstance(resolved, dict) else {}


def safe_value(name: str, schema: dict[str, Any]) -> Any:
    lowered = name.lower()
    if lowered in {"dry_run", "dryrun"}:
        return True
    if lowered in {"approved", "approve", "approval"}:
        return False
    if lowered in {"goal", "instruction", "task", "text", "description", "prompt"}:
        return "V0.4.3 safe Windows E2E dry-run: validate execution path without changing the desktop."
    if lowered in {"task_id", "id"}:
        return "v043-windows-e2e"
    if lowered in {"window_title", "title"}:
        return ""

    if "default" in schema:
        return schema["default"]
    enum = schema.get("enum")
    if isinstance(enum, list) and enum:
        return enum[0]

    kind = schema.get("type")
    if kind == "boolean":
        return False
    if kind == "integer":
        return 0
    if kind == "number":
        return 0
    if kind == "array":
        return []
    if kind == "object":
        return {}
    return "V0.4.3 safe dry-run"


def build_payload(openapi: dict[str, Any], schema: dict[str, Any]) -> tuple[dict[str, Any], set[str]]:
    properties = schema.get("properties", {})
    if not isinstance(properties, dict):
        properties = {}
    required = schema.get("required", [])
    required_names = {str(item) for item in required} if isinstance(required, list) else set()

    payload: dict[str, Any] = {}
    safety_fields: set[str] = set()
    for name, raw_prop in properties.items():
        if not isinstance(name, str):
            continue
        prop = schema_property(openapi, raw_prop)
        lowered = name.lower()
        if lowered in {"dry_run", "dryrun", "approved", "approve", "approval"}:
            safety_fields.add(lowered)
        if name in required_names or lowered in {
            "dry_run", "dryrun", "approved", "approve", "approval",
            "goal", "instruction", "task", "text", "description", "prompt", "task_id"
        }:
            payload[name] = safe_value(name, prop)
    return payload, safety_fields


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


def main() -> int:
    parser = argparse.ArgumentParser(description="Schema-aware safe Windows E2E runner for V0.4.3")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--path", default=DEFAULT_PATH)
    parser.add_argument("--send-dry-run", action="store_true", help="POST only if an explicit safety gate exists")
    args = parser.parse_args()

    base = args.base_url.rstrip("/")
    openapi_url = base + "/openapi.json"
    print(f"OPENAPI = {openapi_url}")
    print(f"TARGET  = POST {args.path}")

    try:
        openapi = fetch_json(openapi_url)
        schema = request_schema(openapi, args.path)
        payload, safety_fields = build_payload(openapi, schema)
    except Exception as exc:
        print("RESULT  = FAILED")
        print(f"ERROR   = {exc}")
        return 1

    print("SCHEMA  =")
    print(json.dumps(schema, ensure_ascii=False, indent=2))
    print("PAYLOAD =")
    print(json.dumps(payload, ensure_ascii=False, indent=2))

    if not args.send_dry_run:
        print("RESULT  = SCHEMA_READY")
        print("NEXT    = Re-run with --send-dry-run after reviewing the safety gate.")
        return 0

    if not safety_fields:
        print("RESULT  = REFUSED")
        print("ERROR   = Endpoint exposes no explicit dry_run/approved safety gate; no request was sent.")
        return 2

    print(f"SAFETY  = {', '.join(sorted(safety_fields))}")
    try:
        response = post_json(base + args.path, payload)
    except Exception as exc:
        print("RESULT  = FAILED")
        print(f"ERROR   = {exc}")
        return 1

    print("RESPONSE=")
    print(json.dumps(response, ensure_ascii=False, indent=2))
    print("RESULT  = DONE")
    print("MESSAGE = Safe Windows E2E request completed. Review response before any real execution.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
