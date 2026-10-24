export class AppError extends Error {
  constructor(message, status = 422) { super(message); this.status = status; }
}
export function requireValue(condition, message, status = 422) {
  if (!condition) throw new AppError(message, status);
}
export function id(value) {
  const result = Number(value);
  requireValue(Number.isSafeInteger(result) && result > 0, 'Invalid record identifier.');
  return result;
}
export function amount(value, precision = 2) {
  const digits = precision === 2 ? 4 : 6;
  requireValue(new RegExp(`^\\d{1,${digits}}(\\.\\d{1,${precision}})?$`).test(String(value)), 'Enter a valid non-negative amount within the allowed range.');
  const [whole, fraction = ''] = String(value).split('.');
  return Number(whole) * 10 ** precision + Number(fraction.padEnd(precision, '0'));
}
