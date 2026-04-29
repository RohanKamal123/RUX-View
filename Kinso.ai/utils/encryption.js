const crypto = require('crypto');

const ALGORITHM = 'aes-256-cbc';
const IV_LENGTH = 16; // For AES, this is always 16

// Ensure the secret key is 32 bytes
function getSecretKey() {
  const key = process.env.ENCRYPTION_SECRET_KEY;
  if (!key) {
    throw new Error('ENCRYPTION_SECRET_KEY is not defined in environment variables.');
  }
  // If key is hex string, convert to buffer, otherwise ensure it's correct length or hash it
  if (key.length === 64) { // Assuming hex representation of 32 bytes
      return Buffer.from(key, 'hex');
  }
  // Fallback: create a 32 byte key from the string (not ideal for production but works for simple setup if user provides short string)
  // Better to enforce 32 byte hex in docs.
  return crypto.createHash('sha256').update(String(key)).digest();
}

function encrypt(text) {
  if (!text) return null;
  const iv = crypto.randomBytes(IV_LENGTH);
  const cipher = crypto.createCipheriv(ALGORITHM, getSecretKey(), iv);
  let encrypted = cipher.update(text);
  encrypted = Buffer.concat([encrypted, cipher.final()]);
  return iv.toString('hex') + ':' + encrypted.toString('hex');
}

function decrypt(text) {
  if (!text) return null;
  const textParts = text.split(':');
  const iv = Buffer.from(textParts.shift(), 'hex');
  const encryptedText = Buffer.from(textParts.join(':'), 'hex');
  const decipher = crypto.createDecipheriv(ALGORITHM, getSecretKey(), iv);
  let decrypted = decipher.update(encryptedText);
  decrypted = Buffer.concat([decrypted, decipher.final()]);
  return decrypted.toString();
}

module.exports = { encrypt, decrypt };
