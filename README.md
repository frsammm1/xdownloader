# xHamster & Pornhub Downloader Bot
## Telegram Bot

A powerful Telegram bot to download videos from **xHamster** and **Pornhub**.

### Features
*   **Multi-Site Support:** Downloads from xHamster and Pornhub using specific cookies.
*   **Force Join System:** Requires users to join a specific backup channel (with private request approval) to use the bot.
*   **Share Verification:** Encourages users to share the bot with friends to unlock unlimited access.
*   **Admin Panel:**
    *   View active users and their upload counts.
    *   Monitor active downloads.
    *   Clickable user profiles.
*   **Log Channel:** Automatically forwards a copy of every uploaded video to a private log channel without re-uploading (saves bandwidth).
*   **Enhanced UX:**
    *   Random "Interesting Messages" during processing.
    *   Real-time progress bar with speed and ETA (updates every 6-7s).
    *   Thumbnail support (auto-converts WebP to JPG if needed).
*   **Concurrency Control:** Limits users to 5 simultaneous downloads.

### Deployment (Heroku/Docker)

This bot is designed to be deployed using **Docker**.

#### Prerequisites
*   Telegram Bot Token
*   Telegram API ID & Hash
*   Cookies files (`cookies.txt` for xHamster, `www.pornhub.com_cookies.txt` for Pornhub)

#### Environment Variables
| Variable | Description | Default |
| :--- | :--- | :--- |
| `API_ID` | Your Telegram API ID | `12345` |
| `API_HASH` | Your Telegram API Hash | `YOUR_HASH` |
| `BOT_TOKEN` | Your Telegram Bot Token | `YOUR_TOKEN` |
| `ADMIN_ID` | Telegram User ID of the Admin | `0` |
| `CREDIT_USERNAME` | Username to show in captions | `@fr_sammm11` |
| `LOG_CHANNEL_ID` | Channel ID for logs | `-1003676470398` |
| `FORCE_CHANNEL_ID` | Channel ID for Force Join | `-1003598486419` |
| `FORCE_CHANNEL_INVITE_LINK` | Invite Link for Force Join | `https://t.me/+b8mBsLIN329hYTVl` |

#### How to Deploy
1.  **Clone the Repo**
2.  **Add Cookies:** Ensure `cookies.txt` and `www.pornhub.com_cookies.txt` are present in the root directory.
3.  **Deploy to Heroku:**
    *   Connect your repo to Heroku.
    *   Set the `stack` to `container` (since we use `Dockerfile`).
    *   Add the Environment Variables in Heroku Settings.
    *   Deploy!

#### Running Locally
```bash
docker build -t downloader-bot .
docker run --env-file .env downloader-bot
```

### Commands
*   `/start` - Start the bot.
*   `/admin` - Open Admin Panel (Admin only).
