import logging
import tempfile
from os import environ, path, chdir
from subprocess import PIPE, STDOUT, run
from typing import List, Optional

from chart_updater import UpdateException

log = logging.getLogger("chart-updater")


class Git:
    def __init__(
        self,
        git_url: str,
        git_ref: str = "master",
        git_path: str = ".",
        git_user: str = "user",
        git_email: str = "git@rossum.ai",
        git_timeout: int = 30,
        git_ssh_identity: Optional[str] = None,
    ):
        self.git_url = git_url
        self.git_ref = git_ref
        self.git_path = git_path
        self.git_user = git_user
        self.git_email = git_email
        self.git_timeout = git_timeout
        self.git_ssh_identity = git_ssh_identity
        self._git_dir = None

    def _run(self, command: List[str], max_ok_returncode: int = 0) -> str:
        log.debug("Running command: {' '.join(command)}")
        env_copy = {**environ.copy(), "GIT_SSH_COMMAND": f"ssh -i {self.git_ssh_identity} -o StrictHostKeyChecking=yes"}
        result = run(self._expand_env_vars(command), stdout=PIPE, stderr=STDOUT, text=True, env=env_copy, timeout=self.git_timeout)
        if result.returncode > max_ok_returncode:
            raise UpdateException(
                f"Command \"{' '.join(command)}\" returned {result.returncode}:\n{result.stdout.strip()}"
            )
        return result.stdout

    @staticmethod
    def _expand_env_vars(command: List[str]) -> List[str]:
        return [path.expandvars(part) for part in command]

    def clone_repo(self) -> None:
        self._git_dir = tempfile.mkdtemp()
        self._run(
            ["git", "clone", self.git_url, "--branch", self.git_ref, self._git_dir]
        )
        chdir(self._git_dir)
        self._run(["git", "config", "user.name", self.git_user])
        self._run(["git", "config", "user.email", self.git_email])

    def update_branch(self) -> None:
        self._run(["git", "fetch", "origin"])
        self._run(["git", "reset", "--hard", f"origin/{self.git_ref}"])

    def push_to_branch(self) -> None:
        self._run(["git", "push", "origin", self.git_ref])

    def update_file(self, path_: str, commit_message: str) -> None:
        self._run(["git", "add", path_])
        self._run(["git", "commit", "-m", commit_message])

    def grep(self, pattern: str) -> List[str]:
        output = self._run(
            ["git", "grep", "-l", pattern, "--", self.git_path], max_ok_returncode=1
        )
        return list(filter(None, output.split("\n")))
