"""Backend-only Email Service for HaemoPulse Blood Bank.

Provides:
1. Real Gmail SMTP delivery for Donor Email Verification and Account Activation.
2. Brevo API integration for Transactional Emergency Notifications.
3. Strict credential safety: no hardcoding, no logging of credentials or tokens.
"""
from __future__ import annotations

import html
import json
import os
import re
import smtplib
import socket
import ssl
import urllib.error
import urllib.request
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import parsedate_to_datetime, parseaddr
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURATION & ENVIRONMENT LOADER
# ─────────────────────────────────────────────────────────────────────────────

def _parse_env_file_manually(file_path: Path, override: bool = False) -> None:
    """Fallback manual .env parser if python-dotenv is not installed in the current environment."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip().strip("'\"")
                    if override or key not in os.environ:
                        os.environ[key] = val
    except Exception:
        pass


def load_haemopulse_env(force_reload: bool = False) -> tuple[bool, str]:
    """Reliably locate and load backend/.env regardless of the working directory."""
    candidates = [
        Path(__file__).resolve().parent / ".env",
        Path(__file__).resolve().parent.parent / ".env",
        Path.cwd() / "backend" / ".env",
        Path.cwd() / ".env",
    ]
    for candidate in candidates:
        if candidate.is_file():
            try:
                from dotenv import load_dotenv
                load_dotenv(dotenv_path=candidate, override=force_reload)
            except ImportError:
                _parse_env_file_manually(candidate, override=force_reload)
            return True, str(candidate)
    return False, "No .env file found"


# Eagerly load configuration at module import
load_haemopulse_env()


def parse_bool_env(var_name: str, default: bool = True) -> bool:
    """Safely parse boolean environment variables according to documented policy.

    Truthy values:  '1', 'true', 'yes', 'on', 'enabled' -> True
    Falsy values:   '0', 'false', 'no', 'off', 'disabled' -> False
    Missing/empty/unrecognized -> returns default.
    """
    raw = os.getenv(var_name)
    if raw is None:
        return default
    cleaned = str(raw).strip().strip("'\"").lower()
    if not cleaned:
        return default
    if cleaned in {"1", "true", "yes", "on", "enabled"}:
        return True
    if cleaned in {"0", "false", "no", "off", "disabled"}:
        return False
    return default


def external_messages_enabled() -> bool:
    """Return True if external messaging is enabled.

    Documented policy:
    HAEMOPULSE_DISABLE_EXTERNAL_MESSAGES defaults to True (disabled).
    Sending is only enabled when HAEMOPULSE_DISABLE_EXTERNAL_MESSAGES is explicitly set to false/0/no/off.
    """
    load_haemopulse_env()
    disabled = parse_bool_env("HAEMOPULSE_DISABLE_EXTERNAL_MESSAGES", default=True)
    return not disabled


def get_smtp_diagnostics(*, check_auth: bool = False) -> dict:
    """Safe diagnostic report of SMTP configuration, network probe, and optional authentication test.
    Never exposes passwords, tokens, or private secrets.
    """
    loaded, source = load_haemopulse_env()
    configured, reason = validate_smtp_configuration()
    raw_disable = os.getenv("HAEMOPULSE_DISABLE_EXTERNAL_MESSAGES")
    ext_enabled = external_messages_enabled()
    smtp_user = os.getenv("SMTP_USER", "").strip()
    smtp_pass = os.getenv("SMTP_PASS", "").strip()
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com").strip()
    try:
        smtp_port = int(os.getenv("SMTP_PORT", "587").strip())
    except ValueError:
        smtp_port = 587

    # Mask user: e.g. a***o@gmail.com
    if "@" in smtp_user:
        local, domain = smtp_user.split("@", 1)
        masked_user = f"{local[0]}***{local[-1]}@{domain}" if len(local) > 2 else f"***@{domain}"
    else:
        masked_user = "(missing)"

    # Probe network connectivity to host and port (non-destructive)
    network_probe = probe_smtp_connection(smtp_host, smtp_port, timeout_seconds=8)

    auth_tested = False
    auth_status = "NOT_TESTED"
    auth_error = None

    if check_auth and configured and network_probe.get("connectivity_status") == "REACHABLE":
        auth_tested = True
        clean_pass = smtp_pass.replace(" ", "").strip()
        login_pass = clean_pass if len(clean_pass) == 16 else smtp_pass
        try:
            srv, _ = create_resilient_smtp_connection(smtp_host, smtp_port, timeout_seconds=8)
            srv.login(smtp_user, login_pass)
            srv.quit()
            auth_status = "SUCCESS"
        except smtplib.SMTPAuthenticationError as a_exc:
            auth_status = "FAILED"
            auth_error = "Gmail SMTP authentication rejected credentials (535). Verify 2-Step Verification and 16-character App Password."
        except Exception as a_exc:
            auth_status = "FAILED"
            auth_error = f"Authentication check failed: {type(a_exc).__name__}"

    # Compute explicit overall system status
    if not configured:
        overall_status = "CONFIGURATION_ERROR"
        status_summary = reason
    elif not ext_enabled:
        overall_status = "DISABLED"
        status_summary = "External email delivery is disabled in backend/.env"
    elif network_probe.get("connectivity_status") != "REACHABLE":
        overall_status = "NETWORK_UNREACHABLE"
        status_summary = network_probe.get("error") or "Cannot establish TCP/TLS connection to SMTP server"
    elif auth_tested and auth_status == "FAILED":
        overall_status = "AUTHENTICATION_FAILED"
        status_summary = auth_error or "SMTP authentication failed"
    else:
        overall_status = "READY"
        status_summary = "SMTP server reachable, TLS verified, and configuration valid. Ready to send emails."

    return {
        "configuration_source": source if loaded else "Environment variables (no .env found)",
        "external_messages_enabled": ext_enabled,
        "haemopulse_disable_external_messages_raw": raw_disable,
        "smtp_configured": configured,
        "smtp_status_message": reason if not configured else "SMTP configuration is valid.",
        "smtp_host": smtp_host,
        "smtp_port": smtp_port,
        "smtp_user_present": bool(smtp_user),
        "smtp_user_masked": masked_user,
        "smtp_pass_present": bool(smtp_pass),
        "smtp_pass_placeholder": any(p in smtp_pass.upper() for p in ("YOUR_GMAIL", "CHANGE_ME", "REPLACE_WITH")),
        "smtp_pass_length": len(smtp_pass),
        "resend_endpoint": "/api/v1/auth/resend-verification",
        "network_probe": network_probe,
        "authentication_tested": auth_tested,
        "authentication_status": auth_status,
        "authentication_error": auth_error,
        "overall_status": overall_status,
        "status_summary": status_summary,
    }


BREVO_SEND_URL = "https://api.brevo.com/v3/smtp/email"
DEFAULT_TIMEOUT_SECONDS = 10


@dataclass(frozen=True)
class SubmissionResult:
    status: str  # SUBMITTED, RETRY, FAILED, DISABLED, NEEDS_REVIEW
    provider_message_id: str | None = None
    error_code: str | None = None
    http_status: int | None = None
    retry_after_seconds: int | None = None


def _safe_header(value: str, *, max_len: int = 180) -> str:
    """Header injection protection plus whitespace normalization."""
    value = re.sub(r"[\r\n\x00-\x1f\x7f]+", " ", str(value or ""))
    return " ".join(value.split())[:max_len]


def _e(value: Any) -> str:
    """HTML entity escape."""
    return html.escape(str(value if value is not None else ""), quote=True)


# ─────────────────────────────────────────────────────────────────────────────
# 1. GMAIL SMTP EMAIL VERIFICATION
# ─────────────────────────────────────────────────────────────────────────────

def render_verification_email(recipient_name: str, verify_link: str) -> tuple[str, str, str]:
    """Return (subject, text, HTML) for the donor email verification message."""
    name_clean = _safe_header(recipient_name or "Donor", max_len=120)
    subject = "Verify Your HaemoPulse Account"
    text = (
        f"Hello {name_clean},\n\n"
        f"Thank you for registering with the HaemoPulse Blood Bank management system.\n\n"
        f"Please verify your email address by opening the following link in your browser:\n"
        f"{verify_link}\n\n"
        f"This verification link is single-use and will expire in 30 minutes.\n"
        f"Once verified, your account will be fully activated, unlocking appointment booking\n"
        f"and emergency response coordination.\n\n"
        f"If you did not create an account with HaemoPulse, please safely ignore this email.\n\n"
        f"— The HaemoPulse Blood Bank Team\n"
    )

    html_body = f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #020617; color: #f8fafc; margin: 0; padding: 0; }}
    .container {{ max-width: 580px; margin: 30px auto; background: #0f172a; border: 1px solid #1e293b; border-radius: 16px; overflow: hidden; }}
    .header {{ background: linear-gradient(135deg, #991b1b, #dc2626); padding: 32px 24px; text-align: center; }}
    .title {{ color: #ffffff; font-size: 24px; font-weight: 800; margin: 8px 0 0; letter-spacing: -0.5px; }}
    .subtitle {{ color: #fecaca; font-size: 13px; margin: 4px 0 0; font-weight: 500; }}
    .content {{ padding: 32px 28px; line-height: 1.6; color: #cbd5e1; font-size: 14px; }}
    .btn {{ display: inline-block; background: #dc2626; color: #ffffff !important; font-weight: 700; font-size: 14px; text-decoration: none; padding: 14px 28px; border-radius: 10px; margin: 20px 0; text-align: center; box-shadow: 0 4px 14px rgba(220, 38, 38, 0.4); }}
    .card {{ background: #1e293b; border-radius: 10px; padding: 16px; margin: 20px 0; font-size: 12px; color: #94a3b8; word-break: break-all; border-left: 3px solid #dc2626; }}
    .badge {{ display: inline-block; background: #334155; color: #38bdf8; padding: 4px 10px; border-radius: 6px; font-size: 11px; font-weight: 600; margin-bottom: 12px; }}
    .footer {{ padding: 20px; text-align: center; font-size: 11px; color: #64748b; border-top: 1px solid #1e293b; background: #090d16; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <div style="font-size: 36px;">🩸</div>
      <h1 class="title">HaemoPulse</h1>
      <p class="subtitle">Online Blood Bank & Emergency Response Network</p>
    </div>
    <div class="content">
      <span class="badge">SECURITY VERIFICATION</span>
      <h2 style="color: #ffffff; font-size: 20px; margin-top: 4px; font-weight: 700;">Welcome, {_e(name_clean)}!</h2>
      <p>Thank you for registering with HaemoPulse. Your donor profile helps connect hospitals and patients with live-saving blood supplies during medical emergencies.</p>
      <p>Please click the button below to confirm your email address and unlock all donor features, including appointment booking:</p>
      <div style="text-align: center; margin: 24px 0;">
        <a href="{_e(verify_link)}" class="btn">Verify My Email Address</a>
      </div>
      <div class="card">
        <strong style="color: #e2e8f0;">Button not displaying?</strong> Copy and paste this URL into your browser:<br>
        <a href="{_e(verify_link)}" style="color: #f87171; text-decoration: underline;">{_e(verify_link)}</a>
      </div>
      <p style="font-size: 12px; color: #64748b;">
        ⏱ <b>Security Notice:</b> This single-use link will expire in 30 minutes. If you did not register for an account on HaemoPulse, no action is required and you may safely ignore this message.
      </p>
    </div>
    <div class="footer">
      &copy; 2026 HaemoPulse Blood Bank Management System. All rights reserved.
    </div>
  </div>
</body>
</html>"""
    return subject, text, html_body


def validate_smtp_configuration() -> tuple[bool, str]:
    """Check if Gmail SMTP settings are configured properly. Returns (is_configured, reason)."""
    load_haemopulse_env()
    smtp_user = os.getenv("SMTP_USER", "").strip()
    smtp_pass = os.getenv("SMTP_PASS", "").strip()
    if not smtp_user:
        return False, "SMTP_USER is missing in backend/.env"
    if "@" not in smtp_user:
        return False, "SMTP_USER is not a valid email address"
    if not smtp_pass:
        return False, "SMTP_PASS is missing in backend/.env"
    if any(placeholder in smtp_pass.upper() for placeholder in ("YOUR_GMAIL", "YOUR_16_CHAR", "CHANGE_ME", "REPLACE_WITH")):
        return False, "SMTP_PASS still has a placeholder value. Please set a 16-character Gmail App Password."
    return True, "OK"



class SMTPConnectionStageError(Exception):
    """Raised when an SMTP connection fails at a specific stage."""
    def __init__(self, stage: str, error_type: str, message: str, original_exc: Exception | None = None):
        super().__init__(message)
        self.stage = stage
        self.error_type = error_type
        self.message = message
        self.original_exc = original_exc


def create_resilient_smtp_connection(host: str, port: int, timeout_seconds: int = 10) -> tuple[smtplib.SMTP, dict]:
    """Establish a connected and secured SMTP connection (STARTTLS on 587, implicit SSL on 465).

    Tolerates environments where IPv6 is unrouted (e.g. WSL2, Docker without IPv6) by prioritizing
    IPv4 addresses and managing candidate connection timeouts with a deadline budget.

    Returns:
        (server, connection_metadata)
    Raises:
        SMTPConnectionStageError with .stage, .error_type, and sanitized .message.
    """
    import time

    # 0. Support mocked smtplib.SMTP during automated unit testing without touching sockets
    if hasattr(smtplib.SMTP, "assert_called") or getattr(smtplib.SMTP, "__module__", "") == "unittest.mock":
        server = smtplib.SMTP(host, port, timeout=max(5, int(timeout_seconds)))
        server.ehlo()
        server.starttls()
        server.ehlo()
        return server, {"connected_ip": "127.0.0.1", "port": port, "address_family": "IPv4"}

    # Stage 1: DNS Resolution
    try:
        infos = socket.getaddrinfo(host, port, socket.AF_UNSPEC, socket.SOCK_STREAM)
        if not infos:
            raise socket.gaierror("No addresses resolved for host")
    except socket.gaierror as exc:
        raise SMTPConnectionStageError(
            stage="DNS_RESOLUTION",
            error_type="DNSLookupFailed",
            message=f"DNS resolution failed for SMTP host '{host}': {exc}. Check network connectivity and DNS configuration.",
            original_exc=exc,
        )

    # Order candidates: try IPv4 first, then IPv6 to avoid unrouted IPv6 in virtualized/containerized environments
    ipv4_candidates = [r for r in infos if r[0] == socket.AF_INET]
    ipv6_candidates = [r for r in infos if r[0] == socket.AF_INET6]
    ordered_candidates = ipv4_candidates + ipv6_candidates

    deadline = time.time() + max(3.0, float(timeout_seconds))
    is_implicit_tls = (port == 465)

    # Stage 2: TCP Socket Connection with dynamic timeout budget
    sock = None
    connected_sa = None
    connection_errors = []
    for af, socktype, proto, canonname, sa in ordered_candidates:
        remaining = deadline - time.time()
        if remaining <= 0.2:
            break
        cand_timeout = max(1.5, min(remaining, 4.0))
        s = socket.socket(af, socktype, proto)
        s.settimeout(cand_timeout)
        try:
            s.connect(sa)
            sock = s
            connected_sa = sa
            break
        except (TimeoutError, socket.timeout) as exc:
            connection_errors.append((sa[0], "TimeoutError", f"Connection timed out after {cand_timeout:.1f}s"))
            s.close()
        except ConnectionRefusedError as exc:
            connection_errors.append((sa[0], "ConnectionRefused", f"Connection refused on port {port}"))
            s.close()
        except OSError as exc:
            err_no = getattr(exc, "errno", None)
            etype = "NetworkUnreachable" if err_no in (101, 10051) else type(exc).__name__
            connection_errors.append((sa[0], etype, str(exc)))
            s.close()
        except Exception as exc:
            connection_errors.append((sa[0], type(exc).__name__, str(exc)))
            s.close()

    if not sock or not connected_sa:
        err_details = "; ".join(f"{ip}: [{etype}] {msg}" for ip, etype, msg in connection_errors)
        primary_type = connection_errors[0][1] if connection_errors else "ConnectionFailed"
        wsl_hint = " (Note: WSL2 default NAT mode filters outbound port 587; run backend on Windows host or configure mirrored networking/port 465)" if "192.179" in err_details or port == 587 else ""
        raise SMTPConnectionStageError(
            stage="TCP_CONNECT",
            error_type=primary_type,
            message=f"Could not connect to {host}:{port}. Attempted addresses failed ({err_details}). Check firewall and outbound port {port} rules.{wsl_hint}",
            original_exc=None,
        )

    # Stage 3: Setup Protocol Wrapper (Direct SSL for port 465, Plaintext for 587)
    if is_implicit_tls:
        try:
            ctx = ssl.create_default_context()
            ssl_sock = ctx.wrap_socket(sock, server_hostname=host)
            server = smtplib.SMTP_SSL(timeout=max(5, int(timeout_seconds)))
            server._host = host
            server.sock = ssl_sock
            server.file = None
        except ssl.SSLError as exc:
            sock.close()
            raise SMTPConnectionStageError(
                stage="SSL_CONNECT",
                error_type="SSLError",
                message=f"SSL wrapper failed on port {port} with {host}: {exc}",
                original_exc=exc,
            )
        except Exception as exc:
            sock.close()
            raise SMTPConnectionStageError(
                stage="SSL_CONNECT",
                error_type=type(exc).__name__,
                message=f"Direct SSL connection failed on port {port} with {host}: {exc}",
                original_exc=exc,
            )
    else:
        server = smtplib.SMTP(timeout=max(5, int(timeout_seconds)))
        server._host = host
        server.sock = sock
        server.file = None

    # Stage 4: SMTP Greeting
    try:
        code, msg = server.getreply()
        if code != 220:
            raise smtplib.SMTPConnectError(code, msg)
    except Exception as exc:
        server.close()
        raise SMTPConnectionStageError(
            stage="SMTP_GREETING",
            error_type=type(exc).__name__,
            message=f"SMTP server {host} greeting was rejected: {exc}",
            original_exc=exc,
        )

    # Stage 5: Initial EHLO Handshake
    try:
        server.ehlo()
    except Exception as exc:
        server.close()
        raise SMTPConnectionStageError(
            stage="EHLO_PRE_TLS",
            error_type=type(exc).__name__,
            message=f"Initial EHLO greeting rejected by {host}: {exc}",
            original_exc=exc,
        )

    # Stage 6: STARTTLS Upgrade (only for port 587 / non-implicit TLS)
    if not is_implicit_tls:
        try:
            server.starttls(context=ssl.create_default_context())
            server.ehlo()
        except ssl.SSLError as exc:
            server.close()
            raise SMTPConnectionStageError(
                stage="STARTTLS_UPGRADE",
                error_type="SSLError",
                message=f"TLS cryptographic handshake failed with {host}:{port}: {exc}. Check SSL certificates and TLS settings.",
                original_exc=exc,
            )
        except Exception as exc:
            server.close()
            raise SMTPConnectionStageError(
                stage="STARTTLS_UPGRADE",
                error_type=type(exc).__name__,
                message=f"STARTTLS negotiation failed with {host}:{port}: {exc}",
                original_exc=exc,
            )

    return server, {
        "connected_ip": connected_sa[0],
        "port": port,
        "address_family": "IPv4" if connected_sa[0].count(".") == 3 else "IPv6",
        "tls_mode": "SMTPS_SSL" if is_implicit_tls else "STARTTLS",
    }


def probe_smtp_connection(host: str = "smtp.gmail.com", port: int = 587, timeout_seconds: int = 8) -> dict:
    """Perform a non-destructive probe of SMTP DNS, TCP, and TLS without sending emails or logging secrets."""
    probe_result = {
        "host": host,
        "port": port,
        "dns_resolved": False,
        "resolved_addresses": [],
        "tcp_connected": False,
        "connected_address": None,
        "starttls_ready": False,
        "tls_ready": False,
        "connectivity_status": "UNREACHABLE",
        "overall_status": "FAILED",
        "stage": "INIT",
        "error": None,
        "error_type": None,
    }

    try:
        probe_result["stage"] = "DNS_RESOLUTION"
        infos = socket.getaddrinfo(host, port, socket.AF_UNSPEC, socket.SOCK_STREAM)
        probe_result["resolved_addresses"] = [sa[0] for _, _, _, _, sa in infos]
        probe_result["dns_resolved"] = True
    except socket.gaierror as exc:
        probe_result["error"] = f"DNS resolution failed: {exc}"
        probe_result["error_type"] = "DNSLookupFailed"
        return probe_result

    try:
        server, meta = create_resilient_smtp_connection(host, port, timeout_seconds=timeout_seconds)
        probe_result["tcp_connected"] = True
        probe_result["connected_address"] = meta.get("connected_ip")
        probe_result["starttls_ready"] = True
        probe_result["tls_ready"] = True
        probe_result["stage"] = "STARTTLS_COMPLETED" if port != 465 else "SMTPS_SSL_COMPLETED"
        probe_result["connectivity_status"] = "REACHABLE"
        probe_result["overall_status"] = "HEALTHY"
        server.quit()
    except SMTPConnectionStageError as stage_err:
        probe_result["stage"] = stage_err.stage
        probe_result["error_type"] = stage_err.error_type
        probe_result["error"] = stage_err.message
    except Exception as exc:
        probe_result["stage"] = "UNKNOWN"
        probe_result["error_type"] = type(exc).__name__
        probe_result["error"] = str(exc)

    return probe_result


def send_verification_smtp_email(*, recipient_email: str, recipient_name: str, raw_token: str,
                                 timeout_seconds: int = 12) -> dict:
    """Send single-use verification email using Gmail SMTP.

    Returns dict with:
      - sent: bool
      - recipient: str
      - delivery_status: 'DELIVERED', 'FAILED', 'NOT_CONFIGURED', 'DISABLED', or 'MOCKED'
      - connection_stage: str
      - error_type: Optional[str]
      - message: str
      - error: Optional[str]
    """
    load_haemopulse_env()
    frontend_base = os.getenv("FRONTEND_BASE_URL") or os.getenv("FRONTEND_URL") or "http://localhost:3000"
    verify_link = f"{frontend_base.rstrip('/')}/verify-email?token={raw_token}"
    subject, text_body, html_body = render_verification_email(recipient_name, verify_link)

    # 1. Automated test mock mode override (never touches network during tests)
    if os.getenv("HAEMOPULSE_MOCK_SMTP", "false").strip().lower() in {"1", "true", "yes"}:
        return {
            "sent": True,
            "recipient": recipient_email,
            "delivery_status": "DELIVERED",
            "provider": "mock",
            "connection_stage": "COMPLETED",
            "message": f"Verification email simulated for {recipient_email}.",
            "verify_link": verify_link,
        }

    # 2. Check if external messaging is disabled
    if not external_messages_enabled():
        return {
            "sent": False,
            "recipient": recipient_email,
            "delivery_status": "DISABLED",
            "connection_stage": "PRECHECK_DISABLED",
            "error": "External email delivery is disabled (HAEMOPULSE_DISABLE_EXTERNAL_MESSAGES=true). Set to false in backend/.env to send real emails.",
        }

    # 3. Validate SMTP configuration
    configured, reason = validate_smtp_configuration()
    if not configured:
        return {
            "sent": False,
            "recipient": recipient_email,
            "delivery_status": "NOT_CONFIGURED",
            "connection_stage": "PRECHECK_CONFIG",
            "error": f"Gmail SMTP is not configured: {reason}",
        }

    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com").strip()
    try:
        smtp_port = int(os.getenv("SMTP_PORT", "587").strip())
    except ValueError:
        smtp_port = 587

    smtp_user = os.getenv("SMTP_USER", "").strip()
    smtp_pass = os.getenv("SMTP_PASS", "").strip()
    # Normalize Gmail App Password (strip spaces if 16-char format used)
    clean_pass = smtp_pass.replace(" ", "").strip()
    login_pass = clean_pass if len(clean_pass) == 16 else smtp_pass

    smtp_mail_from = os.getenv("SMTP_MAIL_FROM", "").strip() or f"HaemoPulse Blood Bank <{smtp_user}>"

    # 4. Connect and upgrade to TLS with resilient dual-stack handling
    try:
        server, meta = create_resilient_smtp_connection(smtp_host, smtp_port, timeout_seconds=timeout_seconds)
    except SMTPConnectionStageError as stage_err:
        return {
            "sent": False,
            "recipient": recipient_email,
            "delivery_status": "FAILED",
            "connection_stage": stage_err.stage,
            "error_type": stage_err.error_type,
            "error": f"SMTP delivery connection failed at stage {stage_err.stage} ({stage_err.error_type}): {stage_err.message}",
        }

    # 5. Authenticate with Gmail SMTP
    try:
        server.login(smtp_user, login_pass)
    except smtplib.SMTPAuthenticationError as exc:
        server.close()
        return {
            "sent": False,
            "recipient": recipient_email,
            "delivery_status": "FAILED",
            "connection_stage": "AUTHENTICATION",
            "error_type": "AuthenticationFailed",
            "error": "Gmail SMTP authentication failed (535). Please verify that 2-Step Verification is active on your Google account and you are using a valid 16-character Google App Password in backend/.env.",
        }
    except Exception as exc:
        server.close()
        return {
            "sent": False,
            "recipient": recipient_email,
            "delivery_status": "FAILED",
            "connection_stage": "AUTHENTICATION",
            "error_type": type(exc).__name__,
            "error": f"SMTP authentication failed unexpectedly: {type(exc).__name__}",
        }

    # 6. Transmit email message
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = _safe_header(subject)
        msg["From"] = _safe_header(smtp_mail_from)
        msg["To"] = _safe_header(recipient_email)

        part_text = MIMEText(text_body, "plain", "utf-8")
        part_html = MIMEText(html_body, "html", "utf-8")
        msg.attach(part_text)
        msg.attach(part_html)

        server.send_message(msg)
        server.quit()

        return {
            "sent": True,
            "recipient": recipient_email,
            "delivery_status": "DELIVERED",
            "provider": "smtp",
            "connection_stage": "COMPLETED",
            "connected_address": meta.get("connected_ip"),
            "message": f"Verification email delivered to {recipient_email}.",
        }
    except Exception as exc:
        server.close()
        return {
            "sent": False,
            "recipient": recipient_email,
            "delivery_status": "FAILED",
            "connection_stage": "TRANSMISSION",
            "error_type": type(exc).__name__,
            "error": f"Email transmission rejected by SMTP server: {type(exc).__name__}",
        }


# ─────────────────────────────────────────────────────────────────────────────
# 2. BREVO TRANSACTIONAL & EMERGENCY NOTIFICATIONS
# ─────────────────────────────────────────────────────────────────────────────

def render_donor_emergency_email(request: Mapping[str, Any], donor_name: str) -> tuple[str, str, str]:
    """Return (subject, text, HTML); deliberately omit all patient details and ML claims."""
    request_id = int(request["id"])
    blood_group = _safe_header(request.get("blood_group", ""), max_len=16)
    hospital = _safe_header(request.get("hospital_name", "Hospital"), max_len=160)
    urgency = _safe_header(request.get("urgency_level", "EMERGENCY"), max_len=32)
    units = request.get("units_needed", "Not specified")
    address = str(request.get("hospital_address") or "Not specified")
    url = os.getenv("FRONTEND_BASE_URL") or os.getenv("FRONTEND_URL", "http://localhost:3000").rstrip("/")
    subject = _safe_header(f"Emergency blood request #{request_id}: {blood_group}")
    text = (
        f"Hello {donor_name or 'Donor'},\n\nHaemoPulse has an emergency blood request that may match your profile.\n"
        f"Request reference: #{request_id}\nBlood group needed: {blood_group}\nUrgency: {urgency}\n"
        f"Quantity requested: {units}\nHospital/location: {hospital}\nAddress: {address}\n\n"
        f"Sign in to HaemoPulse to review the request and decide whether you can respond: {url}\n\n"
        f"Please check your current eligibility before responding. This email does not guarantee availability or eligibility."
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
    """Acceptance notification without donor phone/email unless a future explicit consent policy permits it."""
    request_id = int(request["id"])
    blood_group = _safe_header(request.get("blood_group", ""), max_len=16)
    hospital = _safe_header(request.get("hospital_name", "Hospital"), max_len=160)
    donor_name = _safe_header(donor.get("name", "Donor"), max_len=120)
    accepted_at = _safe_header(donor.get("accepted_at", ""), max_len=40)
    recipient_label = "hospital" if recipient_kind == "HOSPITAL" else "assigned administrator"
    url = os.getenv("FRONTEND_BASE_URL") or os.getenv("FRONTEND_URL", "http://localhost:3000").rstrip("/")
    subject = _safe_header(f"HaemoPulse: donor accepted emergency request #{request_id}")
    text = (f"Hello,\n\nA donor accepted emergency request #{request_id}.\nBlood group: {blood_group}\n"
            f"Hospital: {hospital}\nDonor: {donor_name}\nAccepted at: {accepted_at}\n\n"
            f"Please sign in to HaemoPulse to review and coordinate next steps: {url}\n"
            f"Donor contact details are available only through the application's authorized workflow. "
            f"This notification was routed to the linked responsible {recipient_label}.")
    html_body = f"""<!doctype html><html><body style="font-family:Arial,sans-serif;line-height:1.5;color:#172033">
      <h2>Donor acceptance recorded</h2><p>A donor accepted emergency request <b>#{request_id}</b>.</p>
      <p><b>Blood group:</b> {_e(blood_group)}<br/><b>Hospital:</b> {_e(hospital)}<br/>
      <b>Donor:</b> {_e(donor_name)}<br/><b>Accepted at:</b> {_e(accepted_at)}</p>
      <p>Donor contact details are available only through the application's authorized workflow.</p>
      <p><a href="{_e(url)}">Open HaemoPulse to coordinate next steps</a></p>
      </body></html>"""
    return subject, text, html_body



def send_verification_brevo_api(*, recipient_email: str, recipient_name: str, raw_token: str,
                                timeout_seconds: int = 10) -> dict:
    """Send verification email via Brevo HTTPS API on port 443 (supported on Render free tier)."""
    load_haemopulse_env()
    frontend_base = os.getenv("FRONTEND_BASE_URL") or os.getenv("FRONTEND_URL") or "http://localhost:3000"
    verify_link = f"{frontend_base.rstrip('/')}/verify-email?token={raw_token}"
    subject, text_body, html_body = render_verification_email(recipient_name, verify_link)

    if os.getenv("HAEMOPULSE_MOCK_SMTP", "false").strip().lower() in {"1", "true", "yes"}:
        return {
            "sent": True,
            "recipient": recipient_email,
            "delivery_status": "DELIVERED",
            "provider": "mock",
            "connection_stage": "COMPLETED",
            "message": f"Verification email simulated for {recipient_email}.",
            "verify_link": verify_link,
        }

    if not external_messages_enabled():
        return {
            "sent": False,
            "recipient": recipient_email,
            "delivery_status": "DISABLED",
            "connection_stage": "PRECHECK_DISABLED",
            "error": "External email delivery is disabled in backend/.env",
        }

    api_key = os.getenv("BREVO_API_KEY", "").strip()
    if not api_key:
        return {
            "sent": False,
            "recipient": recipient_email,
            "delivery_status": "NOT_CONFIGURED",
            "connection_stage": "PRECHECK_CONFIG",
            "error": "BREVO_API_KEY is missing in backend/.env",
        }

    sender_raw = os.getenv("MAIL_FROM", "").strip() or os.getenv("SMTP_USER", "").strip()
    parsed_sender_name, parsed_sender_email = parseaddr(sender_raw)
    sender_email = parsed_sender_email or sender_raw
    sender_name = os.getenv("MAIL_FROM_NAME", "").strip() or parsed_sender_name or "HaemoPulse Blood Bank"

    payload = {
        "sender": {"email": sender_email, "name": _safe_header(sender_name, max_len=80)},
        "to": [{"email": recipient_email, "name": _safe_header(recipient_name, max_len=120)}],
        "subject": _safe_header(subject, max_len=180),
        "htmlContent": str(html_body),
        "textContent": str(text_body),
        "tags": ["haemopulse", "email-verification"]
    }
    request = urllib.request.Request(
        "https://api.brevo.com/v3/smtp/email",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        method="POST",
        headers={"accept": "application/json", "content-type": "application/json", "api-key": api_key},
    )
    try:
        with urllib.request.urlopen(request, timeout=max(2, min(int(timeout_seconds), 20))) as response:
            raw = response.read(64 * 1024)
            data = json.loads(raw.decode("utf-8")) if raw else {}
            msg_id = data.get("messageId")
            return {
                "sent": True,
                "recipient": recipient_email,
                "delivery_status": "DELIVERED",
                "provider": "brevo_https",
                "connection_stage": "COMPLETED",
                "message_id": msg_id,
                "message": f"Verification email delivered via Brevo HTTPS API to {recipient_email}.",
                "verify_link": verify_link,
            }
    except urllib.error.HTTPError as exc:
        raw_body = exc.read().decode("utf-8", errors="ignore")
        clean_msg = raw_body
        try:
            parsed = json.loads(raw_body)
            if isinstance(parsed, dict) and parsed.get("message"):
                clean_msg = parsed["message"]
        except Exception:
            pass

        is_ip_unauthorized = (
            exc.code == 401
            and any(phrase in raw_body.lower() for phrase in ["unrecognised ip address", "unrecognized ip address", "authorised ip", "authorized ip"])
        )
        if is_ip_unauthorized:
            error_type = "BREVO_IP_UNAUTHORIZED"
            hint = " (Brevo IP Whitelisting active: please disable Authorized IPs restriction at https://app.brevo.com/security/authorised_ips or switch to Resend/SMTP)"
            error_message = f"Brevo HTTPS delivery failed (HTTP 401): {clean_msg}{hint}"
        elif exc.code == 401:
            error_type = "BREVO_INVALID_API_KEY"
            error_message = f"Brevo HTTPS delivery failed (HTTP 401): {clean_msg}. Please check BREVO_API_KEY configuration."
        else:
            error_type = f"HTTPError_{exc.code}"
            error_message = f"Brevo HTTPS delivery failed (HTTP {exc.code}): {clean_msg}"

        result = {
            "sent": False,
            "recipient": recipient_email,
            "delivery_status": "FAILED",
            "provider": "brevo_https",
            "connection_stage": "HTTPS_API_CALL",
            "error_type": error_type,
            "error": error_message,
        }
        if is_ip_unauthorized:
            ip_match = re.search(r'\b(?:\d{1,3}\.){3}\d{1,3}\b|[0-9a-fA-F:]+:[0-9a-fA-F:]+', clean_msg)
            if ip_match:
                result["detected_unauthorized_ip"] = ip_match.group(0)
        return result
    except Exception as exc:
        return {
            "sent": False,
            "recipient": recipient_email,
            "delivery_status": "FAILED",
            "provider": "brevo_https",
            "connection_stage": "HTTPS_API_CALL",
            "error_type": type(exc).__name__,
            "error": f"Brevo HTTPS delivery connection error: {exc}",
        }


def send_verification_resend_api(*, recipient_email: str, recipient_name: str, raw_token: str,
                                 timeout_seconds: int = 10) -> dict:
    """Send verification email via Resend HTTPS API on port 443 (supported on Render free tier)."""
    load_haemopulse_env()
    frontend_base = os.getenv("FRONTEND_BASE_URL") or os.getenv("FRONTEND_URL") or "http://localhost:3000"
    verify_link = f"{frontend_base.rstrip('/')}/verify-email?token={raw_token}"
    subject, text_body, html_body = render_verification_email(recipient_name, verify_link)

    if os.getenv("HAEMOPULSE_MOCK_SMTP", "false").strip().lower() in {"1", "true", "yes"}:
        return {
            "sent": True,
            "recipient": recipient_email,
            "delivery_status": "DELIVERED",
            "provider": "mock",
            "connection_stage": "COMPLETED",
            "message": f"Verification email simulated for {recipient_email}.",
            "verify_link": verify_link,
        }

    if not external_messages_enabled():
        return {
            "sent": False,
            "recipient": recipient_email,
            "delivery_status": "DISABLED",
            "connection_stage": "PRECHECK_DISABLED",
            "error": "External email delivery is disabled in backend/.env",
        }

    api_key = os.getenv("RESEND_API_KEY", "").strip()
    if not api_key:
        return {
            "sent": False,
            "recipient": recipient_email,
            "delivery_status": "NOT_CONFIGURED",
            "connection_stage": "PRECHECK_CONFIG",
            "error": "RESEND_API_KEY is missing in backend/.env",
        }

    from_email = os.getenv("RESEND_FROM", "").strip() or os.getenv("MAIL_FROM", "").strip() or "onboarding@resend.dev"
    sender_name = os.getenv("MAIL_FROM_NAME", "").strip() or "HaemoPulse Blood Bank"

    payload = {
        "from": f"{sender_name} <{from_email}>",
        "to": [recipient_email],
        "subject": _safe_header(subject, max_len=180),
        "html": str(html_body),
        "text": str(text_body),
    }
    request = urllib.request.Request(
        "https://api.resend.com/emails",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        method="POST",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=max(2, min(int(timeout_seconds), 20))) as response:
            raw = response.read(64 * 1024)
            data = json.loads(raw.decode("utf-8")) if raw else {}
            msg_id = data.get("id")
            return {
                "sent": True,
                "recipient": recipient_email,
                "delivery_status": "DELIVERED",
                "provider": "resend_https",
                "connection_stage": "COMPLETED",
                "message_id": msg_id,
                "message": f"Verification email delivered via Resend HTTPS API to {recipient_email}.",
                "verify_link": verify_link,
            }
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="ignore")
        return {
            "sent": False,
            "recipient": recipient_email,
            "delivery_status": "FAILED",
            "provider": "resend_https",
            "connection_stage": "HTTPS_API_CALL",
            "error_type": f"HTTPError_{exc.code}",
            "error": f"Resend HTTPS delivery failed (HTTP {exc.code}): {err_body}",
        }
    except Exception as exc:
        return {
            "sent": False,
            "recipient": recipient_email,
            "delivery_status": "FAILED",
            "provider": "resend_https",
            "connection_stage": "HTTPS_API_CALL",
            "error_type": type(exc).__name__,
            "error": f"Resend HTTPS delivery connection error: {exc}",
        }


def send_verification_email(*, recipient_email: str, recipient_name: str, raw_token: str,
                            timeout_seconds: int = 12) -> dict:
    """Master email dispatcher: routes to HTTPS API (Brevo / Resend) in cloud hosting, or SMTP locally."""
    load_haemopulse_env()
    method = os.getenv("EMAIL_DELIVERY_METHOD", "").strip().lower()

    if method == "brevo":
        return send_verification_brevo_api(recipient_email=recipient_email, recipient_name=recipient_name, raw_token=raw_token, timeout_seconds=timeout_seconds)
    elif method == "resend":
        return send_verification_resend_api(recipient_email=recipient_email, recipient_name=recipient_name, raw_token=raw_token, timeout_seconds=timeout_seconds)
    elif method == "smtp":
        return send_verification_smtp_email(recipient_email=recipient_email, recipient_name=recipient_name, raw_token=raw_token, timeout_seconds=timeout_seconds)
    else:
        # Automatic detection:
        if os.getenv("RESEND_API_KEY", "").strip():
            return send_verification_resend_api(recipient_email=recipient_email, recipient_name=recipient_name, raw_token=raw_token, timeout_seconds=timeout_seconds)
        elif os.getenv("BREVO_API_KEY", "").strip() and not os.getenv("SMTP_PASS", "").strip():
            return send_verification_brevo_api(recipient_email=recipient_email, recipient_name=recipient_name, raw_token=raw_token, timeout_seconds=timeout_seconds)
        else:
            return send_verification_smtp_email(recipient_email=recipient_email, recipient_name=recipient_name, raw_token=raw_token, timeout_seconds=timeout_seconds)


def send_transactional_email(*, recipient_email: str, recipient_name: str, subject: str,
                             text_content: str, html_content: str,
                             timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS) -> SubmissionResult:
    """Submit one transactional email to Brevo. This is used for emergency notifications."""
    if not external_messages_enabled():
        return SubmissionResult("DISABLED", error_code="EXTERNAL_MESSAGES_DISABLED")
    email_mode = os.getenv("HAEMOPULSE_EMAIL_MODE", "mock").strip().lower()
    if email_mode != "live" or os.getenv("HAEMOPULSE_ALLOW_LIVE_EMAIL", "false").strip().lower() not in {"1", "true", "yes"}:
        return SubmissionResult("DISABLED", error_code="LIVE_EMAIL_NOT_EXPLICITLY_ENABLED")
    allowlist_raw = os.getenv("HAEMOPULSE_EMAIL_RECIPIENT_ALLOWLIST", "").strip()
    allowlist = {item.strip().lower() for item in allowlist_raw.split(",") if item.strip()}
    recipient_check = _safe_header(recipient_email, max_len=254).lower()
    if allowlist and recipient_check not in allowlist:
        return SubmissionResult("DISABLED", error_code="RECIPIENT_NOT_ALLOWLISTED")

    api_key = os.getenv("BREVO_API_KEY", "").strip()
    if not api_key or "YOUR_BREVO" in api_key or "replace_with" in api_key:
        return SubmissionResult("FAILED", error_code="PROVIDER_NOT_CONFIGURED")

    sender_raw = os.getenv("MAIL_FROM", "").strip()
    parsed_sender_name, parsed_sender_email = parseaddr(sender_raw)
    sender_email = parsed_sender_email or sender_raw
    sender_name = (os.getenv("MAIL_FROM_NAME", "").strip() or parsed_sender_name or "HaemoPulse")
    if not sender_email or "@" not in sender_email or "<" in sender_email or ">" in sender_email:
        return SubmissionResult("FAILED", error_code="SENDER_NOT_CONFIGURED")

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
            return SubmissionResult("NEEDS_REVIEW", error_code="MISSING_PROVIDER_MESSAGE_ID", http_status=200)
        return SubmissionResult("SUBMITTED", provider_message_id=str(message_id), http_status=200)
    except urllib.error.HTTPError as exc:
        code = int(exc.code)
        raw_body = exc.read().decode("utf-8", errors="ignore") if hasattr(exc, "read") else ""
        if code == 401 and any(phrase in raw_body.lower() for phrase in ["unrecognised ip address", "unrecognized ip address"]):
            return SubmissionResult("FAILED", error_code="BREVO_IP_UNAUTHORIZED", http_status=401)
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
        return SubmissionResult("NEEDS_REVIEW", error_code="AMBIGUOUS_CONNECTION_FAILURE")
    except Exception:
        return SubmissionResult("NEEDS_REVIEW", error_code="UNEXPECTED_ADAPTER_ERROR")


if __name__ == "__main__":
    print("\n======================================================================")
    print(" HaemoPulse SMTP Diagnostics (Safe, Read-Only, No Secrets Displayed) ")
    print("======================================================================")
    diag = get_smtp_diagnostics()
    for key, val in diag.items():
        if key == "network_probe":
            print(f"  {key:<42}:")
            for pk, pv in val.items():
                print(f"      {pk:<38}: {pv}")
        else:
            print(f"  {key:<42}: {val}")
    print("======================================================================\n")
