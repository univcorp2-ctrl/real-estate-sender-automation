from __future__ import annotations

import re
from urllib.parse import urlparse

from .models import CampaignPlan, Property, Recipient, ValidationIssue

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
ACTIVE_STATUSES = {"active", "available", "公開", "募集中", "販売中"}


def _https_url(value: str | None) -> bool:
    if not value:
        return False
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.netloc)


def validate_properties(properties: list[Property]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    seen_ids: set[str] = set()
    for prop in properties:
        if not prop.property_id:
            issues.append(ValidationIssue("error", "missing_property_id", "property_id is required"))
        elif prop.property_id in seen_ids:
            issues.append(
                ValidationIssue("error", "duplicate_property_id", "property_id is duplicated", prop.property_id)
            )
        seen_ids.add(prop.property_id)

        if not prop.title:
            issues.append(ValidationIssue("error", "missing_title", "title is required", prop.property_id))
        if prop.price <= 0:
            issues.append(ValidationIssue("error", "invalid_price", "price must be greater than zero", prop.property_id))
        if prop.area <= 0:
            issues.append(ValidationIssue("error", "invalid_area", "area must be greater than zero", prop.property_id))
        if not prop.address:
            issues.append(ValidationIssue("error", "missing_address", "address is required", prop.property_id))
        if prop.status not in ACTIVE_STATUSES:
            issues.append(ValidationIssue("warning", "inactive_property", f"status is {prop.status}", prop.property_id))
        if not _https_url(prop.detail_url):
            issues.append(
                ValidationIssue("error", "invalid_detail_url", "detail_url must be HTTPS", prop.property_id)
            )
        if prop.brochure_url and not _https_url(prop.brochure_url):
            issues.append(
                ValidationIssue("error", "invalid_brochure_url", "brochure_url must be HTTPS", prop.property_id)
            )
    return issues


def validate_recipients(recipients: list[Recipient]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    seen: set[str] = set()
    for rec in recipients:
        if not EMAIL_RE.match(rec.email):
            issues.append(ValidationIssue("error", "invalid_email", "recipient email is invalid", rec.email))
        if rec.email in seen:
            issues.append(ValidationIssue("warning", "duplicate_recipient", "recipient is duplicated", rec.email))
        seen.add(rec.email)
        if not rec.consent:
            issues.append(ValidationIssue("error", "missing_consent", "recipient consent is false", rec.email))
    return issues


def validate_campaign_render(plan: CampaignPlan) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if "{{" in plan.html or "}}" in plan.html or "{%" in plan.html:
        issues.append(ValidationIssue("error", "unrendered_template", "HTML contains template markers"))
    if "{{" in plan.text or "}}" in plan.text or "{%" in plan.text:
        issues.append(ValidationIssue("error", "unrendered_template", "Text contains template markers"))
    if len(plan.subject) > 120:
        issues.append(ValidationIssue("warning", "long_subject", "Subject may be too long"))
    if not plan.properties:
        issues.append(ValidationIssue("error", "empty_campaign", "No properties in campaign"))
    if "unsubscribe" not in plan.html.lower() and "配信停止" not in plan.html:
        issues.append(ValidationIssue("warning", "missing_unsubscribe_hint", "No unsubscribe wording found"))
    return issues


def has_errors(issues: list[ValidationIssue]) -> bool:
    return any(issue.level == "error" for issue in issues)
