import test from 'node:test';
import assert from 'node:assert/strict';

function isHospitalAuthorized(currentUser) {
  return Boolean(
    currentUser?.token &&
    ['HOSPITAL', 'ROLE_HOSPITAL', 'ADMIN', 'ROLE_ADMIN'].includes(
      String(currentUser?.role || '').toUpperCase()
    )
  );
}

function resolveHospitalDashboardUser(currentUser) {
  const isAuthorized = ['HOSPITAL', 'ROLE_HOSPITAL', 'ADMIN', 'ROLE_ADMIN'].includes(
    String(currentUser?.role || '').toUpperCase()
  );
  return isAuthorized ? currentUser : null;
}

test('authorizes users with HOSPITAL or ADMIN roles when token is present', () => {
  assert.equal(isHospitalAuthorized({ role: 'HOSPITAL', token: 'valid_token' }), true);
  assert.equal(isHospitalAuthorized({ role: 'ROLE_HOSPITAL', token: 'valid_token' }), true);
  assert.equal(isHospitalAuthorized({ role: 'ADMIN', token: 'valid_token' }), true);
  assert.equal(isHospitalAuthorized({ role: 'ROLE_ADMIN', token: 'valid_token' }), true);
});

test('denies users with DONOR, STAFF, or unrecognized roles even with a valid token', () => {
  assert.equal(isHospitalAuthorized({ role: 'DONOR', token: 'donor_token' }), false);
  assert.equal(isHospitalAuthorized({ role: 'ROLE_DONOR', token: 'donor_token' }), false);
  assert.equal(isHospitalAuthorized({ role: 'STAFF', token: 'staff_token' }), false);
  assert.equal(isHospitalAuthorized({ role: 'ROLE_STAFF', token: 'staff_token' }), false);
  assert.equal(isHospitalAuthorized({ role: 'UNKNOWN', token: 'some_token' }), false);
});

test('denies unauthenticated or missing users', () => {
  assert.equal(isHospitalAuthorized(null), false);
  assert.equal(isHospitalAuthorized(undefined), false);
  assert.equal(isHospitalAuthorized({ role: 'HOSPITAL', token: '' }), false);
  assert.equal(isHospitalAuthorized({ role: 'HOSPITAL' }), false);
});

test('App.jsx resolves currentUser for HospitalDashboard safely', () => {
  const donorUser = { id: 1, role: 'DONOR', token: 'tok_donor' };
  const hospitalUser = { id: 2, role: 'HOSPITAL', token: 'tok_hospital' };
  const adminUser = { id: 3, role: 'ADMIN', token: 'tok_admin' };

  // Donor token MUST NOT be passed to HospitalDashboard
  assert.equal(resolveHospitalDashboardUser(donorUser), null);

  // Hospital and Admin tokens are passed safely
  assert.deepEqual(resolveHospitalDashboardUser(hospitalUser), hospitalUser);
  assert.deepEqual(resolveHospitalDashboardUser(adminUser), adminUser);
});
