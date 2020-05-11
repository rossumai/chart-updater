import re
from os import mkdir
from subprocess import run, PIPE
from tempfile import NamedTemporaryFile
from unittest.mock import patch, Mock

from chart_updater.git import Git
from chart_updater.helm_repo import HelmRepo
from chart_updater.updater import Updater

MANIFEST_PATH = "helmrelease.yaml"

MANIFEST_WITHOUT_ANNOTATION = \
"""kind: HelmRelease
metadata:
  name: hello-world
  namespace: default
  annotations:
    fluxcd.io/automated: "true"
spec:
  chart:
  values:
"""

MANIFEST_WITHOUT_CHART_VERSION_PATTERN = \
"""kind: HelmRelease
metadata:
  name: hello-world
  namespace: default
  annotations:
    rossum.ai/chart-auto-update: "true"
spec:
  chart:
  values:
"""

MANIFEST_WITH_SEMVER_PATTERN = \
"""kind: HelmRelease
metadata:
  name: hello-world
  namespace: default
  annotations:
    rossum.ai/chart-auto-update: "true"
    rossum.ai/chart-version: semver:1.2.x
spec:
  chart:
    name: hello-world
    version: 1.2.3
  values:
"""

UPDATED_MANIFEST_WITH_SEMVER_PATTERN = \
"""kind: HelmRelease
metadata:
  name: hello-world
  namespace: default
  annotations:
    rossum.ai/chart-auto-update: "true"
    rossum.ai/chart-version: semver:1.2.x
spec:
  chart:
    name: hello-world
    version: 1.2.4
  values:
"""

MANIFEST_WITH_GLOB_PATTERN = \
"""kind: HelmRelease
metadata:
  name: hello-world
  namespace: default
  annotations:
    rossum.ai/chart-auto-update: "true"
    rossum.ai/chart-version: glob:1.2.*
spec:
  chart:
    name: hello-world
    version: 1.2.3
  values:
"""

UPDATED_MANIFEST_WITH_GLOB_PATTERN = \
"""kind: HelmRelease
metadata:
  name: hello-world
  namespace: default
  annotations:
    rossum.ai/chart-auto-update: "true"
    rossum.ai/chart-version: glob:1.2.*
spec:
  chart:
    name: hello-world
    version: 1.2.4
  values:
"""

MANIFEST_WITH_REGEX_PATTERN = \
"""kind: HelmRelease
metadata:
  name: hello-world
  namespace: default
  annotations:
    rossum.ai/chart-auto-update: "true"
    rossum.ai/chart-version: regex:1\.2\..*
spec:
  chart:
    name: hello-world
    version: 1.2.3
  values:
"""

UPDATED_MANIFEST_WITH_REGEX_PATTERN = \
"""kind: HelmRelease
metadata:
  name: hello-world
  namespace: default
  annotations:
    rossum.ai/chart-auto-update: "true"
    rossum.ai/chart-version: regex:1\.2\..*
spec:
  chart:
    name: hello-world
    version: 1.2.4
  values:
"""

CHART_REPO_INDEX_WITH_ANOTHER_CHART = """
apiVersion: v1
entries:
  cert-manager:
  - version: 0.11.0
    created: "2019-10-10T13:57:16.097Z"
    appVersion: v0.11.0
"""

CHART_REPO_INDEX_WITH_OLD_CHARTS = """
apiVersion: v1
entries:
  hello-world:
  - version: 0.0.1
    created: "2019-10-10T10:00:00.000Z"
    appVersion: v0.11.0
  - version: 0.0.2
    created: "2019-10-10T13:00:00.000Z"
    appVersion: v0.11.1    
"""

CHART_REPO_INDEX_WITH_NEW_CHARTS = """
apiVersion: v1
entries:
  hello-world:
  - version: 1.2.3
    created: "2020-01-02T13:57:16.097Z"
    appVersion: v10.11.12
  - version: 1.2.4
    created: "2020-01-03T13:57:16.097Z"
    appVersion: v10.11.15
  - version: 1.0.0
    created: "2020-01-01T13:57:16.097Z"
    appVersion: v10.11.10
"""

MANIFEST_WITH_SINGLE_IMAGE = \
"""kind: HelmRelease
metadata:
  name: hello-world
  namespace: default
  annotations:
    rossum.ai/chart-auto-update: "true"
    rossum.ai/chart-version: glob:1.2.*
    rossum.ai/update-image.chart-image: "true"
spec:
  chart:
    name: hello-world
    version: 1.2.3
  values:
    image:
      tag: v0.0.1"""

UPDATED_MANIFEST_WITH_SINGLE_IMAGE = \
"""kind: HelmRelease
metadata:
  name: hello-world
  namespace: default
  annotations:
    rossum.ai/chart-auto-update: "true"
    rossum.ai/chart-version: glob:1.2.*
    rossum.ai/update-image.chart-image: "true"
spec:
  chart:
    name: hello-world
    version: 1.2.4
  values:
    image:
      tag: v10.11.15
"""

MANIFEST_WITH_MULTIPLE_IMAGES = \
"""kind: HelmRelease
metadata:
  name: hello-world
  namespace: default
  annotations:
    rossum.ai/chart-auto-update: "true"
    rossum.ai/chart-version: glob:1.2.*
    rossum.ai/update-image.chart-image: "true"
    rossum.ai/update-image.other: "true"
spec:
  chart:
    name: hello-world
    version: 1.2.3
  values:
    image:
      tag: v0.0.1
    other:
      image:
        tag: v0.0.1
"""

UPDATED_MANIFEST_WITH_MULTIPLE_IMAGES = \
"""kind: HelmRelease
metadata:
  name: hello-world
  namespace: default
  annotations:
    rossum.ai/chart-auto-update: "true"
    rossum.ai/chart-version: glob:1.2.*
    rossum.ai/update-image.chart-image: "true"
    rossum.ai/update-image.other: "true"
spec:
  chart:
    name: hello-world
    version: 1.2.4
  values:
    image:
      tag: v10.11.15
    other:
      image:
        tag: v10.11.15
"""

INITIAL_COMMIT_RE = re.compile(r"Init")
CHART_RELEASE_COMMIT_RE = re.compile(r"Release of hello-world 1.2.4.*\+\s+version:\s+1.2.4", flags=re.DOTALL)
SINGLE_IMAGE_RELEASE_COMMIT_RE = re.compile(r"Release of hello-world 1.2.4.*tag:\s+v10.11.15", flags=re.DOTALL)
MULTIPLE_IMAGES_RELEASE_COMMIT_RE = re.compile(r"Release of hello-world 1.2.4.*tag:\s+v10.11.15.*tag:\s+v10.11.15",
                                               flags=re.DOTALL)

HELM_REPO_URL = "mock://some.url"
HELM_REPO_INDEX = f"{HELM_REPO_URL}/index.yaml"


def test_no_annotation(empty_git_repo):
    _add_manifest(MANIFEST_WITHOUT_ANNOTATION)
    _init_commit()

    updater = Updater(Git(empty_git_repo), HelmRepo("mock://"))
    updater.update_loop(one_shot=True)

    assert _get_manifest() == MANIFEST_WITHOUT_ANNOTATION
    assert re.search(INITIAL_COMMIT_RE, _last_commit())


def test_no_chart_tag(empty_git_repo):
    _add_manifest(MANIFEST_WITHOUT_CHART_VERSION_PATTERN)
    _init_commit()

    updater = Updater(Git(empty_git_repo), HelmRepo("mock://"))
    updater.update_loop(one_shot=True)

    assert _get_manifest() == MANIFEST_WITHOUT_CHART_VERSION_PATTERN
    assert re.search(INITIAL_COMMIT_RE, _last_commit())


def test_no_chart_in_helm_repository(empty_git_repo, requests_mock):
    _add_manifest(MANIFEST_WITH_GLOB_PATTERN)
    _init_commit()
    requests_mock.get(HELM_REPO_INDEX, text=CHART_REPO_INDEX_WITH_ANOTHER_CHART)

    updater = Updater(Git(empty_git_repo), HelmRepo(HELM_REPO_URL))
    updater.update_loop(one_shot=True)

    assert _get_manifest() == MANIFEST_WITH_GLOB_PATTERN
    assert re.search(INITIAL_COMMIT_RE, _last_commit())


def test_no_new_chart(empty_git_repo, requests_mock):
    _add_manifest(MANIFEST_WITH_GLOB_PATTERN)
    _init_commit()
    requests_mock.get(HELM_REPO_INDEX, text=CHART_REPO_INDEX_WITH_OLD_CHARTS)

    updater = Updater(Git(empty_git_repo), HelmRepo(HELM_REPO_URL))
    updater.update_loop(one_shot=True)

    assert _get_manifest() == MANIFEST_WITH_GLOB_PATTERN
    assert re.search(INITIAL_COMMIT_RE, _last_commit())


def test_chart_updated_semver(empty_git_repo, requests_mock):
    _add_manifest(MANIFEST_WITH_SEMVER_PATTERN)
    _init_commit()
    requests_mock.get(HELM_REPO_INDEX, text=CHART_REPO_INDEX_WITH_NEW_CHARTS)

    updater = Updater(Git(empty_git_repo), HelmRepo(HELM_REPO_URL))
    updater.update_loop(one_shot=True)

    assert _get_manifest() == UPDATED_MANIFEST_WITH_SEMVER_PATTERN
    assert re.search(CHART_RELEASE_COMMIT_RE, _last_commit())


def test_chart_updated_glob(empty_git_repo, requests_mock):
    _add_manifest(MANIFEST_WITH_GLOB_PATTERN)
    _init_commit()
    requests_mock.get(HELM_REPO_INDEX, text=CHART_REPO_INDEX_WITH_NEW_CHARTS)

    updater = Updater(Git(empty_git_repo), HelmRepo(HELM_REPO_URL))
    updater.update_loop(one_shot=True)

    assert _get_manifest() == UPDATED_MANIFEST_WITH_GLOB_PATTERN
    assert re.search(CHART_RELEASE_COMMIT_RE, _last_commit())


def test_chart_updated_regex(empty_git_repo, requests_mock):
    _add_manifest(MANIFEST_WITH_REGEX_PATTERN)
    _init_commit()
    requests_mock.get(HELM_REPO_INDEX, text=CHART_REPO_INDEX_WITH_NEW_CHARTS)

    updater = Updater(Git(empty_git_repo), HelmRepo(HELM_REPO_URL))
    updater.update_loop(one_shot=True)

    assert _get_manifest() == UPDATED_MANIFEST_WITH_REGEX_PATTERN
    assert re.search(CHART_RELEASE_COMMIT_RE, _last_commit())


def test_default_image_updated(empty_git_repo, requests_mock):
    _add_manifest(MANIFEST_WITH_SINGLE_IMAGE)
    _init_commit()
    requests_mock.get(HELM_REPO_INDEX, text=CHART_REPO_INDEX_WITH_NEW_CHARTS)

    updater = Updater(Git(empty_git_repo), HelmRepo(HELM_REPO_URL))
    updater.update_loop(one_shot=True)

    assert _get_manifest() == UPDATED_MANIFEST_WITH_SINGLE_IMAGE
    assert re.search(SINGLE_IMAGE_RELEASE_COMMIT_RE, _last_commit())


def test_multiple_images_updated(empty_git_repo, requests_mock):
    _add_manifest(MANIFEST_WITH_MULTIPLE_IMAGES)
    _init_commit()
    requests_mock.get(HELM_REPO_INDEX, text=CHART_REPO_INDEX_WITH_NEW_CHARTS)

    updater = Updater(Git(empty_git_repo), HelmRepo(HELM_REPO_URL))
    updater.update_loop(one_shot=True)

    assert _get_manifest() == UPDATED_MANIFEST_WITH_MULTIPLE_IMAGES
    assert re.search(MULTIPLE_IMAGES_RELEASE_COMMIT_RE, _last_commit())


def test_chart_not_updated_manifest_outside_of_path(empty_git_repo, requests_mock):
    mkdir("deploy")
    _add_manifest(MANIFEST_WITH_GLOB_PATTERN)
    _init_commit()
    requests_mock.get(HELM_REPO_INDEX, text=CHART_REPO_INDEX_WITH_NEW_CHARTS)

    updater = Updater(Git(empty_git_repo, git_path="deploy/"), HelmRepo(HELM_REPO_URL))
    updater.update_loop(one_shot=True)

    assert _get_manifest() == MANIFEST_WITH_GLOB_PATTERN
    assert re.search(INITIAL_COMMIT_RE, _last_commit())


def test_chart_updated_manifest_inside_path(empty_git_repo, requests_mock):
    mkdir("deploy")
    _add_manifest(MANIFEST_WITH_GLOB_PATTERN, path="deploy/helmrelease.yaml")
    _init_commit()
    requests_mock.get(HELM_REPO_INDEX, text=CHART_REPO_INDEX_WITH_NEW_CHARTS)

    updater = Updater(Git(empty_git_repo, git_path="deploy/"), HelmRepo(HELM_REPO_URL))
    updater.update_loop(one_shot=True)

    assert _get_manifest("deploy/helmrelease.yaml") == UPDATED_MANIFEST_WITH_GLOB_PATTERN
    assert re.search(CHART_RELEASE_COMMIT_RE, _last_commit())


def test_git_over_ssh():
    GIT_REPO = "git@github.com:rossumai/_non_existing_repo_"
    with NamedTemporaryFile(mode="w") as tmp, patch("chart_updater.git.run") as run:
        run.return_value=Mock(returncode=111, stdout="Some error")
        updater = Updater(Git(GIT_REPO, git_ssh_identity=tmp.name), HelmRepo(HELM_REPO_URL))
        updater.update_loop(one_shot=True)
        run.assert_called_once()
        assert run.call_args.args[0][0:3] == ["git", "clone", GIT_REPO]
        assert run.call_args.kwargs["env"]["GIT_SSH_COMMAND"] == f"ssh -i {tmp.name} -o StrictHostKeyChecking=yes"


def test_git_over_https(monkeypatch):
    GIT_AUTHUSER = "test_user"
    GIT_AUTHKEY = "test_pw"
    GIT_REPO = "https://${GIT_AUTHUSER}:${GIT_AUTHKEY}@github.com/rossumai/_non_existing_repo_"
    GIT_REPO_RESOLVED = f"https://{GIT_AUTHUSER}:{GIT_AUTHKEY}@github.com/rossumai/_non_existing_repo_"
    monkeypatch.setenv("GIT_AUTHUSER", GIT_AUTHUSER)
    monkeypatch.setenv("GIT_AUTHKEY", GIT_AUTHKEY)
    with patch("chart_updater.git.run") as run:
        run.return_value=Mock(returncode=111, stdout="Some error")
        updater = Updater(Git(GIT_REPO), HelmRepo(HELM_REPO_URL))
        updater.update_loop(one_shot=True)
        run.assert_called_once()
        assert run.call_args.args[0][0:3] == ["git", "clone", GIT_REPO_RESOLVED]


def _add_manifest(content: str, path: str = MANIFEST_PATH) -> None:
    with open(path, "w") as f:
        f.write(content)
    run(["git", "add", path])

def _init_commit():
    run(["git", "commit", "-m", "Init"])
    run(["git", "checkout", "-b", "test"])


def _last_commit():
    run(["git", "checkout", "master"])
    return run(["git", "show", "HEAD"], stdout=PIPE, text=True, check=True).stdout


def _get_manifest(path: str = MANIFEST_PATH):
    with open(path, "r") as f:
        return f.read()
