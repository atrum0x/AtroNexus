"""WhatsApp template rules: checking a template before it goes to Meta,
building Meta's template payload, and the components of a message.

Meta's rules, checked here so customers get a readable message instead of a
rejection a day later:
- variables are {{1}}, {{2}}, ... with no gaps, and each needs an example;
- the body can't start or end with a variable;
- the header has at most one variable, {{1}}; the footer has none;
- a URL button may end with {{1}}; at most 2 URL buttons and 3 buttons in all.
"""

import re
from dataclasses import dataclass, field
from typing import Any

VAR = re.compile(r"\{\{\s*(\d+)\s*\}\}")
NAME = re.compile(r"^[a-z][a-z0-9_]{0,59}$")
LANGUAGE = re.compile(r"^[a-z]{2,3}(_[A-Z]{2})?$")
CATEGORIES = ("UTILITY", "MARKETING")
URL_BUTTON = "URL"
QUICK_REPLY = "QUICK_REPLY"


class TemplateInvalid(ValueError):
    pass


@dataclass
class Button:
    type: str
    text: str
    url: str | None = None

    @property
    def has_variable(self) -> bool:
        return self.type == URL_BUTTON and bool(self.url and VAR.search(self.url))


@dataclass
class TemplateSpec:
    name: str
    language: str
    category: str
    body: str
    header: str | None = None
    footer: str | None = None
    buttons: list[Button] = field(default_factory=list)
    body_examples: list[str] = field(default_factory=list)
    header_example: str | None = None
    button_examples: dict[str, str] = field(default_factory=dict)  # button index -> value


def variables(text: str | None) -> list[int]:
    return [int(n) for n in VAR.findall(text or "")]


def normalize(text: str | None) -> str | None:
    """"{{ 1 }}" -> "{{1}}", trimmed; empty -> None."""
    if text is None:
        return None
    text = VAR.sub(lambda m: "{{" + m.group(1) + "}}", text).strip()
    return text or None


def body_variable_count(body: str) -> int:
    return len(set(variables(body)))


def check(spec: TemplateSpec) -> None:
    """Raises TemplateInvalid with a message a person can act on."""
    if not NAME.match(spec.name):
        raise TemplateInvalid("Name: lowercase letters, digits and _ only, starting with a letter (max 60).")
    if not LANGUAGE.match(spec.language):
        raise TemplateInvalid("Language: a code like en, en_US or si.")
    if spec.category not in CATEGORIES:
        raise TemplateInvalid("Category: UTILITY or MARKETING.")

    body = spec.body
    if not body:
        raise TemplateInvalid("The body can't be empty.")
    if len(body) > 1024:
        raise TemplateInvalid("The body can be at most 1024 characters.")
    numbers = sorted(set(variables(body)))
    if numbers != list(range(1, len(numbers) + 1)):
        raise TemplateInvalid("Number the body's variables {{1}}, {{2}}, ... without gaps.")
    if numbers and (VAR.match(body) or re.search(r"\{\{\d+\}\}$", body)):
        raise TemplateInvalid("The body can't start or end with a variable. Add some text around it.")
    if len(spec.body_examples) != len(numbers) or any(not e.strip() for e in spec.body_examples):
        raise TemplateInvalid("Give an example value for every variable in the body.")

    if spec.header is not None:
        if len(spec.header) > 60:
            raise TemplateInvalid("The header can be at most 60 characters.")
        header_vars = variables(spec.header)
        if header_vars not in ([], [1]):
            raise TemplateInvalid("The header can have one variable, {{1}}.")
        if header_vars and not (spec.header_example or "").strip():
            raise TemplateInvalid("Give an example value for the header's variable.")
    if spec.footer is not None:
        if len(spec.footer) > 60:
            raise TemplateInvalid("The footer can be at most 60 characters.")
        if variables(spec.footer):
            raise TemplateInvalid("The footer can't have variables.")

    if len(spec.buttons) > 3:
        raise TemplateInvalid("At most 3 buttons.")
    if sum(b.type == URL_BUTTON for b in spec.buttons) > 2:
        raise TemplateInvalid("At most 2 link buttons.")
    for i, b in enumerate(spec.buttons):
        if b.type not in (URL_BUTTON, QUICK_REPLY):
            raise TemplateInvalid("A button is a link (URL) or a quick reply.")
        if not b.text or len(b.text) > 25:
            raise TemplateInvalid("Button text: 1 to 25 characters.")
        if b.type == URL_BUTTON:
            url = b.url or ""
            if not url.startswith("https://") or len(url) > 2000:
                raise TemplateInvalid("A link button needs an https:// address.")
            url_vars = variables(url)
            if url_vars not in ([], [1]) or (url_vars and not re.search(r"\{\{1\}\}$", url)):
                raise TemplateInvalid("A link button's address can end with {{1}}, and have no other variable.")
            if url_vars and not (spec.button_examples.get(str(i)) or "").strip():
                raise TemplateInvalid(f"Give an example value for button {i + 1}'s address.")


def meta_payload(spec: TemplateSpec, meta_name: str) -> dict[str, Any]:
    """The body of POST /{waba-id}/message_templates."""
    components: list[dict[str, Any]] = []
    if spec.header:
        header: dict[str, Any] = {"type": "HEADER", "format": "TEXT", "text": spec.header}
        if variables(spec.header):
            header["example"] = {"header_text": [spec.header_example]}
        components.append(header)
    body: dict[str, Any] = {"type": "BODY", "text": spec.body}
    if spec.body_examples:
        body["example"] = {"body_text": [spec.body_examples]}
    components.append(body)
    if spec.footer:
        components.append({"type": "FOOTER", "text": spec.footer})
    if spec.buttons:
        buttons = []
        for i, b in enumerate(spec.buttons):
            if b.type == URL_BUTTON:
                button: dict[str, Any] = {"type": "URL", "text": b.text, "url": b.url}
                if b.has_variable:
                    example = spec.button_examples[str(i)]
                    button["example"] = [VAR.sub(lambda _m, v=example: v, b.url or "")]
                buttons.append(button)
            else:
                buttons.append({"type": "QUICK_REPLY", "text": b.text})
        components.append({"type": "BUTTONS", "buttons": buttons})
    return {
        "name": meta_name,
        "language": spec.language,
        "category": spec.category,
        "components": components,
    }


def fill_numbered(text: str, values: list[str]) -> str:
    """The text with {{n}} replaced by values[n-1] (for the log and previews)."""
    return VAR.sub(lambda m: values[int(m.group(1)) - 1] if int(m.group(1)) <= len(values) else m.group(0), text)


def message_components(
    header_value: str | None, body_values: list[str], button_values: dict[int, str]
) -> list[dict[str, Any]]:
    """The "components" of a template message, with the values filled in."""
    components: list[dict[str, Any]] = []
    if header_value is not None:
        components.append({"type": "header", "parameters": [{"type": "text", "text": header_value}]})
    if body_values:
        components.append({"type": "body", "parameters": [{"type": "text", "text": v} for v in body_values]})
    for index, value in sorted(button_values.items()):
        components.append(
            {"type": "button", "sub_type": "url", "index": str(index), "parameters": [{"type": "text", "text": value}]}
        )
    return components
