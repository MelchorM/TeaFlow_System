import dotenv from 'dotenv';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

export const backendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
export const webRoot = path.dirname(backendRoot);
export const root = path.dirname(webRoot);
dotenv.config({ path: path.join(backendRoot, '.env'), quiet: true });
export const config = {
  host: process.env.HOST || '127.0.0.1',
  port: Number(process.env.PORT || 3000),
  database: process.env.DB_NAME || 'teaflow',
  sessionSecret: process.env.SESSION_SECRET,
  cashierKey: process.env.CASHIER_DEVICE_KEY || '',
  kitchenKey: process.env.KITCHEN_DEVICE_KEY || '',
  sampleRecipes: process.env.SAMPLE_RECIPES !== 'false',
  mysql: {
    host: process.env.DB_HOST || '127.0.0.1', port: Number(process.env.DB_PORT || 3306),
    user: process.env.DB_USER || 'root', password: process.env.DB_PASSWORD || '',
    connectionLimit: 8, timezone: 'Z', charset: 'utf8mb4',
    supportBigNumbers: true, bigNumberStrings: false, multipleStatements: false,
  },
};
