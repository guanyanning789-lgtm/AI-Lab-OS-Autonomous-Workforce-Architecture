from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request


KEYWORDS = ("action", "screen", "computer", "windows", "input", "click", "type")


def fetch_openapi(base_url: str, timeout_seconds: int = 10) -> dict[str, object]:
    url = base_url.rstrip("/") + "/openapi.json"
    try:
        with urllib.request.urlopen(url, timeout=timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Cannot reach {url}: {exc.reason}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("OpenAPI response is not a JSON object")
    return payload


def candidate_paths(payload: dict[str, object]) -> list[tuple[str, tuple[str, ...]]]:
    paths = payload.get("paths", {})
    if not isinstance(paths, dict):
        return []
    found: list[tuple[str, tuple[str, ...]]] = []
    for path, operations in paths.items():
        path_text = str(path)
        lowered = path_text.lower()
        if not any(keyword in lowered for keyword in KEYWORDS):
            continue
        methods: list[str] = []
        if isinstance(operations, dict):
            for method in operations:
                if str(method).lower() in {"get", "post", "put", "patch", "delete"}:
                    methods.append(str(method).upper())
        found.append((path_text, tuple(sorted(methods))))
    return sorted(found)


def main() -> int:
    parser = argparse.ArgumentParser(description="Discover local AI Lab Windows/computer action API routes")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()

    print(f"PROBING = {args.base_url.rstrip('/')}/openapi.json")
    try:
        payload = fetch_openapi(args.base_url)
    except Exception as exc:
        print("RESULT = FAILED")
        print(f"ERROR = {exc}")
        return 1

    title = payload.get("info", {}).get("title") if isinstance(payload.get("info"), dict) else None
    if title:
        print(f"API = {title}")

    candidates = candidate_paths(payload)
    if not candidates:
        print("RESULT = NO_CANDIDATE_ROUTES")
        print("No action/screen/computer/windows/input routes were found.")
        return 2

    print("RESULT = FOUND")
    for path, methods in candidates:
        method_text = ",".join(methods) or "UNKNOWN"
        print(f"{method_text:12s} {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
