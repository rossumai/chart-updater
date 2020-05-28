from tempfile import NamedTemporaryFile
from unittest.mock import Mock, patch

from chart_updater.git import Git
from chart_updater.helm_repo import HelmRepo
from chart_updater.updater import Updater

HELM_REPO_URL = "mock://some.url"


def test_git_over_ssh():
    GIT_REPO = "git@github.com:rossumai/_non_existing_repo_"
    with NamedTemporaryFile(mode="w") as tmp, patch("chart_updater.git.run") as run:
        run.return_value = Mock(returncode=111, stdout="Some error")
        updater = Updater(
            Git(GIT_REPO, git_ssh_identity=tmp.name), HelmRepo(HELM_REPO_URL)
        )
        updater.update_loop(one_shot=True)
        run.assert_called_once()
        assert run.call_args.args[0][0:3] == ["git", "clone", GIT_REPO]
        assert (
            run.call_args.kwargs["env"]["GIT_SSH_COMMAND"]
            == f"ssh -i {tmp.name} -o StrictHostKeyChecking=yes"
        )


def test_git_over_https(monkeypatch):
    GIT_AUTHUSER = "test_user"
    GIT_AUTHKEY = "test_pw"
    GIT_REPO = (
        "https://${GIT_AUTHUSER}:${GIT_AUTHKEY}@github.com/rossumai/_non_existing_repo_"
    )
    GIT_REPO_RESOLVED = (
        f"https://{GIT_AUTHUSER}:{GIT_AUTHKEY}@github.com/rossumai/_non_existing_repo_"
    )
    monkeypatch.setenv("GIT_AUTHUSER", GIT_AUTHUSER)
    monkeypatch.setenv("GIT_AUTHKEY", GIT_AUTHKEY)
    with patch("chart_updater.git.run") as run:
        run.return_value = Mock(returncode=111, stdout="Some error")
        updater = Updater(Git(GIT_REPO), HelmRepo(HELM_REPO_URL))
        updater.update_loop(one_shot=True)
        run.assert_called_once()
        assert run.call_args.args[0][0:3] == ["git", "clone", GIT_REPO_RESOLVED]
