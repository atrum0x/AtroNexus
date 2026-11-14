"""Builds the IFS package download for an organization.

The zip has everything a customer's IFS admin needs:
- the source files to build (workspace/purch) and the README,
- an application configuration package (config/C_ATX_APPROVALS.zip) with the
  event actions of the approval types the organization switched on, taken from
  flows/<type>/,
- the IFS Connect routing rule and address, with the address pointing at this
  AtroNexus. The hook key isn't included: only its hash is stored, so the
  admin pastes it from the Approvals page.
"""

from collections.abc import Sequence
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile

from app.approvals.flows import Flow

PACKAGE_DIR = Path(__file__).resolve().parents[2] / "ifs_package" / "approvals"
ROOT = "atronexus-approvals"
FLOWS_DIR = "flows"
ROUTING_ADDRESS = "config/connect/RoutingAddress_C_ATX_APPROVAL_ADDR.xml"
DEFAULT_HOOK_URL = "https://atronexus.atrum0x.com/api/hooks/ifs/approvals"
PACKAGE_NAME = "C_ATX_APPROVALS"
# The package keeps its ID across downloads, so importing a newer one updates it.
PACKAGE_ID = "8E0F2C5A7B3D4E6F9A1B2C3D4E5F6071"
PACKAGE_VERSION = 2
PACKAGE_TIMESTAMP = "2026-11-14-12.00.00"


def _files(folder: Path) -> list[Path]:
    return sorted(p for p in folder.rglob("*") if p.is_file())


def package_xml(chosen: Sequence[Flow]) -> str:
    rows = "".join(
        f"""
    <ITEMS_ROW>
      <NAME>{escape(item.name)}</NAME>
      <TYPE>CUSTOM_EVENT_ACTION</TYPE>
      <DESCRIPTION>{escape(item.description)}</DESCRIPTION>
      <FILENAME>{escape(item.filename)}</FILENAME>
    </ITEMS_ROW>"""
        for flow in chosen
        for item in flow.event_actions
    )
    types = ", ".join(f.name for f in chosen)
    return f"""<?xml version="1.0"?>
<APPLICATION_CONFIGURATION>
  <EXPORT_DEF_VERSION>1</EXPORT_DEF_VERSION>
  <PACKAGE_ID>{PACKAGE_ID}</PACKAGE_ID>
  <NAME>{PACKAGE_NAME}</NAME>
  <DESCRIPTION>{escape(f"AtroNexus approvals: {types}")[:200]}</DESCRIPTION>
  <AUTHOR>AtroNexus</AUTHOR>
  <VERSION>{PACKAGE_VERSION}</VERSION>
  <VERSION_TIME_STAMP>{PACKAGE_TIMESTAMP}</VERSION_TIME_STAMP>
  <ORIGIN>ATRONEXUS-*-*</ORIGIN>
  <LAST_MODIFIED_DATE>{PACKAGE_TIMESTAMP}</LAST_MODIFIED_DATE>
  <ITEMS>{rows}
  </ITEMS>
  <ADDITIONAL_ITEMS/>
</APPLICATION_CONFIGURATION>
"""


def build_zip(hook_url: str, chosen: Sequence[Flow]) -> bytes:
    """The download for the given approval types (only built ones; at least one)."""
    if not PACKAGE_DIR.is_dir():
        raise FileNotFoundError(f"IFS package not found at {PACKAGE_DIR}")
    chosen = [f for f in chosen if f.available]
    if not chosen:
        raise ValueError("No approval types to package.")

    out = BytesIO()
    with ZipFile(out, "w", ZIP_DEFLATED) as zip_:
        for path in _files(PACKAGE_DIR):
            rel = path.relative_to(PACKAGE_DIR).as_posix()
            if rel.startswith(FLOWS_DIR + "/"):
                continue  # shipped inside the configuration package below
            data = path.read_bytes()
            if rel == ROUTING_ADDRESS:
                data = data.replace(DEFAULT_HOOK_URL.encode(), escape(hook_url).encode())
            zip_.writestr(f"{ROOT}/{rel}", data)

        # IFS imports an application configuration package as a zip with the
        # package XML and the Items folder at its root.
        inner = BytesIO()
        with ZipFile(inner, "w", ZIP_DEFLATED) as acp:
            acp.writestr(f"{PACKAGE_NAME}.xml", package_xml(chosen))
            for flow in chosen:
                for item in flow.event_actions:
                    acp.write(PACKAGE_DIR / FLOWS_DIR / flow.folder / item.filename, f"Items/{item.filename}")
        zip_.writestr(f"{ROOT}/config/{PACKAGE_NAME}.zip", inner.getvalue())
    return out.getvalue()
