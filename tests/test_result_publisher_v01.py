from pathlib import Path

from ai_lab_os.result_publisher import publish_result_file


class FakeCompleted:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_publish_result_stages_only_requested_result(tmp_path):
    repo = tmp_path / "repo"
    result = repo / "results" / "task-0001.json"
    result.parent.mkdir(parents=True)
    result.write_text("{}\n", encoding="utf-8")

    calls = []

    def runner(command, **kwargs):
        calls.append(command)
        if command[:3] == ["git", "rev-parse", "--show-toplevel"]:
            return FakeCompleted(stdout=str(repo) + "\n")
        if command[:3] == ["git", "branch", "--show-current"]:
            return FakeCompleted(stdout="ai/v0.1-foundation\n")
        if command[:3] == ["git", "diff", "--cached"]:
            return FakeCompleted(returncode=1)
        if command[:3] == ["git", "rev-parse", "HEAD"]:
            return FakeCompleted(stdout="abc123\n")
        return FakeCompleted()

    published = publish_result_file(result, runner=runner, push=True)

    assert published.committed is True
    assert published.pushed is True
    assert published.commit_sha == "abc123"
    assert ["git", "add", "--", "results/task-0001.json"] in calls
    assert ["git", "push", "origin", "ai/v0.1-foundation"] in calls


def test_publish_result_rejects_non_result_file(tmp_path):
    repo = tmp_path / "repo"
    target = repo / "notes.txt"
    repo.mkdir()
    target.write_text("x", encoding="utf-8")

    def runner(command, **kwargs):
        if command[:3] == ["git", "rev-parse", "--show-toplevel"]:
            return FakeCompleted(stdout=str(repo) + "\n")
        raise AssertionError(command)

    try:
        publish_result_file(target, runner=runner)
    except ValueError as exc:
        assert "results/" in str(exc)
    else:
        raise AssertionError("expected ValueError")
