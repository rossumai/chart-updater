import fnmatch
import re
from typing import Optional, Tuple

import requests
import semantic_version
import yaml
from requests import RequestException

from chart_updater import UpdateException


class HelmRepo:
    def __init__(self, helm_repo_url: str):
        self.helm_repo_url = helm_repo_url
        self._index = None

    def update(self):
        self._index = self._load_chart_repo_index()

    def get_latest_chart_versions(self, chart_name: str, chart_version_pattern: str) -> Tuple[str, str]:
        chart = self._get_latest_chart(chart_name, chart_version_pattern)
        return chart.get("version"), chart.get("appVersion")

    def _load_chart_repo_index(self) -> dict:
        try:
            response = requests.get(f"{self.helm_repo_url}/index.yaml")
            response.raise_for_status()
        except RequestException as e:
            raise UpdateException(f"Cannot download chart list: {str(e)}")
        return yaml.safe_load(response.content)

    def _get_latest_chart(self, chart_name: str, chart_version_pattern: str) -> dict:
        try:
            matching_charts = []
            charts = self._index["entries"][chart_name]
            for chart in charts:
                if self._chart_pattern_match(chart["version"], chart_version_pattern):
                    matching_charts.append(chart)
            return sorted(matching_charts, key=lambda c: c["created"])[-1]
        except (IndexError, KeyError):
            raise UpdateException(
                f"No chart {chart_name} matching {chart_version_pattern} found in the Helm repository"
            )

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
