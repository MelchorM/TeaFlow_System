import mysql from 'mysql2/promise';
import { config } from './config.js';

export const pool = mysql.createPool({ ...config.mysql, database: config.database });
export async function transaction(work) {
  for (let attempt = 0; ; attempt++) {
    const connection = await pool.getConnection();
    try {
      await connection.beginTransaction();
      const result = await work(connection);
      await connection.commit();
      return result;
    } catch (error) {
      await connection.rollback();
      if (attempt < 2 && ['ER_LOCK_DEADLOCK', 'ER_LOCK_WAIT_TIMEOUT'].includes(error.code)) continue;
      throw error;
    } finally { connection.release(); }
  }
}
