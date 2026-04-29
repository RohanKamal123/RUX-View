const express = require('express');
const { google } = require('googleapis');
const { encrypt } = require('../utils/encryption');
const { saveUser } = require('../utils/db');
const router = express.Router();

// Load environment variables
const CLIENT_ID = process.env.GOOGLE_CLIENT_ID;
const CLIENT_SECRET = process.env.GOOGLE_CLIENT_SECRET;
const REDIRECT_URI = process.env.REDIRECT_URI || 'http://localhost:3000/auth/google/callback';

const oauth2Client = new google.auth.OAuth2(
    CLIENT_ID,
    CLIENT_SECRET,
    REDIRECT_URI
);

// Scopes for reading mail and modifying (for push notifications/labels)
const SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/userinfo.email' // To get user email
];

// Route to initiate Google OAuth flow
router.get('/google', (req, res) => {
    const authUrl = oauth2Client.generateAuthUrl({
        access_type: 'offline', // Crucial for getting a refresh token
        scope: SCOPES,
        prompt: 'consent' // Force consent to ensure refresh token is returned
    });
    res.redirect(authUrl);
});

// Callback route to handle the response from Google
router.get('/google/callback', async (req, res) => {
    const { code } = req.query;

    if (!code) {
        return res.status(400).send('Authorization code missing.');
    }

    try {
        // Exchange code for tokens
        const { tokens } = await oauth2Client.getToken(code);
        oauth2Client.setCredentials(tokens);

        // Get user info to identify the user
        const oauth2 = google.oauth2({
            auth: oauth2Client,
            version: 'v2'
        });
        const userInfo = await oauth2.userinfo.get();
        const email = userInfo.data.email;

        if (!tokens.refresh_token) {
            console.warn('No refresh token returned. User might have already authorized the app.');
            // In a real app, you might want to prompt the user to revoke access and try again if this is critical.
        }

        // Encrypt the refresh token if it exists
        const encryptedRefreshToken = tokens.refresh_token ? encrypt(tokens.refresh_token) : null;

        // Save user data
        const user = {
            email: email,
            refreshToken: encryptedRefreshToken, // Store encrypted
            updatedAt: new Date().toISOString()
        };
        saveUser(user);

        console.log(`User ${email} successfully connected. Refresh Token stored securely.`);
        res.json({ message: 'Connection Successful', email: email });

    } catch (error) {
        console.error('Error during OAuth callback:', error);
        res.status(500).send('Authentication failed.');
    }
});

module.exports = router;
