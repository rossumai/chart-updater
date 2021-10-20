import logging
from typing import Optional

# We use ruamel library for YAML manipulation because it preserves format, comments, etc.
# But it is slower than PyYAML for large documents.
from ruamel import yaml

from . import UpdateException
from .helm_repo import HelmRepo

CHART_AUTO_UPDATE = "chart-auto-update"
CHART_VERSION_PATTERN = "chart-version"
IMAGE_PREFIX = "update-image."
DEFAULT_CHART_IMAGE = "chart-image"

log = logging.getLogger("chart-updater")

class InvalidManifestError(Exception):
    pass

def is_true_value(value: str) -> bool:
    return str(value).lower() == "true"

class HelmRelease:
    @staticmethod
    def load(manifest):
        if not manifest:
            raise InvalidManifestError()

        if manifest.get("kind") != "HelmRelease":
            raise InvalidManifestError()

        if "spec" not in manifest:
            raise InvalidManifestError()

        api_version = manifest.get("apiVersion")

        if api_version == "helm.fluxcd.io/v1":
            return HelmReleaseV1(manifest)
        elif api_version == "helm.toolkit.fluxcd.io/v2beta1":
            return HelmReleaseV2(manifest)
        else:
            raise InvalidManifestError()

    def __init__(self, manifest):
        self.manifest = manifest

    @property
    def image_tag(self):
        return self.manifest["spec"].get("values", {}).get("image", {}).get("tag")

    @property
    def annotations(self):
        return self.manifest.get("metadata", {}).get("annotations", {})

    @property
    def values(self):
        return self.manifest.get("spec", {}).get("values", {})


class HelmReleaseV1(HelmRelease):
    def __init__(self, manifest):
        if "chart" not in manifest["spec"]:
            raise InvalidManifestError()

        if "name" not in manifest["spec"]["chart"]:
            raise InvalidManifestError()

        if "version" not in manifest["spec"]["chart"]:
            raise InvalidManifestError()

        super().__init__(manifest)

    @property
    def chart_name(self):
        return self.manifest["spec"]["chart"]["name"]

    @property
    def chart_version(self):
        return self.manifest["spec"]["chart"]["version"]

    @chart_version.setter
    def chart_version(self, version):
        self.manifest["spec"]["chart"]["version"] = version


class HelmReleaseV2(HelmRelease):
    def __init__(self, manifest):
        if "chart" not in manifest["spec"]:
            raise InvalidManifestError()

        if "spec" not in manifest["spec"]["chart"]:
            raise InvalidManifestError()

        if "chart" not in manifest["spec"]["chart"]["spec"]:
            raise InvalidManifestError()

        if "version" not in manifest["spec"]["chart"]["spec"]:
            raise InvalidManifestError()

        super().__init__(manifest)

    @property
    def chart_name(self):
        return self.manifest["spec"]["chart"]["spec"]["chart"]

    @property
    def chart_version(self):
        return self.manifest["spec"]["chart"]["spec"]["version"]

    @chart_version.setter
    def chart_version(self, version):
        self.manifest["spec"]["chart"]["spec"]["version"] = version


class Manifest:
    def __init__(self, annotation_prefix: str = "rossum.ai"):
        self.annotation_prefix = annotation_prefix
        self._chart_auto_update_key = f"{annotation_prefix}/{CHART_AUTO_UPDATE}"
        self._chart_version_pattern_key = f"{annotation_prefix}/{CHART_VERSION_PATTERN}"
        self._chart_version_updated = False
        self._chart_image_updated = False

    def load(self, path: str) -> None:
        try:
            with open(path, "r") as f:
                manifest = yaml.round_trip_load(f, preserve_quotes=True)
        except Exception as e:
            raise UpdateException(f"Cannot load manifest {path}: {str(e)}")

        try:
            self._helmrelease = HelmRelease.load(manifest)
        except InvalidManifestError as e:
            raise UpdateException(f"Cannot load manifest {path}: {str(e)}")

    def save(self, path: str) -> None:
        try:
            with open(path, "w") as f:
                yaml.round_trip_dump(self._helmrelease.manifest, f)
        except Exception as e:
            raise UpdateException(f"Cannot update manifest {path}: {str(e)}")

    @property
    def chart_name(self) -> Optional[str]:
        return self._helmrelease.chart_name

    @property
    def chart_version(self) -> Optional[str]:
        return self._helmrelease.chart_version

    @property
    def image_tag(self) -> Optional[str]:
        return self._helmrelease.image_tag

    @property
    def chart_version_pattern(self) -> Optional[str]:
        return self._helmrelease.annotations[self._chart_version_pattern_key]

    @property
    def chart_updated(self) -> bool:
        return self._chart_updated

    @property
    def image_updated(self) -> bool:
        return self._image_updated

    def _update_chart(self, new_version: str) -> bool:
        if not self._should_update_chart(new_version):
            return False

        self._helmrelease.chart_version = new_version

        log.info(
            f"Updating chart {self.chart_name} from {self.chart_version} to {new_version}"
        )
        return True

    def _should_update_chart(self, new_version):
        if new_version is None:
            return False

        return self.chart_version != new_version

    def _update_image(self, new_tag: Optional[str]) -> bool:
        if new_tag is None:
            return False

        updated = False
        annotation_prefix = f"{self.annotation_prefix}/{IMAGE_PREFIX}"
        for key, value in self._helmrelease.annotations.items():
            if not is_true_value(value):
                continue
            if key.startswith(annotation_prefix):
                image_name = key[len(annotation_prefix) :]
                if image_name == DEFAULT_CHART_IMAGE:
                    image = self._helmrelease.values["image"]
                else:
                    image = self._helmrelease.values[image_name]["image"]
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
        if not self._auto_updates_enabled(self._helmrelease):
            return False

        (
            latest_chart_version,
            latest_chart_app_version,
        ) = helm_repo.get_latest_chart_versions(
            self.chart_name, self.chart_version_pattern
        )

        self._chart_updated = self._update_chart(latest_chart_version)
        self._image_updated = self._update_image(latest_chart_app_version)
        return self._chart_updated or self._image_updated

    def _auto_updates_enabled(self, helmrelease):
        annotations = helmrelease.annotations

        if not is_true_value(annotations.get(self._chart_auto_update_key)):
           return False

        if self._chart_version_pattern_key not in annotations:
           return False

        return True
