import test from 'node:test';
import assert from 'node:assert/strict';

/**
 * Pure simulation of handleResendEmail response processing logic
 * mirroring DonorDashboard.jsx
 */
function processResendResponse(res, data, targetEmail) {
  if (res.ok && data.success && data.delivery?.sent) {
    return {
      cooldown: 60,
      status: data.message || `Verification email delivered to ${targetEmail}. Please check your inbox or spam folder.`,
      isError: false,
    };
  } else if (res.status === 429) {
    return {
      cooldown: 30,
      status: data.detail || 'Rate limit: Please wait for the cooldown timer before requesting another email.',
      isError: true,
    };
  } else {
    return {
      cooldown: 15,
      status: data.detail || data.message || data.delivery?.error || 'Verification email delivery failed. Please check backend email configuration.',
      isError: true,
    };
  }
}

test('successful resend email sets 60s cooldown and clean success status', () => {
  const res = { ok: true, status: 200 };
  const data = {
    success: true,
    message: 'Verification email delivered to donor@example.com.',
    delivery: { sent: true, delivery_status: 'DELIVERED' }
  };
  const state = processResendResponse(res, data, 'donor@example.com');
  assert.equal(state.cooldown, 60);
  assert.equal(state.isError, false);
  assert.match(state.status, /delivered to donor@example\.com/);
});

test('Brevo HTTP 502 unauthorized IP error sets error state and actionable message without claiming success', () => {
  const res = { ok: false, status: 502 };
  const data = {
    success: false,
    detail: "Email delivery failed: Brevo rejected the connection because the server outbound IP is not authorized. The administrator must disable the 'Authorized IPs' restriction at https://app.brevo.com/security/authorised_ips in the Brevo dashboard.",
    delivery: {
      sent: false,
      delivery_status: 'FAILED',
      error_type: 'BREVO_IP_UNAUTHORIZED',
      detected_unauthorized_ip: '74.220.48.235'
    }
  };
  const state = processResendResponse(res, data, 'donor@example.com');
  assert.equal(state.cooldown, 15);
  assert.equal(state.isError, true);
  assert.match(state.status, /Authorized IPs/);
  assert.doesNotMatch(state.status, /delivered/i);
});

test('Rate limit HTTP 429 displays cooldown rate limit notice', () => {
  const res = { ok: false, status: 429 };
  const data = { detail: 'Please wait 45 seconds before requesting another verification email.' };
  const state = processResendResponse(res, data, 'donor@example.com');
  assert.equal(state.cooldown, 30);
  assert.equal(state.isError, true);
  assert.match(state.status, /45 seconds/);
});
