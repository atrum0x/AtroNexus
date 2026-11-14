"""Filling a scenario's mappings with the values IFS sends.

A mapping is text with {field} placeholders: "{customerName}", "Order {orderNo}",
"{customer.phone}" (a dot reads inside an object). Everything else is literal.
"""

import re
from typing import Any

PLACEHOLDER = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)\}")


class MissingValue(ValueError):
    pass


def fields(text: str | None) -> list[str]:
    return PLACEHOLDER.findall(text or "")


def _lookup(params: dict[str, Any], path: str) -> Any:
    value: Any = params
    for part in path.split("."):
        if not isinstance(value, dict) or part not in value:
            raise MissingValue(f"IFS didn't send {{{path}}}.")
        value = value[part]
    return value


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def fill(mapping: str, params: dict[str, Any]) -> str:
    """The mapping with every {field} replaced; raises MissingValue for a field IFS didn't send."""
    return PLACEHOLDER.sub(lambda m: _text(_lookup(params, m.group(1))), mapping)


def parameter(mapping: str, params: dict[str, Any], what: str) -> str:
    """A template variable's value. WhatsApp refuses empty values, line breaks,
    tabs and long runs of spaces in variables, so those are tidied up."""
    value = re.sub(r"[\r\n\t]+", " ", fill(mapping, params))
    value = re.sub(r" {2,}", " ", value).strip()
    if not value:
        raise MissingValue(f"{what} came out empty.")
    return value


def phone(raw: str, default_country_code: str | None) -> str:
    """An international number in digits only (what WhatsApp wants), e.g. 94771234567.

    "+94 77 123 4567" and "0094771234567" work everywhere; "0771234567" needs the
    organization's default country code.
    """
    value = re.sub(r"[\s().-]", "", raw or "")
    if value.startswith("+"):
        value = value[1:]
    elif value.startswith("00"):
        value = value[2:]
    elif value.startswith("0"):
        if not default_country_code:
            raise MissingValue(
                f"{raw!r} is a local number. Send it with the country code, or set a default country code."
            )
        value = default_country_code + value[1:]
    if not value.isdigit() or not 8 <= len(value) <= 15:
        raise MissingValue(f"{raw!r} isn't a phone number.")
    return value
