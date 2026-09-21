"""Read-only access to the exact U1 runtime and evidence before the 1.1 upgrade."""

from contextlib import contextmanager
import hashlib
from pathlib import Path
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "experience/unified-v1/frozen-runtime.tar.gz"
SHA256 = "d4a47989e196ba9985cf69a23eb373f5eb07a4e47bd3939c2fa0352e22d4d3ac"


@contextmanager
def extracted():
    if hashlib.sha256(ARCHIVE.read_bytes()).hexdigest() != SHA256:
        raise ValueError("frozen unified runtime archive changed")
    with tempfile.TemporaryDirectory() as folder, tarfile.open(ARCHIVE, "r:gz") as archive:
        root = Path(folder)
        size = 0
        for member in archive.getmembers():
            path = Path(member.name)
            if path.is_absolute() or ".." in path.parts or not (member.isfile() or member.isdir()):
                raise ValueError("unsafe frozen archive member")
            if member.isdir():
                continue
            size += member.size
            if size > 25_000_000:
                raise ValueError("frozen archive exceeds extraction budget")
            destination = root / path
            destination.parent.mkdir(parents=True, exist_ok=True)
            with archive.extractfile(member) as source:
                destination.write_bytes(source.read())
        yield root
