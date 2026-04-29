# Secure Unified Inbox Backend (Phase 1)

This is the backend core for the Secure Unified Inbox project. It handles Google OAuth 2.0 authentication and securely stores user credentials.

## Prerequisites

- Node.js installed
- A Google Cloud Project with OAuth 2.0 credentials

## Setup

1.  **Install Dependencies**:
    ```bash
    npm install
    ```

2.  **Environment Configuration**:
    - Copy `.env.example` to `.env`:
      ```bash
      cp .env.example .env
      ```
    - Fill in the `.env` file with your credentials:
      - `GOOGLE_CLIENT_ID`: From Google Cloud Console.
      - `GOOGLE_CLIENT_SECRET`: From Google Cloud Console.
      - `ENCRYPTION_SECRET_KEY`: A 32-byte hex string (64 characters) or a strong secret string.
      - `REDIRECT_URI`: Ensure this matches what is set in Google Cloud Console (default: `http://localhost:3000/auth/google/callback`).

3.  **Run the Server**:
    ```bash
    npm start
    ```

## Usage

1.  Open your browser and navigate to `http://localhost:3000/auth/google`.
2.  Sign in with your Google account and grant permissions.
3.  Upon success, you will see a "Connection Successful" message.
4.  Check `users.json` in the project root to see the stored (encrypted) user data.

## Security

- Refresh tokens are encrypted using AES-256-CBC before storage.
- The encryption key is managed via environment variables.
