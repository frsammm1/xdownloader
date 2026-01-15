import os
import time
import logging
import asyncio
import shutil
import random
import glob

# --- FIX FOR PYTHON 3.10+ CRASH ---
try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())
# ----------------------------------

from pyrogram import Client, filters, idle
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ChatJoinRequest
import yt_dlp

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

# --- IN-MEMORY DATA STORE ---
# Users: { user_id: { "joined": bool, "shared": bool, "uploads": int, "name": str } }
users_db = {}

# Ongoing tasks: { user_id: { task_id: { "title": str, "status": str, "progress": str, "speed": str } } }
ongoing_tasks = {}

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

# --- UPLOAD PROGRESS BAR ---
# Dictionary to store progress state: { message_id: { 'last_update_time': float, 'last_current': int } }
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

        # Update Telegram Message every 6.5s
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

# --- START HANDLER ---
@app.on_message(filters.command("start"))
async def start(client, message):
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name

    if user_id not in users_db:
        users_db[user_id] = {"joined": False, "shared": False, "uploads": 0, "name": first_name or username}

    # ADMIN BYPASS
    if user_id == ADMIN_ID:
        users_db[user_id]["joined"] = True
        users_db[user_id]["shared"] = True

    # Force Join Check
    if not users_db[user_id]["joined"]:
        try:
            member = await client.get_chat_member(FORCE_CHANNEL_ID, user_id)
            if member.status in ["member", "administrator", "creator"]:
                 users_db[user_id]["joined"] = True
        except Exception:
             pass

    if not users_db[user_id]["joined"]:
        await message.reply_text(
            "🛑 **Access Denied!**\n\n"
            "You must join our Backup Channel to use this bot.\n"
            "Click the button below to send a **Join Request**.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🚀 Join Backup Channel", url=FORCE_CHANNEL_INVITE_LINK)]
            ])
        )
        return

    # Share Check
    if not users_db[user_id].get("shared", False):
         share_text = f"https://t.me/{client.me.username}?start=ref_{user_id}"
         await message.reply_text(
            "🔓 **One Last Step!**\n\n"
            "Please share this bot with at least 2 friends/groups to unlock.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📤 Share Bot", url=f"https://t.me/share/url?url={share_text}")],
                [InlineKeyboardButton("✅ I have Shared", callback_data="shared_done")]
            ])
        )
         return

    # MAIN MENU
    buttons = []
    if user_id == ADMIN_ID:
        buttons.append([InlineKeyboardButton("👮‍♂️ Admin Panel", callback_data="admin_panel_cb")])

    # Active Tasks Button for everyone
    buttons.append([InlineKeyboardButton("📊 My Active Tasks", callback_data="my_tasks")])

    await message.reply_text(
        "👋 **Welcome Back!**\n\n"
        "✅ **You have unlimited access.**\n"
        "🔗 **Supported Sites:** xHamster & Pornhub.\n\n"
        "👇 Send me a link to start downloading!",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

@app.on_callback_query(filters.regex("shared_done"))
async def shared_callback(client, callback_query):
    user_id = callback_query.from_user.id
    if user_id == ADMIN_ID:
        users_db[user_id]["shared"] = True

    if user_id in users_db:
        users_db[user_id]["shared"] = True
        await start(client, callback_query.message) # Re-run start logic to show menu
    else:
        await callback_query.answer("⚠️ Please /start first.")

@app.on_chat_join_request(filters.chat(FORCE_CHANNEL_ID))
async def approve_join_request(client, message: ChatJoinRequest):
    user_id = message.from_user.id
    try:
        await client.approve_chat_join_request(chat_id=message.chat.id, user_id=user_id)
        if user_id not in users_db:
             users_db[user_id] = {
                 "joined": True,
                 "shared": False,
                 "uploads": 0,
                 "name": message.from_user.first_name or message.from_user.username
             }
        else:
            users_db[user_id]["joined"] = True

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
    text += f"👥 **Active Users:** {len(users_db)}\n"

    total_tasks = 0
    for tasks in ongoing_tasks.values():
        total_tasks += len(tasks)

    text += f"📥 **Global Active Tasks:** {total_tasks}\n\n"
    text += "**📋 Recent Users:**\n"
    for uid, data in list(users_db.items())[-20:]: # Show last 20
         text += f"👤 {data['name']} (Uploads: {data.get('uploads', 0)})\n"

    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 View All Active Downloads", callback_data="admin_downloads")]
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
             user_name = users_db.get(uid, {}).get('name', 'Unknown')
             text += f"👤 **{user_name}:**\n"
             for tid, tdata in tasks.items():
                 text += f" - {tdata.get('title', 'Unknown')} [{tdata.get('status', 'Init')}]\n"
             has_tasks = True

    if not has_tasks:
        text += "✅ No active downloads."

    await callback_query.message.edit_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_panel_cb")]]))

# --- USER STATUS PANEL ---
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
    # Just show the start message again
    await start(client, callback_query.message)


# --- DOWNLOADER ENGINE ---
def run_download(url, path, task_info_dict, generic_mode=False):

    def progress_hook(d):
        if d['status'] == 'downloading':
            task_info_dict['status'] = "Downloading"
            task_info_dict['progress'] = d.get('_percent_str', '0%')
            task_info_dict['speed'] = d.get('_speed_str', 'N/A')

    out_tmpl = f'{path}/%(title)s.%(ext)s'
    cookie_file = 'cookies.txt'
    if 'pornhub' in url.lower():
        cookie_file = 'www.pornhub.com_cookies.txt'

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

    # ACCESS CHECK
    if user_id != ADMIN_ID:
        if user_id not in users_db or not users_db[user_id].get("joined") or not users_db[user_id].get("shared"):
            await message.reply_text("⚠️ **Access Denied!** Please /start to verify.")
            return

    # CONCURRENCY
    if user_id not in ongoing_tasks:
        ongoing_tasks[user_id] = {}

    if len(ongoing_tasks[user_id]) >= 5:
        await message.reply_text("⚠️ Limit reached (5 tasks). Wait for completion.")
        return

    # INIT TASK
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

    # MONITORING LOOP (Downloading Phase)
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
        # DOWNLOAD
        ongoing_tasks[user_id][task_id]['title'] = "Downloading Video..."
        try:
            info, filename = await asyncio.to_thread(run_download, url, download_path, ongoing_tasks[user_id][task_id], False)
        except Exception as e:
            print(f"Method 1 Failed: {e}")
            await status_msg.edit_text("🔄 **Method 1 failed. Trying Generic Mode...**")
            info, filename = await asyncio.to_thread(run_download, url, download_path, ongoing_tasks[user_id][task_id], True)

        monitor_running = False
        monitor_task.cancel()

        title = info.get('title', 'Video')
        duration = info.get('duration', 0)
        ongoing_tasks[user_id][task_id]['title'] = title
        ongoing_tasks[user_id][task_id]['status'] = "Processing"

        # FIND FILE
        if not filename or not os.path.exists(filename):
             files = [f for f in os.listdir(download_path) if f.endswith(('.mp4', '.mkv', '.webm'))]
             if files:
                 filename = os.path.join(download_path, files[0])

        if not filename or not os.path.exists(filename):
            raise Exception("File not found after download.")
        
        # SIZE CHECK
        if os.path.getsize(filename) > 2000000000:
            raise Exception("File > 2GB.")

        # THUMBNAIL FINDER (Improved)
        # Find any image file in the directory that is NOT the video
        image_files = []
        for f in os.listdir(download_path):
            if f.endswith(('.jpg', '.jpeg', '.png', '.webp')):
                image_files.append(os.path.join(download_path, f))

        if image_files:
            # Prefer jpg/png
            thumb_path = image_files[0]
            for img in image_files:
                if img.endswith(('.jpg', '.jpeg')):
                    thumb_path = img
                    break

            # Convert WebP
            if thumb_path.endswith(".webp"):
                new_thumb = os.path.splitext(thumb_path)[0] + ".jpg"
                try:
                    process = await asyncio.create_subprocess_exec(
                        "ffmpeg", "-i", thumb_path, new_thumb, "-y", "-hide_banner", "-loglevel", "error"
                    )
                    await process.wait()
                    if os.path.exists(new_thumb):
                        thumb_path = new_thumb
                except Exception:
                    pass

        # UPLOAD
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

        # LOG CHANNEL
        try:
            # Attempt to resolve peer lazily if needed
            try:
                await client.get_chat(LOG_CHANNEL_ID)
            except:
                pass

            await client.send_video(
                 chat_id=LOG_CHANNEL_ID,
                 video=sent_msg.video.file_id,
                 caption=f"📝 **Log**\n👤 {message.from_user.mention}\n🆔 `{user_id}`\n🎥 {title}",
            )
        except Exception as e_log:
             print(f"Log Error: {e_log}")

        # Update stats
        if user_id in users_db:
             users_db[user_id]["uploads"] = users_db[user_id].get("uploads", 0) + 1

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
    await app.start()
    # Ensure Bot ID info is available
    print("Bot Started!")
    await idle()
    await app.stop()

if __name__ == "__main__":
    app.run(start_bot())
