"""
Sets test-safe environment variables before anything in `opspilot` is
imported -- config.py's `settings` singleton and server.py's
module-level objects are both built at import time, so these have to
land before the first `import opspilot...` anywhere in the test
session. pytest guarantees conftest.py loads before sibling test
modules, which is what makes this reliable.
"""
import os
import tempfile

os.environ.setdefault("LLM_PROVIDER", "mock")
os.environ.setdefault("TARGET_REPO", "octocat/test-repo")
os.environ.setdefault("GITHUB_TOKEN", "")
os.environ.setdefault("REPO_INDEX_PATH", os.path.dirname(os.path.dirname(__file__)))  # index this project's own code
os.environ["OPSPILOT_DB_PATH"] = os.path.join(tempfile.mkdtemp(), "test_opspilot.db")
