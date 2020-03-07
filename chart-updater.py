#!/usr/bin/env python3

import logging
import threading

import click
from flask import Flask
from waitress import serve

from chart_updater.chart import LatestChart
from chart_updater.git import Git
from chart_updater.updater import Updater

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("chart-updater")
app = Flask(__name__)
event = threading.Event()


@app.route("/v1/sync-git", methods=["POST"])
def refresh():
    event.set()
    log.info("Sync-git triggered")
    return "Sync-git triggered."


@app.route("/")
def healthz():
    return '', 204


@click.command()
@click.option("--git-url", required=True, help="Git config repo URL.")
@click.option("--git-path", default=".", show_default=True, help="Git config path.")
@click.option(
    "--git-branch", default="master", show_default=True, help="Git config repo ref."
)
@click.option(
    "--git-user",
    default="Chart Sync",
    show_default=True,
    help="Git commit author's name.",
)
@click.option(
    "--git-email",
    default="chart-sync@rossum.ai",
    show_default=True,
    help="Git commit author's email.",
)
@click.option("--git-timeout", default=30, show_default=True, help="Git operations timeout (seconds).")
@click.option("--git-ssh-identity", help="Git config SSH identity file (key).")
@click.option("--helm-repo-url", required=True, help="Helm repo URL.")
@click.option("--helm-repo-username", help="Helm repo username (basic auth).")
@click.option("--helm-repo-password", help="Helm repo password (basic auth).")
@click.option(
    "--sync-interval",
    default=60,
    show_default=True,
    help="Period of git sync (seconds).",
)
@click.option(
    "--annotation-prefix",
    default="rossum.ai",
    show_default=True,
    help="Prefix of k8s annotations.",
)
def chart_updater(
    git_url,
    git_path,
    git_branch,
    git_user,
    git_email,
    git_timeout,
    git_ssh_identity,
    helm_repo_url,
    helm_repo_username,
    helm_repo_password,
    sync_interval,
    annotation_prefix,
):
    git = Git(git_url, git_path, git_branch, git_ssh_identity, git_user, git_email, git_timeout, git_ssh_identity)
    chart = LatestChart(helm_repo_url, helm_repo_username, helm_repo_password)
    updater = Updater(git, chart, sync_interval, annotation_prefix, event=event)
    updater.start()
    serve(app, host="0.0.0.0", port=3030)


if __name__ == "__main__":
    chart_updater()
