# REP Strategy Bot - Deployment Guide

This guide details how to deploy your **REP Strategy Bot** to the cloud using **Render.com**. This ensures the bot runs 24/7, automatically checking for market hours and sending Telegram alerts.

## Prerequisites
1.  **GitHub Repository**: Your code is already pushed to `ronadasakalesha/rep-strategy-bot`.
2.  **Angel One Credentials**: Have your API Key, Client ID, Password, and TOTP key ready.
3.  **Telegram Credentials**: Have your Bot Token and Chat ID ready.

---

## Deployment Steps (Render.com)

### 1. Create a New Web Service
1.  Log in to [Render Dashboard](https://dashboard.render.com/).
2.  Click the **"New +"** button and select **"Web Service"**.
3.  Select **"Build and deploy from a Git repository"**.
4.  Connect your repository: `ronadasakalesha/rep-strategy-bot`.

### 2. Configure the Service
Fill in the details as follows:

| Setting | Value |
| :--- | :--- |
| **Name** | `rep-strategy-bot` (or any name you like) |
| **Region** | Singapore (Nearest to India for lower latency) |
| **Branch** | `main` |
| **Runtime** | **Python 3** |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `python main.py` |
| **Instance Type** | **Free** (Good for testing) or **Starter** ($7/mo for reliability) |

### 3. Set Environment Variables (Crucial)
You **MUST** add your secrets here so the bot can log in.
Scroll down to the **"Environment Variables"** section and add the following key-value pairs (copy from your local `.env` file):

| Key | Value (Example) |
| :--- | :--- |
| `ANGEL_API_KEY` | `your_api_key_here` |
| `ANGEL_CLIENT_ID` | `your_client_id` |
| `ANGEL_PASSWORD` | `your_password` |
| `ANGEL_TOTP_KEY` | `your_totp_key` |
| `TELEGRAM_BOT_TOKEN` | `your_bot_token` |
| `TELEGRAM_CHAT_ID` | `your_chat_id` |

> **Note**: Do NOT wrap values in quotes. Just paste the plain text.

### 4. Deploy
1.  Click **"Create Web Service"**.
2.  Render will start building your bot. You will see the logs in the dashboard.
3.  **Success Indicator**: Look for the log line: `[INFO] Starting Web Server on port 10000` (or similar).

---

## How It Works
*   **24/7 Operation**: The bot will run continuously.
*   **Market Hours**: The internal logic (`is_market_open`) checks IST time.
    *   **09:15 - 15:30 IST**: Scans active.
    *   **Off-Hours**: Sleeps (prints "Market Closed" logs).
*   **Keep-Alive**: The simple Flask server we added ensures Render considers the service "healthy" and doesn't kill it.

## Troubleshooting
*   **Logs**: View the "Logs" tab in Render to see what the bot is doing.
*   **Re-Deploy**: If you push new code to GitHub, Render will automatically re-deploy the new version.
