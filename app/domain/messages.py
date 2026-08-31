from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class Lead:
    phone: str
    text: str
    timestamp: str  # ISO 8601


def parse_whatsapp_payload(data: dict) -> list[Lead]:
    """Parse a Meta webhook POST payload and return a list of Lead objects.

    Traverses entry[].changes[].value.messages[] extracting sender and body.
    Returns an empty list if the object is not a whatsapp_business_account.
    """
    if data.get("object") != "whatsapp_business_account":
        return []

    leads: list[Lead] = []
    for entry in data.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            if "messages" in value:
                for msg in value["messages"]:
                    phone = msg["from"]
                    text = msg.get("text", {}).get("body", "")
                    ts = datetime.now().isoformat()
                    leads.append(Lead(phone=phone, text=text, timestamp=ts))
    return leads
