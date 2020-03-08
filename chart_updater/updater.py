import logging
import os
from threading import Event, Thread
from time import sleep
from typing import Optional

from . import UpdateException
from .helm_repo import HelmRepo
from .git import Git
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
        chart_version = manifest.chart_version
        if manifest.image_updated:
            tag = f", image {manifest.image_tag}"
        else:
            tag = ""
        return f"Release of {chart_name} {chart_version}{tag}"

    def _one_update_iteration(self) -> None:
        log.info("Checking for chart updates")
        self.git.update_branch()
        self.helm_repo.update()

        updated = False
        for path in self.git.grep(self.annotation_prefix + "/"):
            manifest = Manifest(self.annotation_prefix)
            manifest.load(path)
            if manifest.update_with_latest_chart(self.helm_repo):
                manifest.save(path)
                commit_message = self._build_commit_message(manifest)
                self.git.update_file(path, commit_message)
                updated = True
        if updated:
            self.git.push_to_branch()
            log.info("Update finished")
        else:
            log.info("No updates detected")

    def _ensure_git_repo_cloned(self):
        if self._cloned:
            return
        self.git.clone_repo()
        os.chdir(self.git.git_dir)
        self._cloned = True

    def update_loop(self, one_shot: bool = False) -> None:
        while True:
            try:
                self._ensure_git_repo_cloned()
                self._one_update_iteration()
            except UpdateException as e:
                log.error(str(e))

            if one_shot:
                break

            if self._event:
                self._event.wait(self.refresh_period)
                self._event.clear()
            else:
                sleep(self.refresh_period)
