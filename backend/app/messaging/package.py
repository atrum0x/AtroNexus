"""Builds the messaging hub's IFS package download: the source to build, the
README, and the IFS Connect routing files with the address pointing at this
AtroNexus. The hook key isn't included (only its hash is stored)."""

from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile

PACKAGE_DIR = Path(__file__).resolve().parents[2] / "ifs_package" / "messaging"
ROOT = "atronexus-messaging"
ROUTING_ADDRESS = "config/connect/RoutingAddress_C_ATX_MESSAGE_ADDR.xml"
DEFAULT_HOOK_URL = "https://atronexus.atrum0x.com/api/hooks/ifs/messages"


def build_zip(hook_url: str) -> bytes:
    if not PACKAGE_DIR.is_dir():
        raise FileNotFoundError(f"IFS package not found at {PACKAGE_DIR}")
    out = BytesIO()
    with ZipFile(out, "w", ZIP_DEFLATED) as zip_:
        for path in sorted(p for p in PACKAGE_DIR.rglob("*") if p.is_file()):
            rel = path.relative_to(PACKAGE_DIR).as_posix()
            data = path.read_bytes()
            if rel == ROUTING_ADDRESS:
                data = data.replace(DEFAULT_HOOK_URL.encode(), escape(hook_url).encode())
            zip_.writestr(f"{ROOT}/{rel}", data)
    return out.getvalue()
