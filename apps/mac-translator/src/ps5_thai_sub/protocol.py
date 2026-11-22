"""Wire contract: wall clock metadata never determines receiver expiry."""

import re
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime


@dataclass(frozen=True)
class Caption:
    id: str
    text: str
    language: str
    duration_ms: int
    created_at: str

    def __post_init__(self):
        if not re.fullmatch(r"[A-Za-z0-9._-]{1,64}", self.id):
            raise ValueError("Invalid caption id")
        if self.language != "th" or len(self.text.encode("utf-16-le")) // 2 > 500:
            raise ValueError("Expected Thai language and at most 500 UTF-16 code units")
        if any(ord(c) < 32 and c != "\n" for c in self.text):
            raise ValueError("Control characters are forbidden")
        if type(self.duration_ms) is not int or not 250 <= self.duration_ms <= 15000:
            raise ValueError("duration_ms must be 250..15000")
        stamp = datetime.fromisoformat(self.created_at)
        if stamp.tzinfo is None:
            raise ValueError("created_at must include timezone")

    @classmethod
    def new(cls, text: str, duration_ms: int = 5000):
        return cls(str(uuid.uuid4()), text, "th", duration_ms, datetime.now(UTC).isoformat())

    def payload(self):
        return asdict(self)
