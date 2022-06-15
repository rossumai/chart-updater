import logging
import subprocess
from threading import Event, Thread
from time import sleep
from typing import Iterator, Optional

from . import UpdateException
from .git import Git
from .helm_repo import HelmRepo
from .manifest import Manifest

log = logging.getLogger("chart-updater")


class Updater:
    def __init__(
        self,
        git: Git,
        helm_repo: HelmRepo,
        refresh_period: int = 60,
        annotation_prefix: str = "rossum.ai",
        event: Optional[Event] = None,
    ) -> None:
        self.git = git
        self.helm_repo = helm_repo
        self.annotation_prefix = annotation_prefix
        self.refresh_period = refresh_period
        self._event = event
        self._cloned = False

    def start(self) -> None:
        Thread(target=self.update_loop, daemon=True).start()

    @staticmethod
    def _build_commit_message(manifest: Manifest) -> str:
        chart_name = manifest.chart_name
        parts = []
        if manifest.chart_updated:
            parts.append(manifest.chart_version)
        if manifest.image_updated:
            parts.append(f"image {manifest.image_tag}")
        return f"Release of {chart_name} {', '.join(parts)}"

    def _manifests_to_check(self) -> Iterator[str]:
        helmreleases = self.git.grep("HelmRelease")
        manifests_with_annotation = self.git.grep(self.annotation_prefix + "/")
        return iter(set(helmreleases).intersection(manifests_with_annotation))

    def _update_manifest(self, path: str) -> bool:
        try:
            manifest = Manifest(self.annotation_prefix)
            manifest.load(path)
            if not manifest.update_with_latest_chart(self.helm_repo):
                return False
            manifest.save(path)
            commit_message = self._build_commit_message(manifest)
            self.git.update_file(path, commit_message)
            return True
        except UpdateException as e:
            log.info(str(e))
            return False

    def _one_update_iteration(self) -> None:
        log.info("Checking for chart updates")
        self.git.update_branch()
        self.helm_repo.update()

        updated = [self._update_manifest(path) for path in self._manifests_to_check()]
        if any(updated):
            self.git.push_to_branch()
            log.info("Update finished")
        else:
            log.info("No updates detected")

    def _ensure_git_repo_cloned(self):
        if self._cloned:
            return
        self.git.clone_repo()
        self._cloned = True

    def update_loop(self, one_shot: bool = False) -> None:
        while True:
            try:
                self._ensure_git_repo_cloned()
                self._one_update_iteration()
            except (UpdateException, subprocess.TimeoutExpired) as e:
                log.error(str(e))

            if one_shot:
                break

            if self._event:
                self._event.wait(self.refresh_period)
                self._event.clear()
            else:
                sleep(self.refresh_period)
