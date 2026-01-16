import os
import time
import logging
import asyncio
import shutil
import random
import glob
import subprocess
import requests
from bs4 import BeautifulSoup

# --- FIX FOR PYTHON 3.10+ CRASH ---
try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())
# ----------------------------------

from pyrogram import Client, filters, idle
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ChatJoinRequest
import yt_dlp
from database import add_user, get_user, update_user_verification, get_all_users, increment_upload_count

# --- CONFIGURATION ---
API_ID = int(os.environ.get("API_ID", 12345))
API_HASH = os.environ.get("API_HASH", "YOUR_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID", 0))
CREDIT_USERNAME = os.environ.get("CREDIT_USERNAME", "@fr_sammm11")
LOG_CHANNEL_ID = int(os.environ.get("LOG_CHANNEL_ID", -1003676470398))
FORCE_CHANNEL_ID = int(os.environ.get("FORCE_CHANNEL_ID", -1003598486419))
FORCE_CHANNEL_INVITE_LINK = os.environ.get("FORCE_CHANNEL_INVITE_LINK", "https://t.me/+b8mBsLIN329hYTVl")

logging.basicConfig(level=logging.INFO)

app = Client("my_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- GLOBAL STATE ---
ongoing_tasks = {}
BOT_IS_AWAKE = False  # Default to Sleep on restart
BROADCAST_WAIT_MODE = False # Admin broadcast state

INTERESTING_MESSAGES = [
    "🔥 Fetching that hot video for you...",
    "🍑 Hold tight, extracting the goods...",
    "😏 Just a moment, making it ready...",
    "🚀 Launching the download rocket...",
    "💥 Boom! Found it. Processing now...",
    "✨ Magic in progress... Wait for it!",
    "👀 Oh yeah, this one looks good...",
    "🕵️‍♂️ Investigating the link... Found it!",
    "🥂 Cheers! Downloading your request...",
    "💃 Dancing through the servers...",
    "🐱‍👤 Ninja mode activated. Downloading...",
    "🌟 Shining bright! Almost there...",
    "🎉 Party time soon! Downloading...",
    "💎 A hidden gem? Let's see...",
    "🔥 Hot stuff coming through!"
]

# --- HELPER FUNCTIONS ---

import re

def fallback_scraper(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            content = response.text
            soup = BeautifulSoup(content, 'html.parser')

            # 1. Check for .m3u8 (HLS) in text
            m3u8_match = re.search(r'https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*', content)
            if m3u8_match:
                return m3u8_match.group(0)

            # 2. Search for video tag with src
            video_tag = soup.find('video')
            if video_tag and video_tag.get('src'):
                return video_tag.get('src')

            # 3. Search for source tag inside video
            source_tag = soup.find('source', type=lambda t: t and ('mp4' in t or 'webm' in t or 'mkv' in t))
            if source_tag and source_tag.get('src'):
                return source_tag.get('src')

            # 4. Check for direct MP4 links in regex
            mp4_match = re.search(r'https?://[^\s"\'<>]+\.mp4[^\s"\'<>]*', content)
            if mp4_match:
                return mp4_match.group(0)

            # 5. Iframe fallback (Look for embed URL)
            iframes = soup.find_all('iframe')
            for iframe in iframes:
                src = iframe.get('src')
                if src:
                    # Handle protocol-relative URLs
                    if src.startswith('//'):
                        src = "https:" + src

                    # Return if it looks like an embed or video player
                    if "embed" in src or "player" in src or "masawatch" in src or "video" in src:
                        return src

    except Exception as e:
        print(f"Scraper Error: {e}")
    return None

def get_duration_ffmpeg(filepath):
    try:
        result = subprocess.check_output(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", filepath],
            stderr=subprocess.STDOUT
        )
        return int(float(result.strip()))
    except Exception as e:
        print(f"Duration Error: {e}")
        return 0

# --- UPLOAD PROGRESS BAR ---
progress_state = {}

async def upload_progress(current, total, message, user_id, task_id):
    try:
        now = time.time()
        msg_id = message.id

        # Update Task Info
        percentage = current * 100 / total
        if user_id in ongoing_tasks and task_id in ongoing_tasks[user_id]:
            ongoing_tasks[user_id][task_id]['status'] = "Uploading"
            ongoing_tasks[user_id][task_id]['progress'] = f"{round(percentage, 1)}%"

        # Initialize state
        if msg_id not in progress_state:
            progress_state[msg_id] = {'last_update_time': 0, 'last_current': 0}

        state = progress_state[msg_id]

        if now - state['last_update_time'] < 6.5 and current != total:
            return

        time_diff = now - state['last_update_time']
        if time_diff == 0: time_diff = 1

        speed = (current - state['last_current']) / time_diff
        state['last_current'] = current
        state['last_update_time'] = now
        
        def humanbytes(b):
            if not b: return ""
            power = 1024
            n = 0
            dic_powerN = {0: ' ', 1: 'Ki', 2: 'Mi', 3: 'Gi', 4: 'Ti'}
            while b > power:
                b /= power
                n += 1
            return str(round(b, 2)) + " " + dic_powerN[n] + 'B'

        speed_text = humanbytes(speed)

        text = f"**🚀 Uploading...**\n"
        text += f"📊 **Progress:** {round(percentage, 2)}%\n"
        text += f"📦 **Size:** {humanbytes(current)} / {humanbytes(total)}\n"
        text += f"⚡ **Speed:** {speed_text}/s"
        
        if user_id in ongoing_tasks and task_id in ongoing_tasks[user_id]:
             ongoing_tasks[user_id][task_id]['speed'] = f"{speed_text}/s"

        await message.edit_text(text)

        if current == total:
            if msg_id in progress_state:
                del progress_state[msg_id]

    except Exception:
        pass

# --- CORE FUNCTIONS ---

async def show_main_menu(client, chat_id, user_id):
    # MAIN MENU
    buttons = []
    if user_id == ADMIN_ID:
        buttons.append([InlineKeyboardButton("👮‍♂️ Admin Panel", callback_data="admin_panel_cb")])

    # Removed "My Active Tasks" button as requested

    reply_markup = InlineKeyboardMarkup(buttons) if buttons else None

    await client.send_message(
        chat_id=chat_id,
        text=(
            "👋 **Hy I'm powerful p0rn video downloader bot**\n"
            "You can download unlimited p0rn videos in this bot\n"
            "Just send me any P0rn links \n"
            "Supported websites: most p0rn websites available on internet (if not downloads try another website)\n"
            "/start Start the bot\n"
            "/cancel /stop cancel any active task\n"
            "/active_task check all active task\n\n"
            "**`Send any P*rn link directly to the bot`**"
        ),
        reply_markup=reply_markup
    )

async def check_user_access(client, message, user_id, user_name):
    # Initializes user in DB and performs checks.
    # Returns True if access granted, False if prompt sent.

    # Sync with MongoDB
    await add_user(user_id, user_name)
    user_data = await get_user(user_id)
    if not user_data:
         # Should not happen after add_user
         return False

    # ADMIN BYPASS
    if user_id == ADMIN_ID:
        return True

    # Force Join Check
    if not user_data.get("joined"):
        try:
            member = await client.get_chat_member(FORCE_CHANNEL_ID, user_id)
            if member.status in ["member", "administrator", "creator"]:
                 await update_user_verification(user_id, joined=True)
                 user_data['joined'] = True
        except Exception:
             pass

    if not user_data.get("joined"):
        await message.reply_text(
            "🛑 **Access Denied!**\n\n"
            "You must join our Backup Channel to use this bot.\n"
            "If you have already joined, click **'I've Joined'** below.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🚀 Join Backup Channel", url=FORCE_CHANNEL_INVITE_LINK)],
                [InlineKeyboardButton("✅ I've Joined", callback_data="check_join_status")]
            ])
        )
        return False

    # Share Check
    if not user_data.get("shared", False):
         share_text = f"https://t.me/{client.me.username}?start=ref_{user_id}"
         await message.reply_text(
            "🔓 **One Last Step!**\n\n"
            "Please share this bot with at least 2 friends/groups to unlock.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📤 Share Bot", url=f"https://t.me/share/url?url={share_text}")],
                [InlineKeyboardButton("✅ I have Shared", callback_data="shared_done")]
            ])
        )
         return False

    return True

# --- HANDLERS ---

@app.on_message(filters.command(["active_task", "status"]))
async def active_task_command(client, message):
    # Trigger existing callback logic manually
    # We create a dummy callback query object or just reuse the logic.
    # Reusing logic is cleaner.
    user_id = message.from_user.id
    tasks = ongoing_tasks.get(user_id, {})

    text = "📊 **My Active Tasks**\n\n"
    if not tasks:
        text += "✅ No active downloads/uploads."
    else:
        for tid, tdata in tasks.items():
            text += f"🎥 **{tdata.get('title', 'Video')}**\n"
            text += f"   Status: {tdata.get('status', 'Waiting')}\n"
            text += f"   Progress: {tdata.get('progress', '0%')} | Speed: {tdata.get('speed', '0B/s')}\n\n"

    # For command, we send a new message instead of editing
    await message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Refresh", callback_data="my_tasks")]
        ])
    )

@app.on_message(filters.command(["stop", "cancel"]))
async def cancel_command(client, message):
    user_id = message.from_user.id
    tasks = ongoing_tasks.get(user_id, {})

    if not tasks:
        await message.reply_text("✅ No active tasks to cancel.")
        return

    text = "🛑 **Select a task to cancel:**\n"
    buttons = []
    for tid, tdata in tasks.items():
        title = tdata.get("title", "Unknown Task")[:30]
        buttons.append([InlineKeyboardButton(f"❌ {title}", callback_data=f"cancel_task_{tid}")])

    await message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))

@app.on_callback_query(filters.regex(r"^cancel_task_"))
async def cancel_task_callback(client, callback_query):
    user_id = callback_query.from_user.id
    try:
        task_id = float(callback_query.data.split("_")[2])
        if user_id in ongoing_tasks and task_id in ongoing_tasks[user_id]:
            # Mark status as cancelled to trigger hooks/loops
            ongoing_tasks[user_id][task_id]['status'] = "Cancelled"
            await callback_query.answer("🛑 Task Cancelled!")
            await callback_query.message.edit_text(f"❌ **Task Cancelled.**")
        else:
            await callback_query.answer("⚠️ Task not found or already completed.", show_alert=True)
            await callback_query.message.delete()
    except Exception as e:
        print(f"Cancel Error: {e}")

@app.on_message(filters.command("start"))
async def start_command(client, message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name or "User"

    # Initialize user in DB on start
    await add_user(user_id, first_name)

    # ALWAYS show menu on /start, do NOT check verification here.
    # Sleep check is only for downloading links, as requested.
    await show_main_menu(client, message.chat.id, user_id)

    # Check verification (Prompts if needed)
    await check_user_access(client, message, user_id, first_name)

@app.on_callback_query(filters.regex("ask_awake"))
async def ask_awake_callback(client, callback_query):
    user = callback_query.from_user
    try:
        await client.send_message(
            chat_id=ADMIN_ID,
            text=f"🔔 **Wake Request**\n\n"
                 f"👤 **User:** {user.mention}\n"
                 f"🆔 `{user.id}`\n\n"
                 f"This user is asking to wake the bot!"
        )
        await callback_query.answer("✅ Request sent to Admin!", show_alert=True)
    except Exception as e:
        await callback_query.answer("❌ Failed to contact Admin.", show_alert=True)
        print(f"Wake Request Error: {e}")

@app.on_callback_query(filters.regex("check_join_status"))
async def check_join_status(client, callback_query):
    user_id = callback_query.from_user.id
    # BLIND TRUST: Immediately verify the user
    await add_user(user_id, callback_query.from_user.first_name)
    await update_user_verification(user_id, joined=True)

    await callback_query.message.delete()

    # Proceed to next step (Share Check)
    if await check_user_access(client, callback_query.message, user_id, callback_query.from_user.first_name):
        await show_main_menu(client, callback_query.message.chat.id, user_id)


@app.on_callback_query(filters.regex("shared_done"))
async def shared_callback(client, callback_query):
    user_id = callback_query.from_user.id

    # Update state - BLIND TRUST
    await add_user(user_id, callback_query.from_user.first_name)
    await update_user_verification(user_id, shared=True)

    await callback_query.message.delete()

    # Final check just in case, then show menu
    if await check_user_access(client, callback_query.message, user_id, callback_query.from_user.first_name):
         await show_main_menu(client, callback_query.message.chat.id, user_id)


@app.on_chat_join_request(filters.chat(FORCE_CHANNEL_ID))
async def approve_join_request(client, message: ChatJoinRequest):
    user_id = message.from_user.id
    try:
        await client.approve_chat_join_request(chat_id=message.chat.id, user_id=user_id)
        await add_user(user_id, message.from_user.first_name)
        await update_user_verification(user_id, joined=True)
        await client.send_message(user_id, "✅ **Request Approved!** Type /start.")
    except Exception as e:
        print(f"Error approving: {e}")

# --- ADMIN PANEL ---
@app.on_message(filters.command("admin") & filters.user(ADMIN_ID))
async def admin_command(client, message):
    await admin_panel_logic(client, message, is_edit=False)

@app.on_callback_query(filters.regex("admin_panel_cb"))
async def admin_panel_cb(client, callback_query):
    if callback_query.from_user.id != ADMIN_ID:
        return
    await admin_panel_logic(client, callback_query.message, is_edit=True)

async def admin_panel_logic(client, message, is_edit):
    text = "👮‍♂️ **Admin Panel**\n\n"

    all_users = await get_all_users()
    text += f"👥 **Total Users:** {len(all_users)}\n"

    total_tasks = 0
    for tasks in ongoing_tasks.values():
        total_tasks += len(tasks)

    text += f"📥 **Global Active Tasks:** {total_tasks}\n\n"
    text += "**📋 Recent Users:**\n"
    for data in all_users[-10:]: # Show last 10
         text += f"👤 {data['name']} (Uploads: {data.get('uploads', 0)})\n"

    # Awake Status
    status_icon = "🟢" if BOT_IS_AWAKE else "🔴"
    status_text = "Awake" if BOT_IS_AWAKE else "Sleeping"

    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Active Downloads", callback_data="admin_downloads"),
         InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast")],
        [InlineKeyboardButton(f"{status_icon} Bot: {status_text} (Click to Toggle)", callback_data="toggle_sleep")]
    ])

    if is_edit:
        await message.edit_text(text, reply_markup=buttons)
    else:
        await message.reply_text(text, reply_markup=buttons)

@app.on_callback_query(filters.regex("admin_downloads"))
async def admin_downloads_callback(client, callback_query):
    if callback_query.from_user.id != ADMIN_ID:
        return
    text = "📥 **Global Active Downloads**\n\n"
    has_tasks = False
    for uid, tasks in ongoing_tasks.items():
        if tasks:
             user_data = await get_user(uid)
             user_name = user_data.get('name', 'Unknown') if user_data else 'Unknown'
             text += f"👤 **{user_name}:**\n"
             for tid, tdata in tasks.items():
                 text += f" - {tdata.get('title', 'Unknown')} [{tdata.get('status', 'Init')}]\n"
             has_tasks = True

    if not has_tasks:
        text += "✅ No active downloads."

    await callback_query.message.edit_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_panel_cb")]]))

@app.on_callback_query(filters.regex("toggle_sleep"))
async def toggle_sleep_callback(client, callback_query):
    if callback_query.from_user.id != ADMIN_ID:
        return

    global BOT_IS_AWAKE
    BOT_IS_AWAKE = not BOT_IS_AWAKE

    # Refresh Admin Panel
    await admin_panel_logic(client, callback_query.message, is_edit=True)
    await callback_query.answer(f"Bot is now {'Awake' if BOT_IS_AWAKE else 'Sleeping'}")

    # BROADCAST ON AWAKE
    if BOT_IS_AWAKE:
        asyncio.create_task(broadcast_awake_msg(client))

async def broadcast_awake_msg(client):
    try:
        users = await get_all_users()
        msg_text = "🔔 **Bot is Awakened!**\n\nDownload hot videos now... 🔥"

        count = 0
        for u in users:
            try:
                await client.send_message(chat_id=u['user_id'], text=msg_text)
                count += 1
                await asyncio.sleep(0.05)
            except Exception:
                pass
        print(f"Awake Broadcast sent to {count} users.")
    except Exception as e:
        print(f"Awake Broadcast Error: {e}")

@app.on_callback_query(filters.regex("admin_broadcast"))
async def admin_broadcast_callback(client, callback_query):
    if callback_query.from_user.id != ADMIN_ID:
        return

    global BROADCAST_WAIT_MODE
    BROADCAST_WAIT_MODE = True

    await callback_query.message.edit_text(
        "📢 **Broadcast Mode**\n\n"
        "Send me the message you want to broadcast (Text, Photo, Video, etc.).\n"
        "It will be sent to ALL users in the database.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data="admin_panel_cb")]])
    )

@app.on_message(filters.user(ADMIN_ID) & filters.incoming)
async def admin_broadcast_listener(client, message):
    global BROADCAST_WAIT_MODE
    if not BROADCAST_WAIT_MODE:
        message.continue_propagation()
        return

    # Ignore commands
    if message.text and message.text.startswith("/"):
        message.continue_propagation()
        return

    BROADCAST_WAIT_MODE = False
    status_msg = await message.reply_text("📢 **Broadcasting...**")

    users = await get_all_users()
    count = 0
    failed = 0

    for u in users:
        try:
            await message.copy(chat_id=u['user_id'])
            count += 1
            await asyncio.sleep(0.05)
        except Exception:
            failed += 1
            pass

    await status_msg.edit_text(
        f"✅ **Broadcast Complete!**\n\n"
        f"👥 Sent: {count}\n"
        f"❌ Failed: {failed}",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Admin Panel", callback_data="admin_panel_cb")]])
    )
    message.stop_propagation()

@app.on_callback_query(filters.regex("my_tasks"))
async def my_tasks_callback(client, callback_query):
    user_id = callback_query.from_user.id
    tasks = ongoing_tasks.get(user_id, {})

    text = "📊 **My Active Tasks**\n\n"
    if not tasks:
        text += "✅ No active downloads/uploads."
    else:
        for tid, tdata in tasks.items():
            text += f"🎥 **{tdata.get('title', 'Video')}**\n"
            text += f"   Status: {tdata.get('status', 'Waiting')}\n"
            text += f"   Progress: {tdata.get('progress', '0%')} | Speed: {tdata.get('speed', '0B/s')}\n\n"

    await callback_query.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Refresh", callback_data="my_tasks")],
            [InlineKeyboardButton("🔙 Back", callback_data="back_to_start")]
        ])
    )

@app.on_callback_query(filters.regex("back_to_start"))
async def back_to_start(client, callback_query):
    user_id = callback_query.from_user.id
    if await check_user_access(client, callback_query.message, user_id, callback_query.from_user.first_name):
        await show_main_menu(client, callback_query.message.chat.id, user_id)


# --- DOWNLOADER ENGINE ---
def run_download(url, path, task_info_dict, generic_mode=False):

    def progress_hook(d):
        # CHECK CANCELLATION
        if task_info_dict.get('status') == "Cancelled":
            raise Exception("Cancelled by User")

        if d['status'] == 'downloading':
            task_info_dict['status'] = "Downloading"
            task_info_dict['progress'] = d.get('_percent_str', '0%')
            task_info_dict['speed'] = d.get('_speed_str', 'N/A')

    out_tmpl = f'{path}/%(title)s.%(ext)s'
    cookie_file = 'cookies.txt'
    if 'pornhub' in url.lower():
        cookie_file = 'www.pornhub.com_cookies.txt'

    # FORCE JPG THUMBNAILS FOR COMPATIBILITY
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': out_tmpl,
        'cookiefile': cookie_file,
        'writethumbnail': True,
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'geo_bypass': True,
        'progress_hooks': [progress_hook],
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'postprocessors': [{
            'key': 'FFmpegThumbnailsConvertor',
            'format': 'jpg',
        }],
    }

    if generic_mode:
        ydl_opts['force_generic_extractor'] = True
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        return info, filename

@app.on_message(filters.text & ~filters.command(["start", "admin", "status"]))
async def download_handler(client, message):
    url = message.text.strip()
    user_id = message.from_user.id
    
    if not url.startswith(("http", "www")):
        return 

    # SLEEP CHECK
    if not BOT_IS_AWAKE and user_id != ADMIN_ID:
        await message.reply_text(
            "😴 **Bot is sleeping! No worries.**\n\n"
            "The bot is currently resting. Click the button below to ask the admin to wake it up!",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔔 Ask admin to awake", callback_data="ask_awake")]
            ])
        )
        return

    # Check Verification using DB
    user_data = await get_user(user_id)
    if user_id != ADMIN_ID:
        if not user_data or not user_data.get("joined") or not user_data.get("shared"):
             await message.reply_text("⚠️ **Access Denied!** Please /start to verify.")
             return

    if user_id not in ongoing_tasks:
        ongoing_tasks[user_id] = {}

    if len(ongoing_tasks[user_id]) >= 5:
        await message.reply_text("⚠️ Limit reached (5 tasks). Wait for completion.")
        return

    task_id = time.time()
    ongoing_tasks[user_id][task_id] = {
        "title": "Fetching Metadata...",
        "status": "Initializing",
        "progress": "0%",
        "speed": "0B/s"
    }

    random_msg = random.choice(INTERESTING_MESSAGES)
    status_msg = await message.reply_text(f"🔎 **{random_msg}**")

    download_path = f"downloads/{int(task_id)}"
    if not os.path.exists(download_path):
        os.makedirs(download_path)

    filename = None
    thumb_path = None
    title = "Video"
    duration = 0

    monitor_running = True
    async def monitor_download():
        while monitor_running:
            await asyncio.sleep(6)
            if not monitor_running: break

            info = ongoing_tasks[user_id].get(task_id, {})
            status = info.get('status', 'Init')
            if status == "Downloading":
                prog = info.get('progress', '0%')
                speed = info.get('speed', '0B/s')
                try:
                    await status_msg.edit_text(f"⬇️ **Downloading...**\n📊 {prog} | ⚡ {speed}")
                except:
                    pass

    monitor_task = asyncio.create_task(monitor_download())

    try:
        ongoing_tasks[user_id][task_id]['title'] = "Downloading Video..."
        try:
            # 1. Standard yt-dlp
            info, filename = await asyncio.to_thread(run_download, url, download_path, ongoing_tasks[user_id][task_id], False)
        except Exception as e:
            print(f"Method 1 Failed: {e}")
            try:
                # 2. Generic yt-dlp
                await status_msg.edit_text("🔄 **Method 1 failed. Trying Generic Mode...**")
                info, filename = await asyncio.to_thread(run_download, url, download_path, ongoing_tasks[user_id][task_id], True)
            except Exception as e2:
                 print(f"Method 2 Failed: {e2}")
                 # 3. Fallback Scraper
                 await status_msg.edit_text("🔄 **Trying Fallback Scraper...**")
                 direct_link = await asyncio.to_thread(fallback_scraper, url)
                 if direct_link:
                     await status_msg.edit_text("✅ **Link Found! Downloading...**")
                     info, filename = await asyncio.to_thread(run_download, direct_link, download_path, ongoing_tasks[user_id][task_id], True)
                 else:
                     raise Exception("All download methods failed.")

        monitor_running = False
        monitor_task.cancel()

        title = info.get('title', 'Video')
        duration = info.get('duration', 0)

        # Duration Fix
        if not duration and filename and os.path.exists(filename):
            duration = get_duration_ffmpeg(filename)
        ongoing_tasks[user_id][task_id]['title'] = title
        ongoing_tasks[user_id][task_id]['status'] = "Processing"

        if not filename or not os.path.exists(filename):
             files = [f for f in os.listdir(download_path) if f.endswith(('.mp4', '.mkv', '.webm'))]
             if files:
                 filename = os.path.join(download_path, files[0])

        if not filename or not os.path.exists(filename):
            raise Exception("File not found after download.")
        
        if os.path.getsize(filename) > 2000000000:
            raise Exception("File > 2GB.")

        # THUMBNAIL FINDER (New: Look for JPGs generated by postprocessor)
        image_files = []
        for f in os.listdir(download_path):
            if f.endswith(('.jpg', '.jpeg', '.png', '.webp')):
                image_files.append(os.path.join(download_path, f))

        if image_files:
            thumb_path = image_files[0]
            # Prioritize JPG since we asked for it
            for img in image_files:
                if img.endswith('.jpg'):
                    thumb_path = img
                    break

        # GENERATE THUMBNAIL IF MISSING
        if not thumb_path and filename and os.path.exists(filename):
             thumb_path = os.path.join(download_path, "thumb_gen.jpg")
             try:
                 # Extract frame at 1s
                 subprocess.check_call(['ffmpeg', '-y', '-i', filename, '-ss', '00:00:01', '-vframes', '1', thumb_path], stderr=subprocess.DEVNULL)
             except Exception as e_thumb:
                 print(f"Thumbnail Gen Error: {e_thumb}")
                 thumb_path = None

        await status_msg.edit_text("📤 **Uploading...**")
        
        caption_text = f"🎥 **{title}**\n\n"
        caption_text += f"👤 **Developer:** {CREDIT_USERNAME}\n"
        caption_text += f"📥 **Downloaded by:** @{client.me.username}"

        sent_msg = await client.send_video(
            chat_id=message.chat.id,
            video=filename,
            caption=caption_text,
            duration=duration,
            thumb=thumb_path,
            supports_streaming=True,
            progress=upload_progress,
            progress_args=(status_msg, user_id, task_id)
        )
        await status_msg.delete()

        # LOG CHANNEL (No manual message needed)
        try:
            await client.send_video(
                 chat_id=LOG_CHANNEL_ID,
                 video=sent_msg.video.file_id,
                 caption=f"📝 **Log**\n👤 {message.from_user.mention}\n🆔 `{user_id}`\n🎥 {title}",
            )
        except Exception as e_log:
             print(f"Log Error: {e_log}")

        await increment_upload_count(user_id)

    except Exception as e:
        monitor_running = False
        await status_msg.edit_text(f"❌ **Error:** {str(e)}")

    finally:
        monitor_running = False
        if os.path.exists(download_path):
            shutil.rmtree(download_path, ignore_errors=True)
        if user_id in ongoing_tasks and task_id in ongoing_tasks[user_id]:
            del ongoing_tasks[user_id][task_id]

async def start_bot():
    print("Bot Starting...")
    await app.start()

    # --- LOG CHANNEL FIX: WARM UP PEER ---
    try:
        print(f"Pinging Log Channel ({LOG_CHANNEL_ID}) to cache peer...")

        # 1. Try resolving peer first
        try:
             await app.get_chat(LOG_CHANNEL_ID)
             print("Log Channel Resolved.")
        except Exception as e_resolve:
             print(f"Could not resolve log channel: {e_resolve}")

        # 2. Try sending a message
        msg = await app.send_message(LOG_CHANNEL_ID, ".")
        await msg.delete()
        print("Log Channel Ping Successful.")

    except Exception as e:
        print(f"Log Channel Ping Failed: {e}")
        # Note: If this fails, the bot might not be admin or the ID is wrong.

    print("Bot Started!")

    await idle()
    await app.stop()

if __name__ == "__main__":
    app.run(start_bot())
