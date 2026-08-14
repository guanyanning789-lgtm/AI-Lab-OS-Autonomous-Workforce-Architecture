from __future__ import annotations

import json
import subprocess
from pathlib import Path

import ai_lab_os.managed_repositories as managed_module
from ai_lab_os.managed_repositories import (
    ManagedRepository,
    load_managed_repositories,
    sync_repository,
)


def test_load_managed_repositories(tmp_path):
    config = tmp_path / "managed.json"
    config.write_text(
        json.dumps(
            {
                "repositories": [
                    {
                        "name": "brain",
                        "path": str(tmp_path / "brain"),
                        "branch": "ai/v1.1-coding-agent",
                        "enabled": True,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    repos = load_managed_repositories(config)

    assert len(repos) == 1
    assert repos[0].name == "brain"
    assert repos[0].branch == "ai/v1.1-coding-agent"


def test_sync_repository_blocks_dirty_tree(monkeypatch, tmp_path):
    repo_path = tmp_path / "brain"
    repo_path.mkdir()
    calls = []

    def fake_git(args, *, cwd):
        calls.append(args)
        if args == ["branch", "--show-current"]:
            return subprocess.CompletedProcess(args, 0, "ai/v1.1-coding-agent\n", "")
        if args == ["status", "--porcelain"]:
            return subprocess.CompletedProcess(args, 0, " M app.py\n", "")
        raise AssertionError(args)

    monkeypatch.setattr(managed_module, "_git", fake_git)

    result = sync_repository(
        ManagedRepository(
            name="brain",
            path=str(repo_path),
            branch="ai/v1.1-coding-agent",
        )
    )

    assert result.status == "blocked"
    assert "not clean" in result.message
    assert ["pull", "--ff-only"] not in calls


def test_sync_repository_reports_update(monkeypatch, tmp_path):
    repo_path = tmp_path / "brain"
    repo_path.mkdir()
    heads = iter(["old\n", "new\n"])

    def fake_git(args, *, cwd):
        if args == ["branch", "--show-current"]:
            return subprocess.CompletedProcess(args, 0, "ai/v1.1-coding-agent\n", "")
        if args == ["status", "--porcelain"]:
            return subprocess.CompletedProcess(args, 0, "", "")
        if args == ["rev-parse", "HEAD"]:
            return subprocess.CompletedProcess(args, 0, next(heads), "")
        if args == ["pull", "--ff-only"]:
            return subprocess.CompletedProcess(args, 0, "Updating old..new\n", "")
        raise AssertionError(args)

    monkeypatch.setattr(managed_module, "_git", fake_git)

    result = sync_repository(
        ManagedRepository(
            name="brain",
            path=str(repo_path),
            branch="ai/v1.1-coding-agent",
        )
    )

    assert result.status == "updated"
