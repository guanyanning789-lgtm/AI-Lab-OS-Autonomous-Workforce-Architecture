from pathlib import Path

from ai_lab_os.storage_curator import FileCandidate, StorageDisposition
from ai_lab_os.storage_project_roots import apply_project_root_protection, detect_project_roots


def candidate(path: Path) -> FileCandidate:
    return FileCandidate(str(path), path.stat().st_size, 0, StorageDisposition.KEEP, "test")


def test_detects_project_root_from_package_json(tmp_path: Path) -> None:
    project = tmp_path / "AI-Cinema-Studio"
    project.mkdir()
    (project / "package.json").write_text("{}")
    nested = project / "output" / "clip.mp4"
    nested.parent.mkdir()
    nested.write_bytes(b"video")
    roots = detect_project_roots((candidate(nested),))
    assert any(root.path == str(project) for root in roots)


def test_all_files_inside_detected_project_root_become_protected(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "pyproject.toml").write_text("[project]\nname='x'\n")
    readme = project / "README.md"
    model = project / "cache.safetensors"
    readme.write_text("docs")
    model.write_bytes(b"model")
    candidates = (candidate(readme), candidate(model))
    roots = detect_project_roots(candidates)
    protected = apply_project_root_protection(candidates, roots)
    assert all(item.disposition is StorageDisposition.PROTECTED for item in protected)


def test_unrelated_file_remains_unprotected(tmp_path: Path) -> None:
    loose = tmp_path / "Downloads" / "photo.png"
    loose.parent.mkdir()
    loose.write_bytes(b"img")
    protected = apply_project_root_protection((candidate(loose),), ())
    assert protected[0].disposition is StorageDisposition.KEEP
