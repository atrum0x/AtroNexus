"""Builds the IFS package download for an organization.

The zip has everything a customer's IFS admin needs:
- the source files to build (workspace/purch) and the README,
- the application configuration package already zipped (config/C_ATX_APPROVALS.zip),
- the IFS Connect routing rule and address, with the address pointing at this
  AtroNexus. The hook key isn't included: only its hash is stored, so the
  admin pastes it from the Approvals page.
"""

from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile

PACKAGE_DIR = Path(__file__).resolve().parents[2] / "ifs_package" / "approvals"
ROOT = "atronexus-approvals"
APPCONFIG = "config/appconfig"
ROUTING_ADDRESS = "config/connect/RoutingAddress_C_ATX_APPROVAL_ADDR.xml"
DEFAULT_HOOK_URL = "https://atronexus.atrum0x.com/api/hooks/ifs/approvals"


def _files(folder: Path) -> list[Path]:
    return sorted(p for p in folder.rglob("*") if p.is_file())


def build_zip(hook_url: str) -> bytes:
    if not PACKAGE_DIR.is_dir():
        raise FileNotFoundError(f"IFS package not found at {PACKAGE_DIR}")

    out = BytesIO()
    with ZipFile(out, "w", ZIP_DEFLATED) as zip_:
        for path in _files(PACKAGE_DIR):
            rel = path.relative_to(PACKAGE_DIR).as_posix()
            if rel.startswith(APPCONFIG + "/"):
                continue  # shipped zipped below, ready to import
            data = path.read_bytes()
            if rel == ROUTING_ADDRESS:
                data = data.replace(DEFAULT_HOOK_URL.encode(), escape(hook_url).encode())
            zip_.writestr(f"{ROOT}/{rel}", data)

        # IFS imports an application configuration package as a zip with the
        # package XML and the Items folder at its root.
        inner = BytesIO()
        appconfig = PACKAGE_DIR / APPCONFIG
        with ZipFile(inner, "w", ZIP_DEFLATED) as acp:
            for path in _files(appconfig):
                acp.write(path, path.relative_to(appconfig).as_posix())
        zip_.writestr(f"{ROOT}/config/C_ATX_APPROVALS.zip", inner.getvalue())
    return out.getvalue()
