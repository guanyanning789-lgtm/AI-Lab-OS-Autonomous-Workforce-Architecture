from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CanonicalLocation:
    key: str
    root: str
    purpose: str


CANONICAL_LOCATIONS = (
    CanonicalLocation("projects", r"D:\AI-Lab\Projects", "active source repositories and project workspaces"),
    CanonicalLocation("apps", r"D:\AI-Lab\Apps", "installed portable/local AI applications"),
    CanonicalLocation("models_llm", r"D:\AI-Lab\Models\LLM", "LLM and GGUF model weights"),
    CanonicalLocation("models_image", r"D:\AI-Lab\Models\Image", "image generation model weights"),
    CanonicalLocation("models_video", r"D:\AI-Lab\Models\Video", "video generation model weights"),
    CanonicalLocation("models_audio", r"D:\AI-Lab\Models\Audio", "ASR, TTS and audio model weights"),
    CanonicalLocation("media_images", r"D:\AI-Lab\Media\Images", "standalone images and generated stills"),
    CanonicalLocation("media_video", r"D:\AI-Lab\Media\Video", "standalone videos and exports"),
    CanonicalLocation("datasets", r"D:\AI-Lab\Datasets", "training and evaluation datasets"),
    CanonicalLocation("knowledge", r"D:\Knowledge\Documents", "personal documents, PDFs and notes"),
    CanonicalLocation("archive", r"D:\Archive", "historical versions and inactive bundles"),
    CanonicalLocation("inbox_downloads", r"C:\Users\PC\Downloads", "temporary download inbox; not a permanent home"),
    CanonicalLocation("inbox_desktop", r"C:\Users\PC\Desktop", "temporary desktop inbox; active shortcuts only"),
)


def render_architecture() -> str:
    lines = ["CANONICAL STORAGE ARCHITECTURE:"]
    for item in CANONICAL_LOCATIONS:
        lines.append(f"  {item.root}")
        lines.append(f"    {item.purpose}")
    return "\n".join(lines)


def classify_canonical_destination(path: str) -> str | None:
    p = Path(path)
    suffix = p.suffix.lower()
    if suffix == ".gguf":
        return r"D:\AI-Lab\Models\LLM"
    if suffix in {".safetensors", ".ckpt", ".pt", ".pth"}:
        return r"D:\AI-Lab\Models"
    if suffix in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
        return r"D:\AI-Lab\Media\Images"
    if suffix in {".mp4", ".mov", ".mkv", ".webm"}:
        return r"D:\AI-Lab\Media\Video"
    if suffix in {".pdf", ".docx", ".txt", ".md", ".xlsx", ".pptx"}:
        return r"D:\Knowledge\Documents"
    if suffix in {".zip", ".7z", ".rar", ".tar", ".gz"}:
        return r"D:\Archive"
    return None
