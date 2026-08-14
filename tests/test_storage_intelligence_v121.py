from pathlib import Path

from ai_lab_os.storage_curator import FileCandidate, StorageDisposition
from ai_lab_os.storage_intelligence import apply_project_boundaries, build_version_families, detect_project_boundary


def candidate(path: str) -> FileCandidate:
    return FileCandidate(path, 100, 10, StorageDisposition.KEEP, "test")


def test_node_modules_is_project_dependency_boundary() -> None:
    result = detect_project_boundary(Path(r"C:\Work\app\node_modules\electron\electron.exe"))
    assert result.protected is True
    assert "node_modules" in result.reason


def test_venv_site_packages_is_protected() -> None:
    protected = apply_project_boundaries((candidate(r"D:\AI-Lab\app\.venv\Lib\site-packages\torch\x.dll"),))
    assert protected[0].disposition is StorageDisposition.PROTECTED


def test_guanguan_versions_form_one_family() -> None:
    files = (
        candidate(r"C:\Users\PC\Downloads\guanguan-v0.2.zip"),
        candidate(r"C:\Users\PC\Downloads\guanguan-v0.6.2.zip"),
        candidate(r"C:\Users\PC\Downloads\guanguan-v0.6.3.zip"),
    )
    families = build_version_families(files)
    assert len(families) == 1
    assert families[0].family == "guanguan"
    assert families[0].latest.raw_version == "0.6.3"
    assert len(families[0].historical) == 2


def test_copy_suffix_does_not_create_fake_family() -> None:
    files = (
        candidate(r"C:\Users\PC\Downloads\guanguan-v0.3.1-drill-fix.zip"),
        candidate(r"C:\Users\PC\Downloads\guanguan-v0.3.1-drill-fix (1).zip"),
    )
    families = build_version_families(files)
    assert len(families) == 1
    assert families[0].family == "guanguan"
