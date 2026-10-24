import { randomBytes, scrypt, timingSafeEqual } from 'node:crypto';
import { promisify } from 'node:util';

const derive = promisify(scrypt);
export async function passwordHash(password) {
  const salt = randomBytes(16).toString('hex');
  const hash = await derive(password, salt, 64);
  return `${salt}:${hash.toString('hex')}`;
}
export async function verifyPassword(password, stored) {
  const [salt, encoded] = (stored || '').split(':');
  if (!salt || !encoded) return false;
  const hash = await derive(password, salt, 64);
  const actual = Buffer.from(encoded, 'hex');
  return actual.length === hash.length && timingSafeEqual(actual, hash);
}
export function equalSecret(left, right) {
  if (!left || !right || typeof left !== 'string' || typeof right !== 'string') return false;
  const a = Buffer.from(left), b = Buffer.from(right);
  return a.length === b.length && timingSafeEqual(a, b);
}
export function regenerate(session) { return new Promise((resolve, reject) => session.regenerate(error => error ? reject(error) : resolve())); }
export function save(session) { return new Promise((resolve, reject) => session.save(error => error ? reject(error) : resolve())); }
