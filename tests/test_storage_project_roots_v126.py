from pathlib import Path

from ai_lab_os.storage_curator import FileCandidate, StorageDisposition
from ai_lab_os.storage_project_roots import apply_project_root_protection, detect_project_roots


def fc(path: Path) -> FileCandidate:
    return FileCandidate(str(path), 1, 0, StorageDisposition.KEEP, "test")


def test_composite_project_root_detected_without_git(tmp_path: Path) -> None:
    root = tmp_path / "AI-Cinema-Studio"
    for name in ("dataset", "output", "toolkit", "shot_factory"):
        (root / name).mkdir(parents=True, exist_ok=True)
    prompt = root / "shot_factory" / "prompt.txt"
    prompt.write_text("x")
    roots = detect_project_roots((fc(prompt),))
    assert any(Path(item.path) == root and item.marker.startswith("composite:") for item in roots)


def test_ordinary_folder_with_two_projectish_children_is_not_project(tmp_path: Path) -> None:
    root = tmp_path / "Desktop"
    (root / "scripts").mkdir(parents=True)
    (root / "output").mkdir()
    file = root / "output" / "x.txt"
    file.write_text("x")
    roots = detect_project_roots((fc(file),))
    assert all(Path(item.path) != root for item in roots)


def test_project_root_protects_internal_media_and_models(tmp_path: Path) -> None:
    root = tmp_path / "AI-Cinema-Studio"
    for name in ("dataset", "output", "toolkit"):
        (root / name).mkdir(parents=True, exist_ok=True)
    model = root / "dataset" / "cache.safetensors"
    video = root / "output" / "clip.mp4"
    model.write_bytes(b"m")
    video.write_bytes(b"v")
    candidates = (fc(model), fc(video))
    roots = detect_project_roots(candidates)
    protected = apply_project_root_protection(candidates, roots)
    assert all(item.disposition is StorageDisposition.PROTECTED for item in protected)
