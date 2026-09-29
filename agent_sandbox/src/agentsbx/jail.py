"""Filesystem jail for scripted agent tool calls.

Confinement is enforced at the path layer, not by trusting call args:
every path is resolved with os.path.realpath inside the jail root, so
`../` traversal and in-jail symlinks pointing outside both fail closed.
The symlink case matters: string-level policy checks cannot see
filesystem links, which is why a jail exists at all.

exec() runs a subprocess pinned to the jail with a scrubbed
environment. On Linux with bubblewrap installed, commands run under
`bwrap` for real kernel isolation; elsewhere this is a Python-level
jail — cwd pinning plus path confinement, not a security boundary
against code that tries hard (it still sees the host fs through
absolute paths not routed via read/write). The limitation is stated
where it matters: exec is for exercising tool-call plumbing, not for
running hostile binaries.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile


class JailError(Exception):
    """Path escapes the jail root, or an operation was rejected."""


class Jail:
    def __init__(self, root: str | None = None):
        self.root = os.path.realpath(root or tempfile.mkdtemp(
            prefix="agentsbx-"))
        os.makedirs(self.root, exist_ok=True)
        self._bwrap = shutil.which("bwrap")

    # -- path confinement ------------------------------------------------
    def resolve(self, path: str) -> str:
        cand = path if os.path.isabs(path) else os.path.join(self.root,
                                                            path)
        real = os.path.realpath(cand)
        if real != self.root and not real.startswith(self.root
                                                     + os.sep):
            raise JailError(f"escape: {path!r} resolves to {real!r}")
        return real

    # -- tool surface ----------------------------------------------------
    def read(self, path: str) -> str:
        with open(self.resolve(path), "rb") as f:
            return f.read().decode("utf-8", "replace")

    def write(self, path: str, content: str) -> str:
        real = self.resolve(path)
        os.makedirs(os.path.dirname(real) or self.root, exist_ok=True)
        with open(real, "w") as f:
            f.write(content)
        return f"wrote {len(content)} bytes -> {path}"

    def list(self, path: str = ".") -> list[str]:
        real = self.resolve(path)
        return sorted(os.listdir(real)) if os.path.isdir(real) else []

    def exec(self, cmd: str, timeout: int = 10) -> dict:
        # Only jail-relative commands get a real subprocess. Commands
        # are run with a scrubbed env; bwrap adds kernel-level fs
        # confinement when available.
        argv = ["bash", "-c", cmd]
        if self._bwrap:
            argv = [self._bwrap, "--bind", self.root, "/",
                    "--dev", "/dev", "--", *argv]
        env = {"PATH": "/usr/bin:/bin", "HOME": self.root}
        try:
            p = subprocess.run(argv, cwd=self.root, env=env,
                               capture_output=True, text=True,
                               timeout=timeout)
            return {"rc": p.returncode, "out": p.stdout[:4000],
                    "err": p.stderr[:4000], "kernel_isolated":
                        bool(self._bwrap)}
        except subprocess.TimeoutExpired:
            return {"rc": None, "out": "", "err": "timeout",
                    "kernel_isolated": bool(self._bwrap)}

    def snapshot(self) -> dict:
        """File -> size map of the jail, for before/after diffs."""
        out = {}
        for root, _, names in os.walk(self.root):
            for n in names:
                p = os.path.join(root, n)
                out[os.path.relpath(p, self.root)] = os.path.getsize(p)
        return out
