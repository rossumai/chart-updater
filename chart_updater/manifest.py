import logging
from typing import Optional

# We use ruamel library for YAML manipulation because it preserves format, comments, etc.
# But it is slower than PyYAML for large documents.
from ruamel import yaml
from ruamel.yaml import YAML

from . import UpdateException
from .helm_repo import HelmRepo

CHART_AUTO_UPDATE = "chart-auto-update"
CHART_VERSION_PATTERN = "chart-version"
IMAGE_PREFIX = "update-image."
DEFAULT_CHART_IMAGE = "chart-image"

log = logging.getLogger("chart-updater")


class Manifest:
    def __init__(self, annotation_prefix: str = "rossum.ai"):
        self.annotation_prefix = annotation_prefix
        self._chart_auto_update_key = f"{annotation_prefix}/{CHART_AUTO_UPDATE}"
        self._chart_version_pattern_key = f"{annotation_prefix}/{CHART_VERSION_PATTERN}"
        self._manifest = None
        self._chart_version_updated = False
        self._chart_image_updated = False

    def load(self, path: str) -> None:
        try:
            with open(path, "r") as f:
                self._manifest = yaml.round_trip_load(f, preserve_quotes=True)
        except Exception as e:
            raise UpdateException(f"Cannot load manifest {path}: {str(e)}")

    def save(self, path: str) -> None:
        try:
            with open(path, "w") as f:
                yaml.round_trip_dump(self._manifest, f)
        except Exception as e:
            raise UpdateException(f"Cannot update manifest {path}: {str(e)}")

    @property
    def chart_name(self) -> Optional[str]:
        try:
            return self._manifest["spec"]["chart"]["name"]
        except TypeError:
            return None

    @property
    def chart_version(self) -> Optional[str]:
        try:
            return self._manifest["spec"]["chart"]["version"]
        except TypeError:
            return None

    @property
    def image_tag(self) -> Optional[str]:
        try:
            return self._manifest["spec"]["values"]["image"]["tag"]
        except TypeError:
            return None

    @property
    def chart_version_pattern(self) -> Optional[str]:
        return self._manifest["metadata"]["annotations"][self._chart_version_pattern_key]

    @property
    def chart_updated(self) -> bool:
        return self._chart_updated

    @property
    def image_updated(self) -> bool:
        return self._image_updated

    def _auto_updates_enabled(self) -> bool:
        try:
            kind = self._manifest["kind"]
            chart = self._manifest["spec"]["chart"]
            annotations = self._manifest["metadata"]["annotations"]
            if kind != "HelmRelease":
                return False
            if "name" not in chart:
                return False
            if "version" not in chart:
                return False
            if str(annotations[self._chart_auto_update_key]) != "True":
                return False
            if self._chart_version_pattern_key not in annotations:
                return False
            return True
        except KeyError:
            return False

    def _update_chart(self, new_version: str) -> bool:
        if new_version is None:
            return False
        old_version = self.chart_version
        if old_version == new_version:
            return False
        self._manifest["spec"]["chart"]["version"] = new_version
        log.info(f"Updating chart {self.chart_name} from {old_version} to {new_version}")
        return True

    def _update_image(self, new_tag: Optional[str]) -> bool:
        if new_tag is None:
            return False

        updated = False
        annotation_prefix = f"{self.annotation_prefix}/{IMAGE_PREFIX}"
        for key, value in self._manifest["metadata"]["annotations"].items():
            if str(value) != "True":
                continue
            if key.startswith(annotation_prefix):
                image_name = key[len(annotation_prefix) :]
                if image_name == DEFAULT_CHART_IMAGE:
                    image = self._manifest["spec"]["values"]["image"]
                else:
                    image = self._manifest["spec"]["values"][image_name]["image"]
                old_tag = image["tag"]
                if old_tag == new_tag:
                    continue
                image["tag"] = new_tag
                updated = True
                log.info(
                    f"Updating image {self.chart_name}:{image_name} from {old_tag} to {new_tag}"
                )
        return updated

    def update_with_latest_chart(self, helm_repo: HelmRepo) -> bool:
        if not self._auto_updates_enabled():
            return False

        latest_chart_version, latest_chart_app_version = helm_repo.get_latest_chart_versions(
            self.chart_name,
            self.chart_version_pattern
        )

        self._chart_updated = self._update_chart(latest_chart_version)
        self._image_updated = self._update_image(latest_chart_app_version)
        return self._chart_updated or self._image_updated
