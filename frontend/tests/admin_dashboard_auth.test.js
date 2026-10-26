import test from 'node:test';
import assert from 'node:assert/strict';

function checkIsAdmin(currentUser) {
  return Boolean(
    currentUser?.token &&
    currentUser?.isLoggedIn &&
    ['ADMIN', 'ROLE_ADMIN'].includes(String(currentUser?.role || '').toUpperCase().replace(/^ROLE_/, ''))
  );
}

function processAdminLoginResponse(data) {
  if (!data || !data.token) {
    throw new Error(data?.detail || data?.message || 'Invalid administrator email or password.');
  }
  const rawRole = String(data.user?.role || data.role || '').toUpperCase().replace(/^ROLE_/, '');
  if (rawRole !== 'ADMIN') {
    throw new Error('Access denied: this account does not possess administrator credentials.');
  }
  return {
    ...data.user,
    role: 'ADMIN',
    token: data.token,
    isLoggedIn: true
  };
}

function resolveSessionVerification(status, data) {
  if (status === 200 && (data?.authenticated || data?.status === 'ok')) {
    return { verified: true, error: null };
  }
  if (status === 403) {
    return { verified: false, error: 'Access denied: this account does not possess administrator credentials.', clearSession: true };
  }
  return { verified: false, error: 'Session expired or invalid. Please sign in with administrator credentials.', clearSession: true };
}

test('checkIsAdmin strictly accepts only valid tokens with ADMIN role', () => {
  assert.equal(checkIsAdmin({ token: 'jwt.adm', isLoggedIn: true, role: 'ADMIN' }), true);
  assert.equal(checkIsAdmin({ token: 'jwt.adm', isLoggedIn: true, role: 'ROLE_ADMIN' }), true);

  // Rejection of non-admin or unauthenticated roles
  assert.equal(checkIsAdmin({ token: 'jwt.dnr', isLoggedIn: true, role: 'DONOR' }), false);
  assert.equal(checkIsAdmin({ token: 'jwt.dnr', isLoggedIn: true, role: 'ROLE_DONOR' }), false);
  assert.equal(checkIsAdmin({ token: 'jwt.hsp', isLoggedIn: true, role: 'HOSPITAL' }), false);
  assert.equal(checkIsAdmin({ token: 'jwt.hsp', isLoggedIn: true, role: 'ROLE_HOSPITAL' }), false);
  assert.equal(checkIsAdmin({ token: null, isLoggedIn: true, role: 'ADMIN' }), false);
  assert.equal(checkIsAdmin({ token: 'jwt.adm', isLoggedIn: false, role: 'ADMIN' }), false);
  assert.equal(checkIsAdmin(null), false);
});

test('processAdminLoginResponse throws exact access denied error when non-admin credentials used', () => {
  // Donor response payload
  const donorPayload = {
    message: 'Login successful',
    token: 'jwt.dnr',
    role: 'ROLE_DONOR',
    user: { id: 1, email: 'donor@example.com', role: 'ROLE_DONOR' }
  };
  assert.throws(
    () => processAdminLoginResponse(donorPayload),
    /Access denied: this account does not possess administrator credentials\./
  );

  // Hospital response payload
  const hospPayload = {
    message: 'Login successful',
    token: 'jwt.hsp',
    role: 'ROLE_HOSPITAL',
    user: { id: 2, email: 'hospital@example.com', role: 'ROLE_HOSPITAL' }
  };
  assert.throws(
    () => processAdminLoginResponse(hospPayload),
    /Access denied: this account does not possess administrator credentials\./
  );
});

test('processAdminLoginResponse creates correct session for genuine admin', () => {
  const adminPayload = {
    message: 'Login successful',
    token: 'jwt.adm.secret',
    role: 'ROLE_ADMIN',
    user: { id: 10, email: 'admin@haemopulse.in', role: 'ROLE_ADMIN', name: 'Master Admin' }
  };
  const session = processAdminLoginResponse(adminPayload);
  assert.equal(session.role, 'ADMIN');
  assert.equal(session.isLoggedIn, true);
  assert.equal(session.token, 'jwt.adm.secret');
  assert.equal(session.email, 'admin@haemopulse.in');
});

test('resolveSessionVerification flags invalid and expired sessions for removal', () => {
  // 1. Success 200
  const success = resolveSessionVerification(200, { authenticated: true, role: 'ROLE_ADMIN' });
  assert.equal(success.verified, true);
  assert.equal(success.error, null);

  // 2. Forbidden 403 (e.g. donor/hospital token in admin tab)
  const forbidden = resolveSessionVerification(403, { detail: 'Administrator access required' });
  assert.equal(forbidden.verified, false);
  assert.equal(forbidden.clearSession, true);
  assert.equal(forbidden.error, 'Access denied: this account does not possess administrator credentials.');

  // 3. Unauthorized 401 (expired/tampered token)
  const unauthorized = resolveSessionVerification(401, { detail: 'Token expired' });
  assert.equal(unauthorized.verified, false);
  assert.equal(unauthorized.clearSession, true);
  assert.equal(unauthorized.error, 'Session expired or invalid. Please sign in with administrator credentials.');
});
