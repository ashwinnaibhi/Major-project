"""Backend-only Brevo transactional email adapter and safe notification templates.

External delivery remains disabled unless HAEMOPULSE_DISABLE_EXTERNAL_MESSAGES=false.
No provider SDK is required; calls use the Python standard library.
"""
from __future__ import annotations

import html
import json
import os
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime, parseaddr
from dataclasses import dataclass
from typing import Any, Mapping

BREVO_SEND_URL = "https://api.brevo.com/v3/smtp/email"
DEFAULT_TIMEOUT_SECONDS = 10


@dataclass(frozen=True)
class SubmissionResult:
    status: str  # SUBMITTED, RETRY, FAILED, DISABLED, NEEDS_REVIEW
    provider_message_id: str | None = None
    error_code: str | None = None
    http_status: int | None = None
    retry_after_seconds: int | None = None


def external_messages_enabled() -> bool:
    return os.getenv("HAEMOPULSE_DISABLE_EXTERNAL_MESSAGES", "true").strip().lower() not in {"1", "true", "yes"}


def _safe_header(value: str, *, max_len: int = 180) -> str:
    # Header injection protection plus conservative whitespace normalization.
    value = re.sub(r"[\r\n\x00-\x1f\x7f]+", " ", str(value or ""))
    return " ".join(value.split())[:max_len]


def _e(value: Any) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def render_donor_emergency_email(request: Mapping[str, Any], donor_name: str) -> tuple[str, str, str]:
    """Return (subject, text, HTML); deliberately omit all patient details and ML claims."""
    request_id = int(request["id"])
    blood_group = _safe_header(request.get("blood_group", ""), max_len=16)
    hospital = _safe_header(request.get("hospital_name", "Hospital"), max_len=160)
    urgency = _safe_header(request.get("urgency_level", "EMERGENCY"), max_len=32)
    units = request.get("units_needed", "Not specified")
    address = str(request.get("hospital_address") or "Not specified")
    url = os.getenv("FRONTEND_URL", "http://localhost:3000").rstrip("/")
    subject = _safe_header(f"Emergency blood request #{request_id}: {blood_group}")
    text = (
        f"Hello {donor_name or 'Donor'},\n\nHaemoPulse has an emergency blood request that may match your profile.\n"
        f"Request reference: #{request_id}\nBlood group needed: {blood_group}\nUrgency: {urgency}\n"
        f"Quantity requested: {units}\nHospital/location: {hospital}\nAddress: {address}\n\n"
        f"Sign in to HaemoPulse to review the request and decide whether you can respond: {url}\n\n"
        "Please check your current eligibility before responding. This email does not guarantee availability or eligibility."
    )
    html_body = f"""<!doctype html><html><body style="font-family:Arial,sans-serif;line-height:1.5;color:#172033">
      <h2>HaemoPulse emergency blood request</h2><p>Hello {_e(donor_name or 'Donor')},</p>
      <p>An emergency blood request may match your profile. Please review it before responding.</p>
      <table cellpadding="6" cellspacing="0" border="0">
      <tr><td><b>Request reference</b></td><td>#{request_id}</td></tr>
      <tr><td><b>Blood group</b></td><td>{_e(blood_group)}</td></tr>
      <tr><td><b>Urgency</b></td><td>{_e(urgency)}</td></tr>
      <tr><td><b>Quantity</b></td><td>{_e(units)}</td></tr>
      <tr><td><b>Hospital</b></td><td>{_e(hospital)}</td></tr>
      <tr><td><b>Location</b></td><td>{_e(address)}</td></tr></table>
      <p><a href="{_e(url)}">Open HaemoPulse and review the request</a></p>
      <p>Please verify your current eligibility. This email does not guarantee blood availability or eligibility.</p>
      </body></html>"""
    return subject, text, html_body


def render_acceptance_email(request: Mapping[str, Any], donor: Mapping[str, Any], recipient_kind: str) -> tuple[str, str, str]:
    request_id = int(request["id"])
    blood_group = _safe_header(request.get("blood_group", ""), max_len=16)
    hospital = _safe_header(request.get("hospital_name", "Hospital"), max_len=160)
    donor_name = _safe_header(donor.get("name", "Donor"), max_len=120)
    donor_email = _safe_header(donor.get("email", ""), max_len=254)
    donor_phone = _safe_header(donor.get("phone", ""), max_len=32)
    accepted_at = _safe_header(donor.get("accepted_at", ""), max_len=40)
    recipient_label = "hospital" if recipient_kind == "HOSPITAL" else "assigned administrator"
    url = os.getenv("FRONTEND_URL", "http://localhost:3000").rstrip("/")
    subject = _safe_header(f"HaemoPulse: donor accepted emergency request #{request_id}")
    contact = f"Donor contact: {donor_phone or 'Not available'}; {donor_email or 'Email not available'}"
    text = (f"Hello,\n\nA donor accepted emergency request #{request_id}.\nBlood group: {blood_group}\n"
            f"Hospital: {hospital}\nDonor: {donor_name}\n{contact}\nAccepted at: {accepted_at}\n\n"
            f"Please sign in to HaemoPulse to review and coordinate next steps: {url}\n"
            f"This notification was routed to the linked responsible {recipient_label}.")
    html_body = f"""<!doctype html><html><body style="font-family:Arial,sans-serif;line-height:1.5;color:#172033">
      <h2>Donor acceptance recorded</h2><p>A donor accepted emergency request <b>#{request_id}</b>.</p>
      <p><b>Blood group:</b> {_e(blood_group)}<br/><b>Hospital:</b> {_e(hospital)}<br/>
      <b>Donor:</b> {_e(donor_name)}<br/><b>Phone:</b> {_e(donor_phone or 'Not available')}<br/>
      <b>Email:</b> {_e(donor_email or 'Not available')}<br/><b>Accepted at:</b> {_e(accepted_at)}</p>
      <p><a href="{_e(url)}">Open HaemoPulse to coordinate next steps</a></p>
      </body></html>"""
    return subject, text, html_body


def send_transactional_email(*, recipient_email: str, recipient_name: str, subject: str,
                             text_content: str, html_content: str,
                             timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS) -> SubmissionResult:
    """Submit one transactional email to Brevo. This never retries or falls back to SMTP."""
    if not external_messages_enabled():
        return SubmissionResult("DISABLED", error_code="EXTERNAL_MESSAGES_DISABLED")

    api_key = os.getenv("BREVO_API_KEY", "").strip()
    sender_raw = os.getenv("MAIL_FROM", "").strip()
    parsed_sender_name, parsed_sender_email = parseaddr(sender_raw)
    sender_email = parsed_sender_email or sender_raw
    sender_name = (os.getenv("MAIL_FROM_NAME", "").strip() or parsed_sender_name or "HaemoPulse")
    if not api_key or not sender_email or "@" not in sender_email or "<" in sender_email or ">" in sender_email:
        return SubmissionResult("FAILED", error_code="PROVIDER_NOT_CONFIGURED")

    # Validate/sanitize header fields before constructing the payload.
    recipient_email = _safe_header(recipient_email, max_len=254)
    if "@" not in recipient_email:
        return SubmissionResult("FAILED", error_code="INVALID_RECIPIENT")
    subject = _safe_header(subject, max_len=180)
    payload = {
        "sender": {"email": sender_email, "name": _safe_header(sender_name, max_len=80)},
        "to": [{"email": recipient_email, "name": _safe_header(recipient_name, max_len=120)}],
        "subject": subject,
        "textContent": str(text_content),
        "htmlContent": str(html_content),
        "tags": ["haemopulse", "emergency-notification"],
    }
    request = urllib.request.Request(
        BREVO_SEND_URL,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        method="POST",
        headers={"accept": "application/json", "content-type": "application/json", "api-key": api_key},
    )
    try:
        with urllib.request.urlopen(request, timeout=max(1, min(int(timeout_seconds), 30))) as response:
            raw = response.read(64 * 1024)
            if response.status not in (200, 201, 202):
                return SubmissionResult("FAILED", error_code="UNEXPECTED_PROVIDER_STATUS", http_status=response.status)
        try:
            data = json.loads(raw.decode("utf-8")) if raw else {}
        except (ValueError, UnicodeDecodeError):
            return SubmissionResult("NEEDS_REVIEW", error_code="AMBIGUOUS_PROVIDER_RESPONSE", http_status=200)
        message_id = data.get("messageId") if isinstance(data, dict) else None
        if not message_id:
            # The provider may have accepted the message despite a malformed response; don't blind-retry.
            return SubmissionResult("NEEDS_REVIEW", error_code="MISSING_PROVIDER_MESSAGE_ID", http_status=200)
        return SubmissionResult("SUBMITTED", provider_message_id=str(message_id), http_status=200)
    except urllib.error.HTTPError as exc:
        # Do not log response body/credentials. Respect provider Retry-After hints where supplied.
        code = int(exc.code)
        retry_after_seconds = None
        retry_header = exc.headers.get("Retry-After") if exc.headers else None
        if retry_header:
            try:
                retry_after_seconds = max(1, min(86400, int(retry_header.strip())))
            except (TypeError, ValueError):
                try:
                    retry_at = parsedate_to_datetime(retry_header)
                    if retry_at.tzinfo is None:
                        retry_at = retry_at.replace(tzinfo=timezone.utc)
                    retry_after_seconds = max(1, min(86400, int((retry_at - datetime.now(timezone.utc)).total_seconds())))
                except (TypeError, ValueError, OverflowError):
                    retry_after_seconds = None
        if code == 429 or code >= 500 or code in (408, 425):
            return SubmissionResult("RETRY", error_code=f"HTTP_{code}", http_status=code,
                                    retry_after_seconds=retry_after_seconds)
        return SubmissionResult("FAILED", error_code=f"HTTP_{code}", http_status=code)
    except (TimeoutError, urllib.error.URLError) as exc:
        reason = getattr(exc, "reason", None)
        if isinstance(reason, TimeoutError) or isinstance(exc, TimeoutError):
            return SubmissionResult("NEEDS_REVIEW", error_code="AMBIGUOUS_TIMEOUT")
        # A connection error before HTTP response is ambiguous: conservatively require review.
        return SubmissionResult("NEEDS_REVIEW", error_code="AMBIGUOUS_CONNECTION_FAILURE")
    except Exception:
        return SubmissionResult("NEEDS_REVIEW", error_code="UNEXPECTED_ADAPTER_ERROR")
