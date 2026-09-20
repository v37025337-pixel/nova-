"""Fail-closed Linux process isolation for frozen generated programs.

The child gets only its JSON request, empty environment, closed inherited FDs,
resource limits, and a seccomp syscall allowlist (no open/network/exec/fork).
The expression validator remains the language boundary; this is not a Python
plugin runner. Runtime infrastructure failures do not consume a holdout.
"""

import subprocess
import sys
from pathlib import Path

from .contracts import ContractError, decode, encode


class SandboxError(ContractError):
    pass


def evaluate(jobs, memory):
    request = encode({"jobs": jobs, "memory": memory})
    if len(request.encode()) > 2_000_000:
        raise SandboxError("sandbox request budget")
    try:
        result = subprocess.run([sys.executable, "-I", "-S", str(Path(__file__).with_name("sandbox_worker.py"))],
                                input=request, text=True, capture_output=True, timeout=8,
                                env={}, cwd="/", close_fds=True)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise SandboxError("sandbox unavailable or time budget exceeded") from exc
    if result.returncode or len(result.stdout) > 2_000_000:
        raise SandboxError("sandbox failed closed")
    try:
        body = decode(result.stdout)
    except (ValueError, ContractError) as exc:
        raise SandboxError("invalid sandbox receipt") from exc
    if body.get("isolation") != "linux_seccomp_v1" or body.get("status") != "PASS":
        raise SandboxError("sandbox confinement was not established")
    return body
