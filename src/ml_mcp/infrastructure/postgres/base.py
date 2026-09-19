"""SQLAlchemy declarative base and time-sortable identifier generator."""

import os
import time
import uuid
from datetime import datetime, timezone
from sqlalchemy import DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def generate_uuid7() -> str:
    """Generate a time-sortable UUID (RFC 9562 UUIDv7 format)."""
    # 48-bit timestamp in milliseconds
    ms = int(time.time() * 1000)
    # 12 bits of rand_a + 62 bits of rand_b
    rand_bytes = os.urandom(10)

    # Construct 16-byte UUID array
    b = bytearray(16)
    b[0:6] = ms.to_bytes(6, byteorder="big")
    b[6] = 0x70 | (rand_bytes[0] & 0x0F)  # version 7
    b[7] = rand_bytes[1]
    b[8] = 0x80 | (rand_bytes[2] & 0x3F)  # variant 1
    b[9:16] = rand_bytes[3:10]

    return str(uuid.UUID(bytes=bytes(b)))


def utc_now() -> datetime:
    """Return timezone-aware current UTC datetime."""
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """Declarative base class for all ModelLab ORM entities."""

    type_annotation_map = {
        datetime: DateTime(timezone=True),
    }
