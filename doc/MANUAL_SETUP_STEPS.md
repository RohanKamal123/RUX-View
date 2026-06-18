# Vision OS — Manual Setup Steps
# What You Do By Hand (Can't Be Coded)

**Date**: May 1, 2026
**Estimated Time**: 2-3 hours total
**Cost**: $0 (all free tiers)

---

## 📋 OVERVIEW

These are the steps you must do **manually** — they can't be automated by code. Each step takes 5-15 minutes. Follow them in order.

---

## STEP 1: Create a MEGA.nz Account (5 min)

MEGA.nz is your **backend storage** — all user data, camera configs, events, and billing info are stored here as JSON files.

1. Go to https://mega.nz/register
2. Create an account (e.g., `visionos.business@mega.nz` or use your email)
3. **Free tier**: 20 GB storage — enough for thousands of JSON files
4. After registration, verify your email
5. Log in to MEGA.nz

### Get Your MEGA Credentials

You need your MEGA email and password for the `.env` file:

- **MEGA_EMAIL**: The email you used to register
- **MEGA_PASSWORD**: Your MEGA account password

> ⚠️ **Important**: The MEGA credentials are stored in `.env` and used by `MegaClient` to authenticate. The folder structure (`Vision OS Data/users/`, `Vision OS Data/cameras/`, etc.) is **created automatically by code** — you don't need to create folders manually.

---

## STEP 2: Create Google Cloud Project (10 min)

This is needed for Cloud Run deployment (hosting the API server).

1. Go to https://console.cloud.google.com
2. Click **Create Project** (top of dashboard)
3. Name: `Vision OS Platform`
4. Click **Create**
5. Wait 30 seconds for project to be created
6. Note your **Project ID** (e.g., `vision-os-platform-123456`)

### Enable Required APIs

1. Go to **APIs & Services → Library**
2. Search and **Enable** each of these:
   - ✅ Cloud Run API
   - ✅ Artifact Registry API
   - ✅ Secret Manager API
   - ✅ Cloud Monitoring API

> Note: No Google Drive API needed — Vision OS uses MEGA.nz for storage, not Google Drive.

---

## STEP 4: Set Up Firebase Auth (10 min)

1. Go to https://console.firebase.google.com
2. Click **Create a project**
3. Select your Google Cloud project: `Vision OS Platform`
4. Click **Continue**
5. Disable Google Analytics (not needed)
6. Click **Create project**
7. Wait 1-2 minutes for Firebase to provision

### Enable Email/Password Auth

1. In Firebase Console, go to **Authentication → Sign-in method**
2. Click **Email/Password**
3. Enable it → **Save**

### Download Service Account

1. Go to **Project Settings → Service accounts**
2. Click **Generate new private key**
3. Save the file as `firebase-service-account.json`
4. Place it in your project root

### Create Test User (for development)

1. Go to **Authentication → Users**
2. Click **Add user**
3. Email: `test@visionos.bd`
4. Password: `Test123!`
5. Click **Add**

---

## STEP 5: Set Up Environment Variables (5 min)

1. Open `c:/Users/HP Zbook/Documents/RUX View/.env.example`
2. Save a copy as `.env`
3. Fill in these values:

```bash
# MEGA.nz (Backend Storage — all user data, cameras, events, billing)
MEGA_EMAIL=visionos.business@mega.nz
MEGA_PASSWORD=your_mega_password_here

# Firebase
FIREBASE_SERVICE_ACCOUNT_PATH=firebase-service-account.json
FIREBASE_PROJECT_ID=vision-os-platform-xxxxx

# AI APIs
GEMINI_API_KEY=your_gemini_api_key_here
GROQ_API_KEY=your_groq_api_key_here

# Telegram
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here

# bKash (for payments)
BKASH_MERCHANT_ID=your_bkash_merchant_id
BKASH_API_KEY=your_bkash_api_key
BKASH_SECRET_KEY=your_bkash_secret_key

# Nagad (for payments)
NAGAD_MERCHANT_ID=your_nagad_merchant_id
NAGAD_API_KEY=your_nagad_api_key

# SendGrid (for emails)
SENDGRID_API_KEY=your_sendgrid_api_key

# App
SECRET_KEY=generate-a-random-secret-key-here
ENVIRONMENT=development
```

### Generate a Secret Key

Run this command to generate a random secret key:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

---

## STEP 6: Get Gemini API Key (5 min)

1. Go to https://aistudio.google.com/app/apikey
2. Click **Create API Key**
3. Copy the key
4. Add it to your `.env` file as `GEMINI_API_KEY`

---

## STEP 7: Create Telegram Bot (5 min)

1. Open Telegram and search for **@BotFather**
2. Send: `/newbot`
3. Name: `Vision OS Alerts`
4. Username: `vision_os_alerts_bot` (or any unique name)
5. BotFather will give you a **token** — copy it
6. Add it to your `.env` file as `TELEGRAM_BOT_TOKEN`

---

## STEP 8: Install Dependencies (5 min)

```bash
cd "c:/Users/HP Zbook/Documents/RUX View"
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

Make sure `requirements.txt` has the MEGA.nz dependency:

```txt
mega.py>=1.1.0
```

Then run:
```bash
pip install -r requirements.txt
```

---

## STEP 9: Run Tests (5 min)

```bash
cd "c:/Users/HP Zbook/Documents/RUX View"
venv\Scripts\activate
pytest backend/tests/ -v
```

All tests should pass. If any fail, check the error messages and fix the issues.

---

## STEP 10: Start Development Server (1 min)

```bash
cd "c:/Users/HP Zbook/Documents/RUX View"
venv\Scripts\activate
uvicorn backend.dashboard.server:app --reload --port 8000
```

Open your browser to: http://localhost:8000

You should see the Vision OS landing page.

---

## STEP 11: Deploy to Google Cloud Run (10 min)

### Install Google Cloud CLI

1. Download from: https://cloud.google.com/sdk/docs/install
2. Run the installer
3. After installation, open a new terminal and run:

```bash
gcloud init
gcloud auth login
gcloud config set project vision-os-platform-xxxxx
```

### Deploy

```bash
cd "c:/Users/HP Zbook/Documents/RUX View"
venv\Scripts\activate

# Build and deploy
gcloud builds submit --tag asia-south1-docker.pkg.dev/vision-os-platform-xxxxx/vision-os/api:latest
gcloud run deploy vision-os-api --image asia-south1-docker.pkg.dev/vision-os-platform-xxxxx/vision-os/api:latest --platform managed --region asia-south1 --allow-unauthenticated
```

After deployment, you'll get a URL like: `https://vision-os-api-xxxxx-uc.a.run.app`

---

## STEP 12: Set Up Domain (Optional — 15 min)

If you want a custom domain instead of the `*.run.app` URL:

1. Buy a domain from any registrar (e.g., `visionos.bd` from a Bangladesh registrar)
2. Go to **Cloud Run → vision-os-api → Domain mappings**
3. Click **Add mapping**
4. Enter your domain (e.g., `api.visionos.bd`)
5. Follow the instructions to verify domain ownership
6. Update your DNS records as instructed
7. Wait 5-30 minutes for DNS propagation

---

## 📊 STEP 13: VISUALIZE THE SAAS — Looker Studio Dashboard (15 min)

This is the **visualization** step. You'll create a live dashboard showing all your SaaS metrics.

### What You'll See

After setup, you'll have a dashboard showing:
- 📈 **Daily signups** — line chart
- 📹 **Active cameras** — gauge chart
- 🚨 **Events per day** — bar chart
- 💰 **Revenue** — time series
- 📊 **User growth** — area chart
- 🏆 **Top subscription tiers** — pie chart

### Step-by-Step

1. **Open Looker Studio**
   - Go to https://lookerstudio.google.com
   - Sign in with your Google account

2. **Create a New Report**
   - Click **Blank Report**
   - Name it: `Vision OS Analytics`

3. **Add Data Source**
   - Click **Create New Data Source**
   - Search for **Google Drive**
   - Click **Select**
   - Navigate to: `Vision OS Drive → analytics → daily_stats.csv`
   - Click **Connect**
   - Set these field types:
     - `date` → **Date (YYYYMMDD)**
     - `new_users` → **Number**
     - `total_users` → **Number**
     - `active_cameras` → **Number**
     - `events_detected` → **Number**
     - `revenue_bdt` → **Currency (BDT)**
   - Click **Add to Report**

4. **Create Charts**

   **Chart 1: Daily Signups (Time Series)**
   - Click **Add a chart → Time series**
   - Dimension: `date`
   - Metric: `new_users`
   - Title: "Daily Signups"

   **Chart 2: Total Users (Scorecard)**
   - Click **Add a chart → Scorecard**
   - Metric: `total_users` (latest value)
   - Title: "Total Users"

   **Chart 3: Events Per Day (Bar Chart)**
   - Click **Add a chart → Bar chart**
   - Dimension: `date`
   - Metric: `events_detected`
   - Title: "Events Detected Per Day"

   **Chart 4: Revenue (Time Series)**
   - Click **Add a chart → Time series**
   - Dimension: `date`
   - Metric: `revenue_bdt`
   - Title: "Daily Revenue (BDT)"
   - Format: Currency

   **Chart 5: Active Cameras (Gauge)**
   - Click **Add a chart → Gauge**
   - Metric: `active_cameras`
   - Set range: 0 to 100
   - Title: "Active Cameras"

   **Chart 6: User Growth (Area Chart)**
   - Click **Add a chart → Area chart**
   - Dimension: `date`
   - Metric: `total_users`
   - Title: "User Growth Over Time"

5. **Arrange the Dashboard**
   - Drag charts to arrange them in a grid
   - Add a title at the top: "Vision OS — Live Analytics"
   - Add date range filter (top right)

6. **Share the Dashboard**
   - Click **Share** (top right)
   - Add your team members' emails
   - Set permission: **Can view**
   - Click **Share**

### Alternative: Google Sheets Dashboard (Simpler)

If Looker Studio feels complex, use Google Sheets:

1. Open Google Sheets
2. Go to **File → Import → Upload**
3. Upload `daily_stats.csv` from your Drive
4. Use **Insert → Chart** to create:
   - Line chart for signups
   - Bar chart for events
   - Scorecard for total users
5. Share the sheet with your team

---

## 🔧 WHAT TO DO WHEN THINGS GO WRONG

### "MEGA.nz authentication failed"
- Check your `MEGA_EMAIL` and `MEGA_PASSWORD` in `.env`
- Verify you can log in at https://mega.nz/login
- Make sure your MEGA account is email-verified

### "MEGA.nz storage limit reached"
- Free tier: 20 GB — check usage at https://mega.nz/account
- Delete old backups or upgrade MEGA account
- Run backup cleanup: `python -c "from backend.storage.mega_backup import MegaBackup; import asyncio; asyncio.run(MegaBackup().delete_old_backups())"`

### "Firebase Auth not working"
- Go to Firebase Console → Authentication → Sign-in method
- Verify Email/Password is **Enabled**

### "Deployment failed"
- Run: `gcloud builds submit --tag asia-south1-docker.pkg.dev/[PROJECT_ID]/vision-os/api:latest`
- Check the error message in the build logs
- Common fix: Enable Cloud Build API

### "Tests failing"
- Check that `.env` file exists and has correct values
- Verify MEGA credentials are correct in `.env`
- Run: `pip install -r requirements.txt` to update dependencies

---

## ✅ FINAL CHECKLIST

Before you can use Vision OS, complete these:

- [ ] MEGA.nz account created (free tier: 20 GB)
- [ ] MEGA_EMAIL + MEGA_PASSWORD added to `.env`
- [ ] Google Cloud Project created
- [ ] Cloud Run API enabled
- [ ] Firebase project created
- [ ] Firebase Email/Password auth enabled
- [ ] Firebase service account JSON downloaded
- [ ] `.env` file configured with all keys
- [ ] Gemini API key obtained
- [ ] Telegram bot created + token obtained
- [ ] Dependencies installed (`pip install -r requirements.txt`)
- [ ] Tests pass (`pytest backend/tests/ -v`)
- [ ] Dev server runs (`uvicorn backend.dashboard.server:app --reload --port 8000`)
- [ ] Deployed to Cloud Run (optional for now)
- [ ] Looker Studio dashboard created (visualization)

---

*Vision OS — Manual Setup Guide*
*Total manual time: ~2-3 hours*
*Next: Start coding with DeepSeek prompts from DEEPSEEK_PROMPTS_V11.md*
