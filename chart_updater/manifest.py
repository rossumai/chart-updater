import logging
from typing import Optional

# We use ruamel library for YAML manipulation because it preserves format, comments, etc.
# But it is slower than PyYAML for large documents.
from ruamel.yaml import YAML

from . import UpdateException
from .helm_repo import HelmRepo

CHART_AUTO_UPDATE = "allow-chart-update"
CHART_VERSION_PATTERN = "chart-version"
IMAGE_PREFIX = "image."
DEFAULT_CHART_IMAGE = "chart-image"

log = logging.getLogger("chart-updater")


class Manifest:
    def __init__(self, annotation_prefix: str = "rossum.ai"):
        self.annotation_prefix = annotation_prefix
        self._chart_auto_update_key = f"{annotation_prefix}/{CHART_AUTO_UPDATE}"
        self._chart_version_pattern_key = f"{annotation_prefix}/{CHART_VERSION_PATTERN}"
        self._manifest = None

    def load(self, path: str) -> None:
        try:
            with open(path, "r") as f:
                self._manifest = YAML().load(f)
        except Exception as e:
            raise UpdateException(f"Cannot load manifest {path}: {str(e)}")

    def save(self, path: str) -> None:
        try:
            with open(path, "w") as f:
                YAML().dump(self._manifest, f)
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

    def _auto_updates_enabled(self) -> bool:
        kind = self._manifest.get("kind")
        chart = self._manifest.get("spec", {}).get("chart") or {}
        annotations = self._manifest.get("metadata", {}).get("annotations") or {}
        if kind != "HelmRelease":
            return False
        if "name" not in chart:
            return False
        if "version" not in chart:
            return False
        if self._chart_version_pattern_key not in annotations:
            return False
        if str(annotations[self._chart_auto_update_key]) != "True":
            return False
        return True

    def _update_chart(self, version: str) -> None:
        self._manifest["spec"]["chart"]["version"] = version
        log.info(f"Updating {self.chart_name} to {version}")

    def _update_image(self, image_tag: Optional[str]) -> Optional[str]:
        if image_tag is None:
            return

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
                image["tag"] = image_tag
                log.info(
                    f"Updating image of {self.chart_name} from {image_name}:{old_tag} to {image_name}:{image_tag}"
                )
        return image_tag

    def update_with_latest_chart(self, helm_repo: HelmRepo) -> bool:
        if not self._auto_updates_enabled():
            return False
        latest_chart_version, latest_chart_app_version = helm_repo.get_latest_chart_versions(
            self.chart_name,
            self.chart_version_pattern
        )
        if self.chart_version == latest_chart_version:
            return False
        self._update_chart(latest_chart_version)
        self._update_image(latest_chart_app_version)
        return True
