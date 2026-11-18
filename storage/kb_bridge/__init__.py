"""Bounded NDJSON subprocess adapter; no compiler imports or implicit fallback."""
from .client import KbAdapter, BridgeError

__all__ = ["KbAdapter", "BridgeError"]
