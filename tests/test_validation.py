from datetime import datetime, timezone

from property_mailer.models import Property
from property_mailer.validation import has_errors, validate_properties


def test_validate_properties_accepts_valid_property():
    prop = Property(
        property_id="P1",
        title="Valid Property",
        price=1000,
        area=40,
        address="Tokyo",
        status="active",
        updated_at=datetime.now(timezone.utc),
        detail_url="https://example.com/p1",
        brochure_url="https://example.com/p1.pdf",
    )
    issues = validate_properties([prop])
    assert not has_errors(issues)


def test_validate_properties_rejects_http_url():
    prop = Property(
        property_id="P1",
        title="Invalid URL",
        price=1000,
        area=40,
        address="Tokyo",
        status="active",
        updated_at=datetime.now(timezone.utc),
        detail_url="http://example.com/p1",
    )
    issues = validate_properties([prop])
    assert has_errors(issues)
    assert any(issue.code == "invalid_detail_url" for issue in issues)
