import fnmatch
import re
from typing import Optional

import requests
import semantic_version
from requests import RequestException
from ruamel.yaml import YAML

from chart_updater import UpdateException


class LatestChart:
    def __init__(
        self,
        helm_repo_url: str,
        helm_repo_user: Optional[str] = None,
        helm_repo_password: Optional[str] = None,
    ):
        self.helm_repo_url = helm_repo_url
        self.helm_repo_user = helm_repo_user
        self.helm_repo_password = helm_repo_password
        self._chart = {}

    @property
    def version(self) -> str:
        return self._chart.get("version")

    @property
    def app_version(self) -> str:
        return self._chart.get("appVersion")

    def _load_chart_repo_index(self):
        try:
            if self.helm_repo_user and self.helm_repo_password:
                auth = {"auth": (self.helm_repo_user, self.helm_repo_password)}
            else:
                auth = {}
            response = requests.get(f"{self.helm_repo_url}/index.yaml", **auth)
            return YAML().load(response.content)
        except RequestException as e:
            raise UpdateException(f"Cannot download chart list: {str(e)}")

    @staticmethod
    def _chart_pattern_match(version: str, pattern: str) -> bool:
        try:
            (type_, value) = pattern.split(":")
        except ValueError:
            (type_, value) = (None, None)

        if type_ == "glob":
            return fnmatch.fnmatch(version, value)
        elif type_ == "regexp" or type_ == "regex":
            return re.search(value, version) is not None
        elif type_ == "semver":
            matcher = semantic_version.NpmSpec(value)
            return matcher.match(semantic_version.Version(version))
        else:
            raise UpdateException("Invalid pattern: {pattern}")

    def _get_latest_chart(
        self, index, chart_name: str, chart_version_pattern: str
    ) -> dict:
        try:
            matching_charts = []
            charts = index["entries"][chart_name]
            for chart in charts:
                if self._chart_pattern_match(chart["version"], chart_version_pattern):
                    matching_charts.append(chart)
            return sorted(matching_charts, key=lambda c: c["created"])[-1]
        except (IndexError, KeyError):
            raise UpdateException(
                f"No chart {chart_name} matching {chart_version_pattern} found in the Helm repository"
            )

    def load(self, chart_name: str, chart_version_pattern: str) -> None:
        index = self._load_chart_repo_index()
        self._chart = self._get_latest_chart(index, chart_name, chart_version_pattern)
