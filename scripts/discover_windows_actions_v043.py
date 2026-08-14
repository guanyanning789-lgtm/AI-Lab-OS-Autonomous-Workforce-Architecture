from __future__ import annotations

import argparse
import json
import urllib.request
from typing import Any


DEFAULT_BASE_URL = "http://127.0.0.1:8000"
TARGET_PATHS = (
    "/task/windows/e2e",
    "/actions/execute",
    "/screen/agent",
    "/screen/understand",
)


def fetch_json(url: str) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=15) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"Expected JSON object from {url}")
    return payload


def resolve_ref(document: dict[str, Any], node: Any) -> Any:
    current = node
    seen: set[str] = set()
    while isinstance(current, dict) and "$ref" in current:
        ref = current["$ref"]
        if not isinstance(ref, str) or not ref.startswith("#/"):
            return current
        if ref in seen:
            return current
        seen.add(ref)
        target: Any = document
        for part in ref[2:].split("/"):
            part = part.replace("~1", "/").replace("~0", "~")
            target = target[part]
        current = target
    return current


def walk(document: dict[str, Any], node: Any, path: str, hits: list[dict[str, Any]]) -> None:
    node = resolve_ref(document, node)
    if isinstance(node, dict):
        for key, value in node.items():
            child = f"{path}.{key}" if path else key
            if key.lower() in {"action", "actions", "operation", "kind", "type"} and isinstance(value, (dict, list, str)):
                resolved = resolve_ref(document, value)
                if isinstance(resolved, dict):
                    hit = {
                        "path": child,
                        "enum": resolved.get("enum"),
                        "default": resolved.get("default"),
                        "example": resolved.get("example"),
                        "examples": resolved.get("examples"),
                        "description": resolved.get("description"),
                        "title": resolved.get("title"),
                        "type": resolved.get("type"),
                    }
                    if any(v not in (None, [], "") for k, v in hit.items() if k != "path"):
                        hits.append(hit)
            walk(document, value, child, hits)
    elif isinstance(node, list):
        for index, value in enumerate(node):
            walk(document, value, f"{path}[{index}]", hits)


def endpoint_schema(openapi: dict[str, Any], path: str) -> dict[str, Any] | None:
    operation = openapi.get("paths", {}).get(path, {}).get("post")
    if not isinstance(operation, dict):
        return None
    body = resolve_ref(openapi, operation.get("requestBody", {}))
    if not isinstance(body, dict):
        return None
    content = body.get("content", {})
    if not isinstance(content, dict):
        return None
    media = content.get("application/json", {})
    if not isinstance(media, dict):
        return None
    schema = resolve_ref(openapi, media.get("schema"))
    return schema if isinstance(schema, dict) else None


def main() -> int:
    parser = argparse.ArgumentParser(description="Discover legal Windows action values from local Brain OpenAPI without executing anything")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    args = parser.parse_args()

    base = args.base_url.rstrip("/")
    openapi_url = base + "/openapi.json"
    print(f"OPENAPI = {openapi_url}")
    try:
        openapi = fetch_json(openapi_url)
    except Exception as exc:
        print("RESULT = FAILED")
        print(f"ERROR  = {exc}")
        return 1

    print(f"API     = {openapi.get('info', {}).get('title', 'unknown')}")
    all_hits: list[dict[str, Any]] = []

    for path in TARGET_PATHS:
        schema = endpoint_schema(openapi, path)
        if schema is None:
            continue
        hits: list[dict[str, Any]] = []
        walk(openapi, schema, path, hits)
        print("\n" + "=" * 78)
        print(f"ENDPOINT = POST {path}")
        print("=" * 78)
        print("SCHEMA =")
        print(json.dumps(schema, ensure_ascii=False, indent=2))
        if hits:
            print("ACTION_HINTS =")
            print(json.dumps(hits, ensure_ascii=False, indent=2))
            all_hits.extend(hits)
        else:
            print("ACTION_HINTS = none exposed in this request schema")

    components = openapi.get("components", {}).get("schemas", {})
    component_hits: list[dict[str, Any]] = []
    if isinstance(components, dict):
        for name, schema in components.items():
            if any(token in str(name).lower() for token in ("action", "window", "input", "screen", "taskstep")):
                walk(openapi, schema, f"components.schemas.{name}", component_hits)

    print("\n" + "=" * 78)
    print("COMPONENT_ACTION_HINTS")
    print("=" * 78)
    if component_hits:
        print(json.dumps(component_hits, ensure_ascii=False, indent=2))
        all_hits.extend(component_hits)
    else:
        print("none")

    candidates: list[str] = []
    for hit in all_hits:
        enum = hit.get("enum")
        if isinstance(enum, list):
            candidates.extend(str(item) for item in enum if isinstance(item, (str, int, float)))
        for key in ("default", "example"):
            value = hit.get(key)
            if isinstance(value, str) and value.strip():
                candidates.append(value.strip())

    unique = []
    seen: set[str] = set()
    for candidate in candidates:
        if candidate not in seen:
            seen.add(candidate)
            unique.append(candidate)

    print("\nRESULT = DONE")
    if unique:
        print("LEGAL_ACTION_CANDIDATES = " + ", ".join(unique))
    else:
        print("LEGAL_ACTION_CANDIDATES = none exposed by OpenAPI")
        print("NEXT = inspect the local Brain source for the unsupported_action guard")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
