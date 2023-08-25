"""Module to test PrivateAIScrubbingProvider."""

from openadapt.privacy.providers.private_ai import PrivateAIScrubbingProvider

scrub = PrivateAIScrubbingProvider()


def _hex_to_rgb(hex_color: int) -> tuple[int, int, int]:
    """Convert a hex color (int) to RGB.

    Args:
        hex_color (int): Hex color value.

    Returns:
        tuple[int, int, int]: RGB values.
    """
    assert 0x000000 <= hex_color <= 0xFFFFFF
    blue = (hex_color >> 16) & 0xFF
    green = (hex_color >> 8) & 0xFF
    red = hex_color & 0xFF
    return red, green, blue


def test_empty_string() -> None:
    """Test empty string input for scrub function returns empty string."""
    text = ""
    expected_output = ""
    assert scrub.scrub_text(text) == expected_output


def test_no_scrub_string() -> None:
    """Test that the same string is returned."""
    text = "This string doesn't have anything to scrub."
    expected_output = "This string doesn't have anything to scrub."
    assert scrub.scrub_text(text) == expected_output


def test_scrub_email() -> None:
    """Test that the email address is scrubbed."""
    assert (
        scrub.scrub_text("My email is john.doe@example.com.")
        == "My email is [EMAIL_ADDRESS_1]."
    )


def test_scrub_phone_number() -> None:
    """Test that the phone number is scrubbed."""
    assert (
        scrub.scrub_text("My phone number is 123-456-7890.")
        == "My phone number is [PHONE_NUMBER_1]."
    )


def test_scrub_credit_card() -> None:
    """Test that the credit card number is scrubbed."""
    assert (
        scrub.scrub_text("My credit card number is 4234-5678-9012-3456 and ")
    ) == "My credit card number is [CREDIT_CARD_1] and "


def test_scrub_date_of_birth() -> None:
    """Test that the date of birth is scrubbed."""
    assert (
        scrub.scrub_text("My date of birth is 01/01/2000.")
        == "My date of birth is [DOB_1]."
    )


def test_scrub_address() -> None:
    """Test that the address is scrubbed."""
    assert (
        scrub.scrub_text("My address is 123 Main St, Toronto, On, CAN.")
        == "My address is [LOCATION_ADDRESS_1]."
    )


def test_scrub_ssn() -> None:
    """Test that the social security number is scrubbed."""
    # Test scrubbing of social security number
    assert (
        scrub.scrub_text("My social security number is 923-45-6789")
        == "My social security number is [SSN_1]"
    )


def test_scrub_dl() -> None:
    """Test that the driver's license number is scrubbed."""
    assert (
        scrub.scrub_text("My driver's license number is A123-456-789-012")
        == "My driver's license number is [DRIVER_LICENSE_1]"
    )


def test_scrub_passport() -> None:
    """Test that the passport number is scrubbed."""
    assert (
        scrub.scrub_text("My passport number is A1234567.")
        == "My passport number is [PASSPORT_NUMBER_1]."
    )


def test_scrub_national_id() -> None:
    """Test that the national ID number is scrubbed."""
    assert (
        scrub.scrub_text("My national ID number is 1234567890123.")
        == "My national ID number is [HEALTHCARE_NUMBER_1]."
    )


def test_scrub_routing_number() -> None:
    """Test that the bank routing number is scrubbed."""
    assert (
        scrub.scrub_text("My bank routing number is 123456789.")
        == "My bank routing number is [ROUTING_NUMBER_1]."
    )


def test_scrub_bank_account() -> None:
    """Test that the bank account number is scrubbed."""
    assert (
        scrub.scrub_text("My bank account number is 635526789012.")
        == "My bank account number is [BANK_ACCOUNT_1]."
    )


def test_scrub_all_together() -> None:
    """Test that all PII/PHI types are scrubbed."""
    text_with_pii_phi = (
        "John Smith's email is johnsmith@example.com and"
        " his phone number is 555-123-4567."
        "His credit card number is 4831-5538-2996-5651 and"
        " his social security number is 923-45-6789."
        " He was born on 01/01/1980."
    )
    assert (
        scrub.scrub_text(text_with_pii_phi)
        == "[NAME_1]'s email is [EMAIL_ADDRESS_1] and"
        " his phone number is [PHONE_NUMBER_1]."
        "His credit card number is [CREDIT_CARD_1] and"
        " his social security number is [SSN_1]."
        " He was born on [DOB_1]."
    )


def test_scrub_dict() -> None:
    """Test that the scrub_dict function works."""
    text_with_pii_phi = {"title": "hi my name is Bob Smith."}

    expected_output = {"title": "hi my name is [NAME_1]."}

    assert scrub.scrub_dict(text_with_pii_phi) == expected_output