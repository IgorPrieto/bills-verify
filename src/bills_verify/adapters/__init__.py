"""Adaptadores de entrada. Cada uno expone load(path) -> list[Conversation]."""
from . import common, intercom, zendesk

LOADERS = {
    "common": common.load,
    "intercom": intercom.load,
    "zendesk": zendesk.load,
}

__all__ = ["LOADERS", "common", "intercom", "zendesk"]
