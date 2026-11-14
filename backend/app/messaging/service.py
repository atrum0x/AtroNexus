"""Messaging hub: templates to Meta, scenarios, sending, and status updates."""

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.messaging import accounts, render, templates
from app.messaging.meta import MetaClient, MetaError, SenderAccount
from app.messaging.models import (
    APPROVED,
    DELIVERED,
    DRAFT,
    FAILED,
    READ,
    SENDING,
    SENT,
    STATUS_ORDER,
    Message,
    MessageScenario,
    MessageTemplate,
    MessagingSetup,
)
from app.security import hash_link_token, new_link_token
from app.tools.catalog import MESSAGING
from app.usage import service as usage

SENT_EVENT = "messaging.sent"
FAILED_EVENT = "messaging.failed"


def _now() -> datetime:
    return datetime.now(timezone.utc)


# --- Hook keys ---


def new_hook_key(setup: MessagingSetup) -> str:
    key, key_hash = new_link_token()
    setup.hook_key_hash = key_hash
    setup.hook_key_hint = key[-4:]
    return key


def setup_for_hook_key(db: Session, key: str) -> MessagingSetup | None:
    return db.scalar(select(MessagingSetup).where(MessagingSetup.hook_key_hash == hash_link_token(key)))


# --- Templates ---


def spec(t: MessageTemplate) -> templates.TemplateSpec:
    examples = json.loads(t.examples_json or "{}")
    return templates.TemplateSpec(
        name=t.name,
        language=t.language,
        category=t.category,
        body=t.body_text,
        header=t.header_text,
        footer=t.footer_text,
        buttons=[templates.Button(**b) for b in json.loads(t.buttons_json or "[]")],
        body_examples=list(examples.get("body") or []),
        header_example=examples.get("header"),
        button_examples=dict(examples.get("buttons") or {}),
    )


def submit_template(t: MessageTemplate, account: SenderAccount | None) -> None:
    """Sends the template to Meta for review. On failure it stays a draft with the reason."""
    if account is None:
        t.status = DRAFT
        t.status_reason = accounts.NOT_CONNECTED
        return
    t.meta_name = accounts.meta_template_name(account.kind, t.organization_id, t.name)
    try:
        data = MetaClient(account).create_template(templates.meta_payload(spec(t), t.meta_name))
    except MetaError as exc:
        t.status = DRAFT
        t.status_reason = f"WhatsApp didn't accept it: {exc.message}"
        return
    t.waba_id = account.waba_id
    t.meta_template_id = str(data.get("id") or "") or None
    t.status = str(data.get("status") or "PENDING").lower()
    t.status_reason = None
    t.submitted_at = _now()


def refresh_template(t: MessageTemplate, account: SenderAccount) -> None:
    """Reads the review status from Meta (the webhook normally does this)."""
    if not t.meta_template_id:
        return
    data = MetaClient(account).get_template(t.meta_template_id)
    t.status = str(data.get("status") or t.status).lower()
    reason = data.get("rejected_reason")
    t.status_reason = None if not reason or reason == "NONE" else str(reason)[:1000]


def delete_template(t: MessageTemplate, account: SenderAccount | None) -> None:
    """Removes the template from Meta (when it was submitted there)."""
    if t.meta_template_id and account is not None and t.waba_id == account.waba_id:
        MetaClient(account).delete_template(t.meta_name)


def apply_template_event(db: Session, template_id: str, event: str, reason: str | None) -> None:
    """A template status update from Meta's webhook."""
    t = db.scalar(select(MessageTemplate).where(MessageTemplate.meta_template_id == template_id))
    if t is None:
        return
    t.status = event.lower()
    t.status_reason = None if not reason or reason == "NONE" else reason[:1000]


# --- Scenarios ---


def check_mapping(
    t: MessageTemplate, recipient: str, header_param: str | None, body_params: list[str], button_params: dict[str, str]
) -> None:
    """Raises TemplateInvalid unless the mapping fills exactly the template's variables."""
    if not recipient.strip():
        raise templates.TemplateInvalid("Say who gets the message, e.g. {phone}.")
    s = spec(t)
    wanted = templates.body_variable_count(s.body)
    if len(body_params) != wanted or any(not p.strip() for p in body_params):
        raise templates.TemplateInvalid(f"The template's body has {wanted} variable(s); fill each one.")
    if templates.variables(s.header):
        if not (header_param or "").strip():
            raise templates.TemplateInvalid("Fill the header's variable.")
    elif header_param:
        raise templates.TemplateInvalid("The template's header has no variable.")
    url_buttons = {str(i) for i, b in enumerate(s.buttons) if b.has_variable}
    given = {k for k, v in button_params.items() if v.strip()}
    if given != url_buttons:
        raise templates.TemplateInvalid("Fill the variable of each link button that has one, and nothing else.")


# --- Sending ---


@dataclass
class SendRefused(Exception):
    """Nothing was sent: the request can't work as it is (no point retrying unchanged)."""

    status_code: int
    message: str


@dataclass
class Rendered:
    to: str
    header: str | None
    body: list[str]
    buttons: dict[int, str]
    text: str


def render_scenario(scenario: MessageScenario, params: dict[str, Any], setup: MessagingSetup) -> Rendered:
    try:
        to = render.phone(render.fill(scenario.recipient, params), setup.default_country_code)
        header = (
            render.parameter(scenario.header_param, params, "The header's variable") if scenario.header_param else None
        )
        body = [
            render.parameter(m, params, f"Variable {{{{{i}}}}}")
            for i, m in enumerate(json.loads(scenario.body_params_json or "[]"), start=1)
        ]
        buttons = {
            int(k): render.parameter(v, params, f"Button {int(k) + 1}'s variable")
            for k, v in json.loads(scenario.button_params_json or "{}").items()
        }
    except render.MissingValue as exc:
        raise SendRefused(422, str(exc)) from None
    t = scenario.template
    text = templates.fill_numbered(t.body_text, body)
    if t.header_text:
        text = templates.fill_numbered(t.header_text, [header] if header else []) + "\n" + text
    return Rendered(to=to, header=header, body=body, buttons=buttons, text=text[:4000])


def send(
    db: Session,
    setup: MessagingSetup,
    scenario: MessageScenario,
    params: dict[str, Any],
    *,
    source: str,
    external_id: str | None = None,
) -> Message:
    """Sends a scenario's message. Returns the message, which is FAILED if WhatsApp refused it.

    Raises SendRefused when nothing could be sent (template not approved,
    a value missing, WhatsApp not connected). A message IFS already sent
    successfully (same external_id) isn't sent again.
    """
    org_id = setup.organization_id
    t = scenario.template
    if t.status != APPROVED:
        raise SendRefused(409, f"Template {t.name} isn't approved by WhatsApp yet (it's {t.status}).")
    account = accounts.account_for(db, org_id)
    if account is None:
        raise SendRefused(503, accounts.NOT_CONNECTED)
    if t.waba_id != account.waba_id:
        raise SendRefused(409, f"Template {t.name} was made for another WhatsApp account. Submit it again.")

    message = None
    if external_id:
        message = db.scalar(
            select(Message).where(Message.organization_id == org_id, Message.external_id == external_id)
        )
        if message is not None and message.status != FAILED:
            return message
    rendered = render_scenario(scenario, params, setup)
    if message is None:
        message = Message(organization_id=org_id, external_id=external_id, source=source)
        db.add(message)
    message.scenario_id = scenario.id
    message.scenario_code = scenario.code
    message.template_name = t.name
    message.to_phone = rendered.to
    message.text = rendered.text
    message.params_json = json.dumps(params)[:20000]
    message.status = SENDING
    message.error = None
    db.flush()

    components = templates.message_components(rendered.header, rendered.body, rendered.buttons)
    try:
        message.meta_message_id = MetaClient(account).send_template(rendered.to, t.meta_name, t.language, components)
    except MetaError as exc:
        message.status = FAILED
        message.error = exc.message[:1000]
        usage.record(db, org_id, MESSAGING, FAILED_EVENT, billable=False, ref=f"message:{message.id}")
        return message
    message.status = SENT
    message.sent_at = _now()
    usage.record(db, org_id, MESSAGING, SENT_EVENT, billable=True, ref=f"message:{message.id}")
    return message


# --- Delivery reports (Meta's webhook) ---


def apply_status(db: Session, status: dict[str, Any]) -> None:
    """One entry of a webhook's "statuses": sent, delivered, read or failed."""
    meta_id = status.get("id")
    new = str(status.get("status") or "")
    if not meta_id or new not in (SENT, DELIVERED, READ, FAILED):
        return
    message = db.scalar(select(Message).where(Message.meta_message_id == str(meta_id)))
    if message is None:
        return
    try:
        at = datetime.fromtimestamp(int(status.get("timestamp")), timezone.utc)
    except (TypeError, ValueError):
        at = _now()
    if new == FAILED:
        errors = status.get("errors") or [{}]
        err = errors[0] if isinstance(errors, list) and errors else {}
        detail = (err.get("error_data") or {}).get("details") or err.get("message") or err.get("title")
        message.status = FAILED
        message.error = str(detail or "WhatsApp couldn't deliver it.")[:1000]
        return
    if new == DELIVERED:
        message.delivered_at = message.delivered_at or at
    if new == READ:
        message.read_at = message.read_at or at
        message.delivered_at = message.delivered_at or at
    # Reports can arrive out of order: never step back (read stays read).
    if message.status != FAILED and STATUS_ORDER.get(new, 0) > STATUS_ORDER.get(message.status, 0):
        message.status = new
