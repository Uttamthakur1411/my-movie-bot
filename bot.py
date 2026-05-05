from flask import Flask
from threading import Thread
import os
import requests
import sqlite3
import asyncio
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import FloodWait

print("🚀 Movie Bot Pro - Starting...")

# Flask Keep-Alive
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "✅ Movie Bot Pro - All 4 Features ACTIVE!"

def run_flask():
    port = int(os.environ.get('PORT', 8080))
    flask_app.run(host='0.0.0.0', port=port)

# ==================== CONFIG ====================
API_ID = 34976268
API_HASH = "3ccae7cee8251da06d019c49a6aedb9e"
BOT_TOKEN = "8213871486:AAECaJwnXmup3JEwEnV2cAKMGl3NCl9Y6A4"
ADMIN_ID = 5615686466
UPI_LINK = "yourupi@paytm"  # 🔥 CHANGE THIS
CHANNEL = "@Movies_Uttam_Official"

app = Client("movie_bot_pro", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# ==================== DATABASE ====================
db = sqlite3.connect('movies_pro.db', check_same_thread=False)
cursor = db.cursor()

def init_db():
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY, 
        points INTEGER DEFAULT 50, 
        is_banned INTEGER DEFAULT 0,
        joined_date TEXT DEFAULT CURRENT_TIMESTAMP
    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS movies (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        name TEXT, 
        file_id TEXT
    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS temp_files (
        message_id INTEGER, 
        chat_id INTEGER, 
        movie_name TEXT,
        expire_time TEXT
    )''')
    db.commit()
    print("✅ Database Ready with all tables!")

init_db()

# ==================== 1. AUTO-DELETE ANTI-PIRACY 🔥 ====================
async def auto_delete_file(chat_id, message_id, movie_name):
    """5 Minutes Auto-Delete Protection"""
    await asyncio.sleep(300)  # 5 minutes
    try:
        await app.delete_messages(chat_id, message_id)
        print(f"🗑️ ANTI-PIRACY: Deleted {movie_name} from {chat_id}")
        cursor.execute("DELETE FROM temp_files WHERE message_id=? AND chat_id=?", (message_id, chat_id))
        db.commit()
    except Exception as e:
        print(f"Delete error: {e}")

# ==================== 2. BAN SYSTEM 🚫 ====================
def is_banned(user_id):
    cursor.execute("SELECT is_banned FROM users WHERE user_id=?", (user_id,))
    result = cursor.fetchone()
    return result and result[0] == 1

@app.on_message(filters.command("ban") & filters.user(ADMIN_ID))
async def ban_cmd(client, message):
    try:
        user_id = int(message.command[1])
        cursor.execute("UPDATE users SET is_banned=1 WHERE user_id=?", (user_id,))
        db.commit()
        await message.reply_text(f"🚫 **User BANNED:** `{user_id}`\n✅ No more access!")
        print(f"BANNED: {user_id}")
    except:
        await message.reply_text("❌ **Usage:** `/ban 123456789`")

@app.on_message(filters.command("unban") & filters.user(ADMIN_ID))
async def unban_cmd(client, message):
    try:
        user_id = int(message.command[1])
        cursor.execute("UPDATE users SET is_banned=0 WHERE user_id=?", (user_id,))
        db.commit()
        await message.reply_text(f"✅ **User UNBANNED:** `{user_id}`")
        print(f"UNBANNED: {user_id}")
    except:
        await message.reply_text("❌ **Usage:** `/unban 123456789`")

@app.on_message(filters.command("bannedlist") & filters.user(ADMIN_ID))
async def banned_list_cmd(client, message):
    cursor.execute("SELECT user_id FROM users WHERE is_banned=1")
    banned = cursor.fetchall()
    if not banned:
        return await message.reply_text("✅ **No banned users!**")
    text = "🚫 **BANNED USERS:**\n\n"
    for user in banned[:15]:
        text += f"👤 `{user[0]}`\n"
    await message.reply_text(text)

# ==================== 3. UPI PAYMENT 💰 ====================
@app.on_message(filters.command("buy"))
async def buy_cmd(client, message):
    if is_banned(message.from_user.id):
        return await message.reply_text("🚫 **You are BANNED**")
    
    btns = InlineKeyboardMarkup([
        [InlineKeyboardButton("💰 ₹20 = 100 Points", callback_data="pay100")],
        [InlineKeyboardButton("💎 ₹90 = 500 Points", callback_data="pay500")],
        [InlineKeyboardButton("📱 UPI QR", url=f"https://chart.googleapis.com/chart?chs=300x300&cht=qr&chl=upi://pay?pa={UPI_LINK}&pn=MovieBot")]
    ])
    
    await message.reply_text(
        f"""💳 **BUY POINTS INSTANTLY**

🔗 **UPI:** `{UPI_LINK}`

💵 **₹20** → **100 Points**
💎 **₹90** → **500 Points**

✅ Pay → Send SS to admin
⚡ Admin adds points in 1 min!

**Payment Proof bhejo: @{await client.get_me().username}**""",
        reply_markup=btns,
        disable_web_page_preview=True
    )

@app.on_message(filters.command("addpoints") & filters.user(ADMIN_ID))
async def add_points_cmd(client, message):
    try:
        user_id = int(message.command[1])
        points = int(message.command[2])
        cursor.execute("UPDATE users SET points = points + ? WHERE user_id=?", (points, user_id))
        db.commit()
        await message.send_message(user_id, f"🎉 **{points} Points Added!**\nThank you for payment! 💰")
        await message.reply_text(f"✅ **{points} Points** → `{user_id}` ✅")
    except Exception as e:
        await message.reply_text(f"❌ **Error:** `/addpoints 123456789 100`")

# ==================== 4. PHOTO BROADCAST 📸 ====================
@app.on_message(filters.command("broadcast") & filters.user(ADMIN_ID))
async def broadcast_cmd(client, message):
    if not message.reply_to_message:
        return await message.reply_text("❌ **REPLY TO PHOTO/VIDEO/TEXT** for broadcast!")
    
    cursor.execute("SELECT user_id FROM users WHERE is_banned=0")
    users = [row[0] for row in cursor.fetchall()]
    
    if not users:
        return await message.reply_text("❌ **No active users!**")
    
    status_msg = await message.reply_text(f"🚀 **Broadcasting** → {len(users)} users...")
    sent = 0
    
    for user_id in users[:200]:  # Safety limit
        try:
            await message.reply_to_message.copy(user_id)
            sent += 1
            await asyncio.sleep(0.08)
        except:
            pass
    
    await status_msg.edit_text(
        f"✅ **BROADCAST COMPLETE!**\n\n"
        f"📤 **Sent:** {sent}/{len(users)}\n"
        f"⏰ **Time:** {datetime.now().strftime('%H:%M:%S')}"
    )

# ==================== ADMIN ADD MOVIE 🎬 ====================
@app.on_message((filters.document | filters.video) & filters.user(ADMIN_ID))
async def add_movie(client, message):
    if message.caption:
        movie_name = message.caption
        file_id = message.document.file_id if message.document else message.video.file_id
        cursor.execute("INSERT INTO movies (name, file_id) VALUES (?, ?)", (movie_name, file_id))
        db.commit()
        await message.reply_text(
            f"✅ **MOVIE ADDED TO DB!**\n"
            f"🎬 **{movie_name}**\n"
            f"🆔 `{file_id[:30]}...`"
        )
    else:
        file_id = message.document.file_id if message.document else message.video.file_id
        await message.reply_text(f"🆔 **File ID:** `{file_id}`\n💡 **Add movie name in caption!**")

# ==================== START COMMAND 🎉 ====================
@app.on_message(filters.command("start"))
async def start_cmd(client, message):
    user_id = message.from_user.id
    
    if is_banned(user_id):
        return await message.reply_text("🚫 **You are PERMANENTLY BANNED!**")
    
    cursor.execute("INSERT OR IGNORE INTO users (user_id, points) VALUES (?, 50)", (user_id,))
    cursor.execute("SELECT points FROM users WHERE user_id=?", (user_id,))
    points = cursor.fetchone()[0]
    db.commit()
    
    btns = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔍 Search Movies", callback_data="search_menu")],
        [InlineKeyboardButton("💰 Buy Points", callback_data="buy_menu")],
        [InlineKeyboardButton("📊 My Points", callback_data="my_points")]
    ])
    
    await message.reply_text(
        f"""🔥 **Movie Bot Pro v2.0**

🎬 **Features:**
✅ Movie Search & Download
🗑️ **5min Auto-Delete** (Anti-Piracy)
💰 UPI Payment System
🚫 Admin Ban Protection
📸 Photo Broadcast

**Just type movie name!** 🎥

🪙 **Your Points: {points}**
💡 **Download = 5 Points**""",
        reply_markup=btns,
        disable_web_page_preview=True
    )

# ==================== MOVIE SEARCH ENGINE 🔍 ====================
@app.on_message(filters.text & ~filters.command(["start", "buy", "ban", "unban", "addpoints", "broadcast"]))
async def search_movies(client, message):
    user_id = message.from_user.id
    
    if is_banned(user_id):
        return await message.reply_text("🚫 **BANNED USER**")
    
    query = message.text.strip()
    status = await message.reply_text("🔎 **Searching movies...**")
    
    # Check real database
    cursor.execute("SELECT id, name, file_id FROM movies WHERE name LIKE ?", (f"%{query}%",))
    movies = cursor.fetchall()
    
    # Demo movies if none found
    if not movies:
        movies = [
            (1, f"{query} Full HD [Demo]", "demo_123"),
            (2, f"{query} Hindi Dubbed [Demo]", "demo_456")
        ]
    
    text = f"🎬 **Results for '{query}'** ({len(movies)} found)\n\n"
    btns = []
    
    for movie in movies[:5]:
        text += f"📱 {movie[1]}\n"
        btns.append([InlineKeyboardButton(f"📥 Download ({movie[1]})", callback_data=f"dl_{movie[0]}")])
    
    btns.append([InlineKeyboardButton("🔍 New Search", callback_data="search_menu")])
    
    await status.edit_text(text, reply_markup=InlineKeyboardMarkup(btns))

# ==================== DOWNLOAD w/ AUTO-DELETE 🔥 ====================
@app.on_callback_query(filters.regex(r"^dl_"))
async def download_movie(client, callback_query):
    user_id = callback_query.from_user.id
    
    if is_banned(user_id):
        await callback_query.answer("🚫 **BANNED**", show_alert=True)
        return
    
    movie_id = callback_query.data.split("_")[1]
    
    # Points check
    cursor.execute("SELECT points FROM users WHERE user_id=?", (user_id,))
    points_data = cursor.fetchone()
    if not points_data or points_data[0] < 5:
        await callback_query.answer("❌ **Need 5+ Points!**\n💰 Use /buy", show_alert=True)
        return
    
    # Get movie
    cursor.execute("SELECT name, file_id FROM movies WHERE id=?", (movie_id,))
    movie = cursor.fetchone()
    
    if movie:
        # Deduct points
        cursor.execute("UPDATE users SET points = points - 5 WHERE user_id=?", (user_id,))
        db.commit()
        
        try:
            # Send REAL file from DB
            movie_msg = await client.send_cached_media(
                chat_id=user_id,
                file_id=movie[1],
                caption=f"""🎬 **{movie[0]}**

🪙 **-5 Points Deducted**
🗑️ **AUTO DELETES IN 5 MINS**
🔒 **Cannot Forward**
⚠️ **Anti-Piracy Active**""",
                protect_content=True
            )
            
            # 🚀 START AUTO-DELETE TIMER
            asyncio.create_task(auto_delete_file(user_id, movie_msg.id, movie[0]))
            
            await callback_query.answer("✅ **Movie Sent!**\n🕐 **Deletes in 5min**", show_alert=True)
            
        except Exception as e:
            # Fallback demo video
            movie_msg = await client.send_video(
                chat_id=user_id,
                video="https://sample-videos.com/zip/10/mp4/SampleVideo_1280x720_1mb.mp4",
                caption=f"""🎬 **{movie[0]} - Demo**

🪙 **-5 Points**
🗑️ **AUTO DELETES IN 5 MINS**
🔒 **protect_content=True**""",
                protect_content=True
            )
            asyncio.create_task(auto_delete_file(user_id, movie_msg.id, movie[0]))
            await callback_query.answer("✅ **Demo Sent!** (Real file error)", show_alert=True)
    else:
        await callback_query.answer("❌ **Movie not found**", show_alert=True)

# ==================== CALLBACK HANDLERS ====================
@app.on_callback_query(filters.regex(r"^(search_menu|buy_menu|my_points)$"))
async def menu_callbacks(client, callback_query):
    data = callback_query.data
    
    if data == "buy_menu":
        await buy_cmd(client, callback_query.message)
    elif data == "search_menu":
        await callback_query.message.edit_text(
            "🔍 **SEARCH MOVIES**\n\n"
            "Type: `Avengers`, `Jawan`, `Pathaan`\n"
            "✅ Real database search\n"
            "🗑️ 5min auto-delete"
        )
    elif data == "my_points":
        cursor.execute("SELECT points FROM users WHERE user_id=?", (callback_query.from_user.id,))
        points = cursor.fetchone()[0]
        await callback_query.message.edit_text(
            f"🪙 **Your Points: {points}**\n\n"
            f"📥 **Download = 5 Points**\n"
            f"💰 **/buy** to recharge"
        )

@app.on_callback_query(filters.regex(r"^pay(100|500)"))
async def payment_info(client, callback_query):
    points = "100" if "100" in callback_query.data else "500"
    price = "₹20" if "100" in callback_query.data else "₹90"
    await callback_query.answer(f"💰 **{points} Points = {price}**\nSend payment to {UPI_LINK}", show_alert=True)

# ==================== STATS FOR ADMIN ====================
@app.on_message(filters.command("stats") & filters.user(ADMIN_ID))
async def stats_cmd(client, message):
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM users WHERE is_banned=1")
    banned_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM movies")
    movie_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM temp_files")
    active_downloads = cursor.fetchone()[0]
    
    stats_text = f"""📊 **PRO BOT STATS**

👥 **Total Users:** {total_users}
🚫 **Banned Users:** {banned_count}
🎬 **Movies in DB:** {movie_count}
📥 **Active Downloads:** {active_downloads}

💰 **UPI:** {UPI_LINK}
👑 **Admin:** `{ADMIN_ID}`"""
    
    await message.reply_text(stats_text)

# ==================== LAUNCH SEQUENCE ====================
if __name__ == "__main__":
    print("🔥 ================= MOVIE BOT PRO v2.0 =================")
    print(f"👑 Admin ID: {ADMIN_ID}")
    print(f"💰 UPI Link: {UPI_LINK}")
    print(f"📱 Channel: {CHANNEL}")
    print("✅ All 4 Features Ready!")
    
    # Start Flask
    Thread(target=run_flask, daemon=True).start()
    print("🌐 Flask Server: ACTIVE")
    
    # Start Bot
    print("🤖 Pyrogram Bot: Starting...")
    app.run()
