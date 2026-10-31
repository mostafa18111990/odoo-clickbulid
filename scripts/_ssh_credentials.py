"""Shared SSH authentication settings for maintenance scripts.

SSH keys and the local SSH agent are preferred.  Set
``CLICKBUILD_SSH_PASSWORD`` only for a temporary, approved password-based
connection.  No credential is stored in the repository.
"""

import os


SSH_PASSWORD = os.environ.get("CLICKBUILD_SSH_PASSWORD")
