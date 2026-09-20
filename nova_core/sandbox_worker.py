"""Private isolated worker. No journal, knowledge store or oracle is mounted."""

import ctypes
import json
import os
import platform
import resource
import sys
from pathlib import Path

# -I/-S disables ambient site code. This is the pinned runtime's own package.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from nova_core.contracts import ContractError, decode
from nova_core.evaluation import score


def confine():
    machine = platform.machine()
    if sys.platform != "linux" or machine not in ("x86_64", "aarch64"):
        raise RuntimeError("unsupported syscall architecture")
    if machine == "x86_64":
        architecture = 0xC000003E
        allowed = [0, 1, 3, 5, 8, 9, 10, 11, 12, 13, 14, 15, 28, 39, 60, 72,
                   131, 158, 186, 202, 228, 231, 262]
    else:
        architecture = 0xC00000B7
        allowed = [25, 57, 62, 63, 64, 79, 80, 93, 94, 98, 113, 132, 134, 135,
                   139, 172, 178, 214, 215, 216, 222, 226, 233]
    resource.setrlimit(resource.RLIMIT_CPU, (3, 3))
    resource.setrlimit(resource.RLIMIT_AS, (192 * 1024 ** 2, 192 * 1024 ** 2))
    resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
    resource.setrlimit(resource.RLIMIT_NOFILE, (32, 32))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))

    class Filter(ctypes.Structure):
        _fields_ = [("code", ctypes.c_ushort), ("jt", ctypes.c_ubyte),
                    ("jf", ctypes.c_ubyte), ("k", ctypes.c_uint32)]

    class Program(ctypes.Structure):
        _fields_ = [("len", ctypes.c_ushort), ("filter", ctypes.POINTER(Filter))]

    instructions = [(0x20, 0, 0, 4), (0x15, 1, 0, architecture),
                    (0x06, 0, 0, 0x80000000), (0x20, 0, 0, 0)]
    for number in allowed:
        instructions += [(0x15, 0, 1, number), (0x06, 0, 0, 0x7FFF0000)]
    instructions.append((0x06, 0, 0, 0x00050001))  # EPERM, including x32 syscall ABI.
    filters = (Filter * len(instructions))(*(Filter(*row) for row in instructions))
    program = Program(len(filters), filters)
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(38, 1, 0, 0, 0) or libc.prctl(22, 2, ctypes.byref(program), 0, 0):
        raise RuntimeError("seccomp installation failed")
    # Verify actual confinement, not just return codes. Path exists on Linux.
    try:
        os.open("/etc/passwd", os.O_RDONLY)
    except PermissionError:
        pass
    else:
        raise RuntimeError("filesystem confinement probe failed")
    if libc.syscall(41 if machine == "x86_64" else 198, 2, 1, 0) != -1 or ctypes.get_errno() != 1:
        raise RuntimeError("network confinement probe failed")


def main():
    raw = sys.stdin.read(2_000_001)
    if len(raw.encode()) > 2_000_000:
        raise ContractError("request too large")
    data = decode(raw)
    if (set(data) != {"jobs", "memory"} or type(data["jobs"]) is not list or
            not 1 <= len(data["jobs"]) <= 64 or
            sum(len(job["rows"]) for job in data["jobs"]) > 512):
        raise ContractError("invalid sandbox job budget")
    confine()
    results = [score(job["program"], job["rows"], data["memory"]) for job in data["jobs"]]
    print(json.dumps({"status": "PASS", "isolation": "linux_seccomp_v1", "results": results},
                     ensure_ascii=False, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
