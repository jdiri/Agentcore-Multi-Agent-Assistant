"""Mask account numbers and SSN-like strings before text reaches logs, traces or memory.

Shared by every workstream (owner B). Use `mask_sensitive` on any client text before storing or
recording it, and install `MaskingFilter` on log handlers as a backstop.

- SSN-like: `123-45-6789`, `123 45 6789` or nine bare digits become `[SSN]`.
- Account-like: a run of 8 to 17 digits keeps only its last 4: `7793381504` -> `******1504`.

It errs toward masking: a 10-digit phone number with no separators is masked too. Dates
(`2026-11-19`), amounts (`$40,000`) and digit runs that are part of a dashed ID such as a UUID are
left alone. Known limit: an account number split by spaces or dashes (`7793 3815 04`) is not
recognised. Masking is not a reason to log client text: prefer logging IDs and error types.
"""

import logging
import re

SSN_MASK = "[SSN]"
KEEP_LAST = 4

# Not touching another digit or a dash, so parts of dates, dashed IDs and longer runs don't match.
_SSN = re.compile(r"(?<![\d-])(?:\d{3}([- ])\d{2}\1\d{4}|\d{9})(?![\d-])")
_ACCOUNT = re.compile(r"(?<![\d-])\d{8,17}(?![\d-])")


def _mask_account(match: re.Match[str]) -> str:
    digits = match.group()
    return "*" * (len(digits) - KEEP_LAST) + digits[-KEEP_LAST:]


def mask_sensitive(text: str) -> str:
    """Return `text` with SSN-like strings and account-like numbers masked."""
    return _ACCOUNT.sub(_mask_account, _SSN.sub(SSN_MASK, text))


class MaskingFilter(logging.Filter):
    """Masks each log record's final message, including values passed as `%s` arguments."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = mask_sensitive(record.getMessage())
        record.args = None
        return True
