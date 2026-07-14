from __future__ import annotations

import secrets
import time
from uuid import UUID


def uuid7() -> UUID:
    """Create a time-ordered UUIDv7 without adding a runtime dependency."""

    unix_ms = time.time_ns() // 1_000_000
    random_bits = secrets.randbits(74)
    value = unix_ms << 80
    value |= 0x7 << 76
    value |= ((random_bits >> 62) & 0xFFF) << 64
    value |= 0b10 << 62
    value |= random_bits & ((1 << 62) - 1)
    return UUID(int=value)
