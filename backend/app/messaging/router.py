import hashlib
import hmac
import json
import re
from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response, status
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy import select, update

from app.config import get_settings
from app.deps import DbSession, ManagerOnly, OrgId, VerifiedEmail, get_current_user
from app.messaging import accounts, package, render, service, templates
from app.messaging.meta import MetaError
from app.messaging.models import (
    DRAFT,
    FAILED,
    FROM_IFS,
    FROM_TEST,
    Message,
    MessageScenario,
    MessageTemplate,
    MessagingSetup,
)
from app.models import ORG_ACTIVE, Organization
from app.ratelimit import RateLimiter, enforce
from app.tools.catalog import MESSAGING
from app.tools.service import is_enabled, require_tool

HOOK_PATH = "/api/hooks/ifs/messages"
CODE = re.compile(r"^[A-Z][A-Z0-9_]{1,39}$")

# --- Schemas ---


class SenderOut(BaseModel):
    kind: str  # "shared" for now
    connected: bool
    display_number: str | None


class MessagingSetupOut(BaseModel):
    enabled: bool
    default_country_code: str | None
    hook_url: str
    has_hook_key: bool
    hook_key_hint: str | None
    sender: SenderOut


class MessagingSetupIn(BaseModel):
    enabled: bool = False
    default_country_code: str | None = Field(default=None, pattern=r"^[1-9][0-9]{0,3}$")


class MessagingHookKeyOut(BaseModel):
    hook_key: str


class ButtonIn(BaseModel):
    type: Literal["URL", "QUICK_REPLY"]
    text: str = Field(max_length=25)
    url: str | None = Field(default=None, max_length=2000)


class TemplateIn(BaseModel):
    name: str = Field(max_length=60)
    language: str = Field(default="en", max_length=10)
    category: Literal["UTILITY", "MARKETING"] = "UTILITY"
    header_text: str | None = Field(default=None, max_length=60)
    body_text: str = Field(max_length=1024)
    footer_text: str | None = Field(default=None, max_length=60)
    buttons: list[ButtonIn] = Field(default=[], max_length=3)
    body_examples: list[str] = Field(default=[], max_length=50)
    header_example: str | None = Field(default=None, max_length=200)
    button_examples: dict[str, str] = {}


class TemplateOut(BaseModel):
    id: int
    name: str
    language: str
    category: str
    header_text: str | None
    body_text: str
    footer_text: str | None
    buttons: list[ButtonIn]
    body_variables: int
    header_has_variable: bool
    url_buttons_with_variable: list[int]  # indexes of link buttons whose address ends in {{1}}
    examples: dict[str, Any]
    status: str
    status_reason: str | None
    meta_name: str
    submitted_at: datetime | None
    created_at: datetime
    used_by: int  # scenarios using it


class ScenarioIn(BaseModel):
    code: str = Field(max_length=40)
    name: str = Field(min_length=1, max_length=100)
    template_id: int
    recipient: str = Field(max_length=200)
    header_param: str | None = Field(default=None, max_length=500)
    body_params: list[str] = Field(default=[], max_length=50)
    button_params: dict[str, str] = {}
    enabled: bool = True


class ScenarioOut(BaseModel):
    id: int
    code: str
    name: str
    template_id: int
    template_name: str
    template_status: str
    recipient: str
    header_param: str | None
    body_params: list[str]
    button_params: dict[str, str]
    enabled: bool
    fields: list[str]  # the {fields} IFS must send
    created_at: datetime


class TestSendIn(BaseModel):
    params: dict[str, Any] = {}


class SentMessageOut(BaseModel):
    id: int
    scenario_code: str | None
    template_name: str
    source: str
    to_phone: str
    text: str
    status: str
    error: str | None
    created_at: datetime
    sent_at: datetime | None
    delivered_at: datetime | None
    read_at: datetime | None


class IfsMessageIn(BaseModel):
    """What IFS sends (C_Atx_Message_Util_API.Send)."""

    version: int = 1
    scenario: str = Field(max_length=40)
    params: dict[str, Any] = {}
    messageId: str | None = Field(default=None, max_length=100)


class IfsMessageOut(BaseModel):
    id: int
    status: str
    error: str | None = None


# --- Helpers ---


def _hook_url() -> str:
    return get_settings().app_url.rstrip("/") + HOOK_PATH


def _setup(db: DbSession, org_id: int) -> MessagingSetup:
    setup = db.scalar(select(MessagingSetup).where(MessagingSetup.organization_id == org_id))
    if setup is None:
        setup = MessagingSetup(organization_id=org_id)
        db.add(setup)
        db.flush()
    return setup


def _setup_out(db: DbSession, setup: MessagingSetup) -> MessagingSetupOut:
    account = accounts.account_for(db, setup.organization_id)
    return MessagingSetupOut(
        enabled=setup.enabled,
        default_country_code=setup.default_country_code,
        hook_url=_hook_url(),
        has_hook_key=setup.hook_key_hash is not None,
        hook_key_hint=setup.hook_key_hint,
        sender=SenderOut(
            kind=account.kind if account else accounts.SHARED,
            connected=account is not None,
            display_number=account.display_number if account else None,
        ),
    )


def _get_template(db: DbSession, org_id: int, template_id: int) -> MessageTemplate:
    t = db.get(MessageTemplate, template_id)
    if t is None or t.organization_id != org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Template not found.")
    return t


def _get_scenario(db: DbSession, org_id: int, scenario_id: int) -> MessageScenario:
    s = db.get(MessageScenario, scenario_id)
    if s is None or s.organization_id != org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Scenario not found.")
    return s


def _template_out(db: DbSession, t: MessageTemplate) -> TemplateOut:
    s = service.spec(t)
    return TemplateOut(
        id=t.id,
        name=t.name,
        language=t.language,
        category=t.category,
        header_text=t.header_text,
        body_text=t.body_text,
        footer_text=t.footer_text,
        buttons=[ButtonIn(type=b.type, text=b.text, url=b.url) for b in s.buttons],  # type: ignore[arg-type]
        body_variables=templates.body_variable_count(t.body_text),
        header_has_variable=bool(templates.variables(t.header_text)),
        url_buttons_with_variable=[i for i, b in enumerate(s.buttons) if b.has_variable],
        examples=json.loads(t.examples_json or "{}"),
        status=t.status,
        status_reason=t.status_reason,
        meta_name=t.meta_name,
        submitted_at=t.submitted_at,
        created_at=t.created_at,
        used_by=len(db.scalars(select(MessageScenario.id).where(MessageScenario.template_id == t.id)).all()),
    )


def _scenario_out(s: MessageScenario) -> ScenarioOut:
    body = json.loads(s.body_params_json or "[]")
    buttons = json.loads(s.button_params_json or "{}")
    found: list[str] = []
    for text in [s.recipient, s.header_param, *body, *buttons.values()]:
        for f in render.fields(text):
            if f not in found:
                found.append(f)
    return ScenarioOut(
        id=s.id,
        code=s.code,
        name=s.name,
        template_id=s.template_id,
        template_name=s.template.name,
        template_status=s.template.status,
        recipient=s.recipient,
        header_param=s.header_param,
        body_params=body,
        button_params=buttons,
        enabled=s.enabled,
        fields=found,
        created_at=s.created_at,
    )


def _message_out(m: Message) -> SentMessageOut:
    return SentMessageOut(
        id=m.id,
        scenario_code=m.scenario_code,
        template_name=m.template_name,
        source=m.source,
        to_phone=m.to_phone,
        text=m.text,
        status=m.status,
        error=m.error,
        created_at=m.created_at,
        sent_at=m.sent_at,
        delivered_at=m.delivered_at,
        read_at=m.read_at,
    )


def _apply_template(t: MessageTemplate, body: TemplateIn) -> None:
    t.name = body.name.strip()
    t.language = body.language.strip()
    t.category = body.category
    t.header_text = templates.normalize(body.header_text)
    t.body_text = templates.normalize(body.body_text) or ""
    t.footer_text = templates.normalize(body.footer_text)
    buttons = [
        {"type": b.type, "text": b.text.strip(), "url": templates.normalize(b.url) if b.type == "URL" else None}
        for b in body.buttons
    ]
    t.buttons_json = json.dumps(buttons)
    t.examples_json = json.dumps(
        {
            "body": [e.strip() for e in body.body_examples],
            "header": (body.header_example or "").strip() or None,
            "buttons": {k: v.strip() for k, v in body.button_examples.items() if v.strip()},
        }
    )
    try:
        templates.check(service.spec(t))
    except templates.TemplateInvalid as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from None


# --- Admin ---

router = APIRouter(
    prefix="/api/messaging",
    tags=["messaging"],
    dependencies=[Depends(get_current_user), require_tool(MESSAGING)],
)


@router.get("/setup", response_model=MessagingSetupOut)
def get_messaging_setup(db: DbSession, org_id: OrgId) -> MessagingSetupOut:
    setup = _setup(db, org_id)
    db.commit()
    return _setup_out(db, setup)


@router.put("/setup", response_model=MessagingSetupOut, dependencies=[ManagerOnly])
def update_messaging_setup(body: MessagingSetupIn, db: DbSession, org_id: OrgId) -> MessagingSetupOut:
    setup = _setup(db, org_id)
    if body.enabled and setup.hook_key_hash is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Create a hook key before switching on.")
    setup.enabled = body.enabled
    setup.default_country_code = body.default_country_code or None
    db.commit()
    return _setup_out(db, setup)


@router.post("/setup/hook-key", response_model=MessagingHookKeyOut, dependencies=[ManagerOnly])
def create_messaging_hook_key(db: DbSession, org_id: OrgId) -> MessagingHookKeyOut:
    """A new key for the IFS routing address. The old one stops working at once."""
    setup = _setup(db, org_id)
    key = service.new_hook_key(setup)
    db.commit()
    return MessagingHookKeyOut(hook_key=key)


@router.get(
    "/package",
    response_class=Response,
    responses={200: {"content": {"application/zip": {}}, "description": "The IFS package as a zip"}},
)
def download_messaging_package() -> Response:
    """The IFS package, with the routing address pointing at this AtroNexus."""
    return Response(
        content=package.build_zip(_hook_url()),
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="atronexus-messaging-ifs-package.zip"'},
    )


# Templates


@router.get("/templates", response_model=list[TemplateOut])
def list_message_templates(db: DbSession, org_id: OrgId) -> list[TemplateOut]:
    rows = db.scalars(
        select(MessageTemplate).where(MessageTemplate.organization_id == org_id).order_by(MessageTemplate.name)
    ).all()
    return [_template_out(db, t) for t in rows]


@router.post(
    "/templates",
    response_model=TemplateOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[ManagerOnly, VerifiedEmail],
)
def create_message_template(body: TemplateIn, db: DbSession, org_id: OrgId) -> TemplateOut:
    """Saves the template and submits it to WhatsApp for review."""
    t = MessageTemplate(organization_id=org_id, meta_name="")
    _apply_template(t, body)
    exists = db.scalar(
        select(MessageTemplate.id).where(
            MessageTemplate.organization_id == org_id,
            MessageTemplate.name == t.name,
            MessageTemplate.language == t.language,
        )
    )
    if exists:
        raise HTTPException(status.HTTP_409_CONFLICT, "A template with this name and language already exists.")
    t.meta_name = t.name
    db.add(t)
    db.flush()
    service.submit_template(t, accounts.account_for(db, org_id))
    db.commit()
    return _template_out(db, t)


@router.get("/templates/{template_id}", response_model=TemplateOut)
def get_message_template(template_id: int, db: DbSession, org_id: OrgId) -> TemplateOut:
    return _template_out(db, _get_template(db, org_id, template_id))


@router.put("/templates/{template_id}", response_model=TemplateOut, dependencies=[ManagerOnly, VerifiedEmail])
def update_message_template(template_id: int, body: TemplateIn, db: DbSession, org_id: OrgId) -> TemplateOut:
    """Changes a draft (one WhatsApp hasn't taken yet) and submits it again."""
    t = _get_template(db, org_id, template_id)
    if t.status != DRAFT:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Only drafts can be changed. Make a new template, or delete this one first."
        )
    _apply_template(t, body)
    clash = db.scalar(
        select(MessageTemplate.id).where(
            MessageTemplate.organization_id == org_id,
            MessageTemplate.name == t.name,
            MessageTemplate.language == t.language,
            MessageTemplate.id != t.id,
        )
    )
    if clash:
        raise HTTPException(status.HTTP_409_CONFLICT, "A template with this name and language already exists.")
    service.submit_template(t, accounts.account_for(db, org_id))
    db.commit()
    return _template_out(db, t)


@router.post(
    "/templates/{template_id}/refresh", response_model=TemplateOut, dependencies=[ManagerOnly, VerifiedEmail]
)
def refresh_message_template(template_id: int, db: DbSession, org_id: OrgId) -> TemplateOut:
    """Asks WhatsApp for the review status now (it normally arrives by itself)."""
    t = _get_template(db, org_id, template_id)
    account = accounts.account_for(db, org_id)
    if account is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, accounts.NOT_CONNECTED)
    if t.status == DRAFT:
        service.submit_template(t, account)
    else:
        try:
            service.refresh_template(t, account)
        except MetaError as exc:
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"WhatsApp: {exc.message}") from None
    db.commit()
    return _template_out(db, t)


@router.delete(
    "/templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[ManagerOnly, VerifiedEmail]
)
def delete_message_template(template_id: int, db: DbSession, org_id: OrgId) -> None:
    t = _get_template(db, org_id, template_id)
    if db.scalar(select(MessageScenario.id).where(MessageScenario.template_id == t.id)):
        raise HTTPException(status.HTTP_409_CONFLICT, "A scenario uses this template. Change or delete it first.")
    try:
        service.delete_template(t, accounts.account_for(db, org_id))
    except MetaError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"WhatsApp didn't delete it: {exc.message}") from None
    db.delete(t)
    db.commit()


# Scenarios


def _apply_scenario(db: DbSession, org_id: int, s: MessageScenario, body: ScenarioIn) -> None:
    code = body.code.strip().upper()
    if not CODE.match(code):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "Code: capital letters, digits and _, starting with a letter."
        )
    clash = db.scalar(
        select(MessageScenario.id).where(
            MessageScenario.organization_id == org_id, MessageScenario.code == code, MessageScenario.id != (s.id or 0)
        )
    )
    if clash:
        raise HTTPException(status.HTTP_409_CONFLICT, f"There's already a scenario {code}.")
    t = db.get(MessageTemplate, body.template_id)
    if t is None or t.organization_id != org_id:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Pick one of your templates.")
    header = (body.header_param or "").strip() or None
    params = [p.strip() for p in body.body_params]
    buttons = {k: v.strip() for k, v in body.button_params.items() if v.strip()}
    try:
        service.check_mapping(t, body.recipient, header, params, buttons)
    except templates.TemplateInvalid as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from None
    s.code = code
    s.name = body.name.strip()
    s.template = t
    s.recipient = body.recipient.strip()
    s.header_param = header
    s.body_params_json = json.dumps(params)
    s.button_params_json = json.dumps(buttons)
    s.enabled = body.enabled


@router.get("/scenarios", response_model=list[ScenarioOut])
def list_message_scenarios(db: DbSession, org_id: OrgId) -> list[ScenarioOut]:
    rows = db.scalars(
        select(MessageScenario).where(MessageScenario.organization_id == org_id).order_by(MessageScenario.code)
    ).all()
    return [_scenario_out(s) for s in rows]


@router.post(
    "/scenarios", response_model=ScenarioOut, status_code=status.HTTP_201_CREATED, dependencies=[ManagerOnly]
)
def create_message_scenario(body: ScenarioIn, db: DbSession, org_id: OrgId) -> ScenarioOut:
    s = MessageScenario(organization_id=org_id)
    _apply_scenario(db, org_id, s, body)
    db.add(s)
    db.commit()
    return _scenario_out(s)


@router.get("/scenarios/{scenario_id}", response_model=ScenarioOut)
def get_message_scenario(scenario_id: int, db: DbSession, org_id: OrgId) -> ScenarioOut:
    return _scenario_out(_get_scenario(db, org_id, scenario_id))


@router.put("/scenarios/{scenario_id}", response_model=ScenarioOut, dependencies=[ManagerOnly])
def update_message_scenario(scenario_id: int, body: ScenarioIn, db: DbSession, org_id: OrgId) -> ScenarioOut:
    s = _get_scenario(db, org_id, scenario_id)
    _apply_scenario(db, org_id, s, body)
    db.commit()
    return _scenario_out(s)


@router.delete("/scenarios/{scenario_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[ManagerOnly])
def delete_message_scenario(scenario_id: int, db: DbSession, org_id: OrgId) -> None:
    s = _get_scenario(db, org_id, scenario_id)
    # The log keeps its messages (with the scenario code); only the link goes.
    db.execute(update(Message).where(Message.scenario_id == s.id).values(scenario_id=None))
    db.delete(s)
    db.commit()


@router.post("/scenarios/{scenario_id}/test", response_model=SentMessageOut, dependencies=[ManagerOnly, VerifiedEmail])
def send_test_message(scenario_id: int, body: TestSendIn, db: DbSession, org_id: OrgId) -> SentMessageOut:
    """Sends the scenario's message with sample values, as IFS would. It's a real message, so it counts."""
    s = _get_scenario(db, org_id, scenario_id)
    setup = _setup(db, org_id)
    try:
        message = service.send(db, setup, s, body.params, source=FROM_TEST)
    except service.SendRefused as exc:
        raise HTTPException(exc.status_code, exc.message) from None
    db.commit()
    return _message_out(message)


@router.get("/messages", response_model=list[SentMessageOut])
def list_messages(
    db: DbSession, org_id: OrgId, limit: Annotated[int, Query(ge=1, le=500)] = 100
) -> list[SentMessageOut]:
    rows = db.scalars(
        select(Message).where(Message.organization_id == org_id).order_by(Message.created_at.desc()).limit(limit)
    ).all()
    return [_message_out(m) for m in rows]


# --- The hook IFS calls (through the frontend, which adds the internal key) ---

hook_router = APIRouter(tags=["messaging-hook"])
hook_limiter = RateLimiter(limit=2000, window=3600)


@hook_router.post(HOOK_PATH, response_model=IfsMessageOut)
def receive_ifs_message(
    body: IfsMessageIn,
    db: DbSession,
    response: Response,
    authorization: Annotated[str | None, Header()] = None,
) -> IfsMessageOut:
    key = (authorization or "").removeprefix("Bearer ").strip()
    setup = service.setup_for_hook_key(db, key) if key else None
    if setup is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Unknown hook key.")
    enforce(hook_limiter, f"setup:{setup.id}", "Too many messages. Try again later.")
    org = db.get(Organization, setup.organization_id)
    if org is None or org.status != ORG_ACTIVE or not is_enabled(db, setup.organization_id, MESSAGING):
        raise HTTPException(status.HTTP_409_CONFLICT, "The messaging hub is switched off for this organization.")
    if not setup.enabled:
        raise HTTPException(status.HTTP_409_CONFLICT, "Messaging isn't switched on in AtroNexus yet.")
    if body.version != 1:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Unsupported message version.")
    scenario = db.scalar(
        select(MessageScenario).where(
            MessageScenario.organization_id == setup.organization_id,
            MessageScenario.code == body.scenario.strip().upper(),
        )
    )
    if scenario is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"There's no scenario {body.scenario} in AtroNexus.")
    if not scenario.enabled:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Scenario {scenario.code} is switched off in AtroNexus.")
    try:
        message = service.send(db, setup, scenario, body.params, source=FROM_IFS, external_id=body.messageId)
    except service.SendRefused as exc:
        raise HTTPException(exc.status_code, exc.message) from None
    db.commit()
    if message.status == FAILED:
        # An error status keeps the message in IFS's Application Messages, where it can be resent.
        response.status_code = status.HTTP_502_BAD_GATEWAY
        return IfsMessageOut(id=message.id, status=message.status, error=message.error)
    return IfsMessageOut(id=message.id, status=message.status)


# --- Meta's webhook: template reviews and delivery reports ---

meta_router = APIRouter(tags=["whatsapp-webhook"])
WEBHOOK_PATH = "/api/hooks/meta/whatsapp"


@meta_router.get(WEBHOOK_PATH, response_class=PlainTextResponse)
def verify_whatsapp_webhook(
    mode: Annotated[str, Query(alias="hub.mode")] = "",
    token: Annotated[str, Query(alias="hub.verify_token")] = "",
    challenge: Annotated[str, Query(alias="hub.challenge", max_length=200)] = "",
) -> str:
    """Meta calls this once when the webhook is set up in the Meta app."""
    expected = get_settings().meta_webhook_verify_token
    if mode != "subscribe" or not expected or not hmac.compare_digest(token, expected):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Wrong verify token.")
    return challenge


@meta_router.post(WEBHOOK_PATH)
async def receive_whatsapp_webhook(
    request: Request,
    db: DbSession,
    signature: Annotated[str | None, Header(alias="X-Hub-Signature-256")] = None,
) -> dict[str, bool]:
    raw = await request.body()
    secret = get_settings().meta_app_secret
    if not secret:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "WhatsApp webhook isn't set up.")
    expected = "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    if not signature or not hmac.compare_digest(signature, expected):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Bad signature.")
    try:
        payload = json.loads(raw or b"{}")
    except ValueError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Not JSON.") from None

    for entry in payload.get("entry") or []:
        for change in (entry or {}).get("changes") or []:
            value = (change or {}).get("value") or {}
            if change.get("field") == "messages":
                for item in value.get("statuses") or []:
                    service.apply_status(db, item)
            elif change.get("field") == "message_template_status_update":
                if value.get("message_template_id") and value.get("event"):
                    service.apply_template_event(
                        db, str(value["message_template_id"]), str(value["event"]), value.get("reason")
                    )
    db.commit()
    return {"ok": True}
