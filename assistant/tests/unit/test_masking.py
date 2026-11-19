import logging
import uuid

import pytest

from common.masking import MaskingFilter, mask_sensitive

# 1. Account-like numbers keep only their last 4 digits.


def test_scenario_a11_account_number_is_masked():
    text = "Open a ticket, my account 7793381504 shows a wire I didn't make."
    masked = mask_sensitive(text)
    assert "7793381504" not in masked
    assert masked == "Open a ticket, my account ******1504 shows a wire I didn't make."


@pytest.mark.parametrize(
    ("raw", "masked"),
    [
        ("12345678", "****5678"),
        ("6029376336", "******6336"),
        ("12345678901234567", "*************4567"),
        ("acct#7793381504.", "acct#******1504."),
        ("acct7793381504", "acct******1504"),
    ],
)
def test_account_lengths_and_neighbours(raw, masked):
    assert mask_sensitive(raw) == masked


def test_every_account_in_a_message_is_masked():
    masked = mask_sensitive("Move from 6029376336 to 5960695108")
    assert masked == "Move from ******6336 to ******5108"


# 2. SSN-like strings are fully masked.


@pytest.mark.parametrize("ssn", ["123-45-6789", "123 45 6789", "123456789"])
def test_ssn_forms_are_fully_masked(ssn):
    assert mask_sensitive(f"My SSN is {ssn}.") == "My SSN is [SSN]."


def test_mixed_separators_are_not_an_ssn_but_leave_no_full_number():
    assert mask_sensitive("123-45 6789") == "123-45 6789"  # no run of 8+ digits either


# 3. Ordinary numbers are left alone.


@pytest.mark.parametrize(
    "text",
    [
        "Effective 2026-11-19, the fee is $40,000 or 1,234,567.89 units.",
        "Call 617-555-0134 between 9 and 5.",
        "Ticket T-1234567, 3 to 6 business days, version 3.2, s.4.1",
        "1234567",  # 7 digits: too short to be an account
        "123456789012345678",  # 18 digits: longer than any account
    ],
)
def test_ordinary_numbers_untouched(text):
    assert mask_sensitive(text) == text


def test_dashed_ids_are_not_masked():
    task_id = "12345678-1234-1234-1234-123456789012"
    assert mask_sensitive(f"task_id={task_id}") == f"task_id={task_id}"
    random_id = str(uuid.uuid4())
    assert mask_sensitive(random_id) == random_id


def test_masking_is_idempotent():
    once = mask_sensitive("acct 7793381504 ssn 123-45-6789")
    assert mask_sensitive(once) == once == "acct ******1504 ssn [SSN]"


# 4. The log filter masks the formatted message, arguments included.


def test_log_filter_masks_message_and_arguments(caplog):
    logger = logging.getLogger("test.masking")
    masking = MaskingFilter()
    logger.addFilter(masking)
    try:
        with caplog.at_level(logging.INFO, logger="test.masking"):
            logger.info("client said %s about %s", "acct 7793381504", "SSN 123-45-6789")
            logger.info("literal 6029376336")
    finally:
        logger.removeFilter(masking)
    assert "7793381504" not in caplog.text and "123-45-6789" not in caplog.text
    assert "6029376336" not in caplog.text
    assert [r.getMessage() for r in caplog.records] == [
        "client said acct ******1504 about SSN [SSN]",
        "literal ******6336",
    ]
