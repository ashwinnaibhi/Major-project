import test from 'node:test';
import assert from 'node:assert/strict';

function normalizeRole(role) {
  if (!role) return 'DONOR';
  const value = String(role).toUpperCase();
  const trimmed = value.startsWith('ROLE_') ? value.slice(5) : value;
  return ['ADMIN', 'HOSPITAL', 'DONOR', 'STAFF'].includes(trimmed) ? trimmed : 'DONOR';
}

function checkIsAdmin(currentUser) {
  return Boolean(
    currentUser?.token &&
    currentUser?.isLoggedIn &&
    ['ADMIN', 'ROLE_ADMIN'].includes(String(currentUser?.role || '').toUpperCase())
  );
}

function partitionHospitalRequests(requestsList = []) {
  const pendingRequests = requestsList.filter(r => (r.status || 'PENDING') === 'PENDING');
  const fulfilledRequests = requestsList.filter(r => r.status === 'FULFILLED' || r.status === 'APPROVED' || r.status === 'ALLOCATED');
  return { pendingRequests, fulfilledRequests };
}

test('normalizeRole defaults safely to DONOR and never auto-promotes unknown roles to ADMIN', () => {
  assert.equal(normalizeRole(null), 'DONOR');
  assert.equal(normalizeRole(undefined), 'DONOR');
  assert.equal(normalizeRole(''), 'DONOR');
  assert.equal(normalizeRole('UNKNOWN_GUEST'), 'DONOR');
  assert.equal(normalizeRole('PUBLIC_USER'), 'DONOR');
});

test('normalizeRole correctly identifies ADMIN, HOSPITAL, and STAFF roles', () => {
  assert.equal(normalizeRole('ADMIN'), 'ADMIN');
  assert.equal(normalizeRole('ROLE_ADMIN'), 'ADMIN');
  assert.equal(normalizeRole('HOSPITAL'), 'HOSPITAL');
  assert.equal(normalizeRole('ROLE_HOSPITAL'), 'HOSPITAL');
  assert.equal(normalizeRole('STAFF'), 'STAFF');
  assert.equal(normalizeRole('ROLE_STAFF'), 'STAFF');
  assert.equal(normalizeRole('DONOR'), 'DONOR');
  assert.equal(normalizeRole('ROLE_DONOR'), 'DONOR');
});

test('checkIsAdmin strictly requires token, isLoggedIn, and ADMIN/ROLE_ADMIN role', () => {
  assert.equal(checkIsAdmin({ token: 'jwt123', isLoggedIn: true, role: 'ADMIN' }), true);
  assert.equal(checkIsAdmin({ token: 'jwt123', isLoggedIn: true, role: 'ROLE_ADMIN' }), true);

  // Rejected non-admin roles
  assert.equal(checkIsAdmin({ token: 'jwt123', isLoggedIn: true, role: 'DONOR' }), false);
  assert.equal(checkIsAdmin({ token: 'jwt123', isLoggedIn: true, role: 'ROLE_DONOR' }), false);
  assert.equal(checkIsAdmin({ token: 'jwt123', isLoggedIn: true, role: 'HOSPITAL' }), false);
  assert.equal(checkIsAdmin({ token: 'jwt123', isLoggedIn: true, role: 'ROLE_HOSPITAL' }), false);

  // Missing credentials
  assert.equal(checkIsAdmin({ isLoggedIn: true, role: 'ADMIN' }), false);
  assert.equal(checkIsAdmin({ token: 'jwt123', isLoggedIn: false, role: 'ADMIN' }), false);
  assert.equal(checkIsAdmin(null), false);
});

test('partitionHospitalRequests separates pending requisitions from fulfilled archive', () => {
  const requests = [
    { id: 1, blood_group: 'A+', units_needed: 3, units_fulfilled: 0, status: 'PENDING' },
    { id: 2, blood_group: 'B+', units_needed: 2, units_fulfilled: 1, status: 'PENDING' }, // partially fulfilled
    { id: 3, blood_group: 'O-', units_needed: 4, units_fulfilled: 4, status: 'FULFILLED', fulfilled_at: '2026-10-26 12:00:00' },
    { id: 4, blood_group: 'AB+', units_needed: 1, units_fulfilled: 1, status: 'APPROVED' },
  ];

  const { pendingRequests, fulfilledRequests } = partitionHospitalRequests(requests);

  assert.equal(pendingRequests.length, 2);
  assert.deepEqual(pendingRequests.map(r => r.id), [1, 2]);

  assert.equal(fulfilledRequests.length, 2);
  assert.deepEqual(fulfilledRequests.map(r => r.id), [3, 4]);

  // Request #3 (FULFILLED) must be completely excluded from pending
  assert.ok(!pendingRequests.some(r => r.id === 3));
});
