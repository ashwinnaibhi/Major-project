import { test } from 'node:test';
import assert from 'node:assert/strict';

function toHospitalSession(data) {
  const rawUser = data?.user || {};
  const role = String(rawUser.role || '').toUpperCase().replace(/^ROLE_/, '');
  if (!data?.token || !rawUser.id) {
    throw new Error('The server did not return a valid account session. Please try again.');
  }
  if (role !== 'HOSPITAL') {
    throw new Error('This account is not registered as a hospital. Please use the matching portal.');
  }
  const profile = data?.hospital_profile || rawUser.hospital_profile || {
    hospital_user_id: Number(rawUser.id),
    hospital_name: rawUser.name || '',
    address: '',
    district: '',
    taluk: '',
    latitude: null,
    longitude: null,
    contact_email: '',
    contact_phone: '',
    needs_setup: true,
  };
  return {
    ...rawUser,
    id: Number(rawUser.id),
    role: 'HOSPITAL',
    token: data.token,
    isLoggedIn: true,
    is_verified: rawUser.is_verified ?? true,
    must_change_password: Boolean(data?.must_change_password ?? rawUser.must_change_password),
    hospital_profile: profile,
    name: profile.hospital_name || rawUser.name,
  };
}

test('toHospitalSession processes dedicated login identity and preserves must_change_password', () => {
  const mockResponse = {
    token: 'jwt_mock_token_12345',
    must_change_password: true,
    user: {
      id: 3,
      name: 'General Hospital Koppa',
      email: 'koppa_ghpc@haemopulse.in',
      role: 'ROLE_HOSPITAL',
      must_change_password: true,
      hospital_profile: {
        hospital_user_id: 3,
        hospital_name: 'General Hospital Koppa',
        taluk: 'Koppa',
        contact_email: 'ashwinkumarns1995@gmail.com',
        contact_phone: '08265-221234'
      }
    }
  };

  const session = toHospitalSession(mockResponse);
  assert.equal(session.id, 3);
  assert.equal(session.role, 'HOSPITAL');
  assert.equal(session.email, 'koppa_ghpc@haemopulse.in');
  assert.equal(session.must_change_password, true);
  assert.equal(session.hospital_profile.contact_email, 'ashwinkumarns1995@gmail.com');
  assert.equal(session.isLoggedIn, true);
});

test('toHospitalSession throws error for non-hospital role', () => {
  const invalidRoleResponse = {
    token: 'jwt_token',
    user: {
      id: 1,
      email: 'donor@example.com',
      role: 'ROLE_DONOR'
    }
  };

  assert.throws(
    () => toHospitalSession(invalidRoleResponse),
    /This account is not registered as a hospital/
  );
});

test('toHospitalSession throws error when session token or id is missing', () => {
  assert.throws(
    () => toHospitalSession({}),
    /The server did not return a valid account session/
  );
  assert.throws(
    () => toHospitalSession({ token: 'jwt' }),
    /The server did not return a valid account session/
  );
});
