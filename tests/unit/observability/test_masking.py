"""Unit tests for src.observability.masking.mask_pii (PBI-13-01 §17)."""

from src.observability.masking import mask_pii


def test_mask_pii_masks_an_email_address() -> None:
    result = mask_pii("Contact me at jane.doe@example.com for details.")

    assert "jane.doe@example.com" not in result
    assert "[email masked]" in result


def test_mask_pii_masks_a_synthetic_policy_number() -> None:
    result = mask_pii("My policy is SYN-POL-0001.")

    assert "SYN-POL-0001" not in result
    assert "[policy number masked]" in result


def test_mask_pii_masks_a_phone_number() -> None:
    result = mask_pii("Call me at 555-123-4567.")

    assert "555-123-4567" not in result
    assert "[phone masked]" in result


def test_mask_pii_passes_through_none() -> None:
    assert mask_pii(None) is None


def test_mask_pii_leaves_ordinary_text_unchanged() -> None:
    text = "Necesito ayuda con mi siniestro de auto."

    assert mask_pii(text) == text
