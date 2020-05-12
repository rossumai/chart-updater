import os
import tempfile
from subprocess import run

import pytest


@pytest.fixture
def empty_git_repo():
    git_dir = tempfile.mkdtemp()
    os.chdir(git_dir)
    run(["git", "init"])
    run(["git", "config", "user.name", "test"])
    run(["git", "config", "user.email", "test@rossum.ai"])
    return git_dir
