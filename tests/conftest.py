import os
from subprocess import run
import tempfile

import pytest


@pytest.fixture
def empty_git_repo():
    git_dir = tempfile.mkdtemp()
    os.chdir(git_dir)
    run(['git', 'init'])
    run(["git", "config", "--global", "user.name", "test"])
    run(["git", "config", "--global", "user.email", "test@rossum.ai"])
    return git_dir
