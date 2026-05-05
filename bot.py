from flask import Flask
from threading import Thread
import os
import requests
import sqlite3
import asyncio
import random
from datetime import datetime, timedelta
from pyrogram import Client, filters
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import FloodWait, UserNotParticipant

# --- 1. RENDER PORT BINDING ---
flask_app = Flask('')

@flask_app.route('/')
def home():
    return "✅ Bot is alive and running smoothly! All features active!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    flask_app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_flask)
    t.start()

# --- 2. CONFIGURATION ---
API_ID = 34976268
API_HASH = "3ccae7cee8251da06d019c49a6aedb9e"
BOT_TOKEN = "8213871486:AAECaJwnXmup3JEwEnV2cAKMGl3NCl9Y6A4"
TMDB_KEY = "9309466d747d6bf6e91a81d01ec98cd0"
FORCE_SUB_CHANNEL = "Movies_Uttam_Official" 
ADMIN_ID = 5615686466 
UPI_ID = "yourupi@paytm"  # 🔄 YE CHANGE KARO!

bot_app = Client("Movie_Pro_Netflix_Final", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- 3. DATABASE SETUP (Enhanced) ---
db = sqlite3.connect("bot_data.db", check_same_thread=False)
cr = db.cursor()

def init_db():
    # Users table with ban column
    cr.execute("""CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER UNIQUE, joined_date TEXT, lang TEXT DEFAULT 'en', 
        points INTEGER DEFAULT 50, is_premium INTEGER DEFAULT 0, theme TEXT DEFAULT 'dark',
        is_banned INTEGER DEFAULT 0
    )""")
    
    # Add ban column if missing
    try:
        cr.execute("ALTER TABLE users ADD COLUMN is_banned INTEGER DEFAULT 0")
    except: pass
    
    cr.execute("CREATE TABLE IF NOT EXISTS files (id INTEGER PRIMARY KEY AUTOINCREMENT, movie_name TEXT, file_id TEXT, clicks INTEGER DEFAULT 0)")
    cr.execute("CREATE TABLE IF NOT EXISTS watchlist (user_id INTEGER, movie_id TEXT, movie_name TEXT)")
    cr.execute("CREATE TABLE IF NOT EXISTS last_watch (user_id INTEGER UNIQUE, movie_name TEXT, file_id TEXT)")
    cr.execute("CREATE TABLE IF NOT EXISTS search_logs (query TEXT, count INTEGER DEFAULT 1)")
    cr.execute("CREATE TABLE IF NOT EXISTS temp_files (message_id INTEGER, chat_id INTEGER, expire_time TEXT)")
    db.commit()
    print("✅ Database initialized with ban system!")

init_db()

# ===================== NEW FEATURES START =====================

# --------- 1. AUTO DELETE FUNCTION ----------
async def auto_delete(client, chat_id, message_id, delay=300):
    """Auto delete message after delay (5 mins = 300 sec)"""
    await asyncio.sleep(delay)
    try:
        await client.delete_messages(chat_id, message_id)
        print(f"🗑️ Auto-deleted message {message_id} from {chat_id}")
        # Clean DB
        cr.execute("DELETE FROM temp_files WHERE message_id=? AND chat_id=?", (message_id, chat_id))
        db.commit()
    except Exception as e:
        print(f"Delete error: {e}")

# --------- 2. BAN SYSTEM FUNCTIONS ----------
async def is_banned_user(user_id):
    """Check if user is banned"""
    cr.execute("SELECT is_banned FROM users WHERE user_id=?", (user_id,))
    res = cr.fetchone()
    return res and res[0] == 1

# --------- 2.1 BAN COMMAND ----------
@bot_app.on_message(filters.command("ban") & filters.user(ADMIN_ID))
async def ban_user(client, message):
    try:
        uid = int(message.text.split()[1])
        reason = " ".join(message.text.split()[2:]) or "No reason"
        cr.execute("UPDATE users SET is_banned=1 WHERE user_id=?", (uid,))
        db.commit()
        await message.reply_text(f"🚫 **User BANNED!**\n👤 ID: `{uid}`\n📝 Reason: {reason}")
        print(f"🚫 Banned user: {uid}")
    except:
        await message.reply_text("❌ **Usage:** `/ban 123456789 [reason]`")

# --------- 2.2 UNBAN COMMAND ----------
@bot_app.on_message(filters.command("unban") & filters.user(ADMIN_ID))
async def unban_user(client, message):
    try:
        uid = int(message.text.split()[1])
        cr.execute("UPDATE users SET is_banned=0 WHERE user_id=?", (uid,))
        db.commit()
        await message.reply_text(f"✅ **User UNBANNED!**\n👤 ID: `{uid}`")
        print(f"✅ Unbanned user: {uid}")
    except:
        await message.reply_text("❌ **Usage:** `/unban 123456789`")

# --------- 2.3 BAN LIST ----------
@bot_app.on_message(filters.command("bannedlist") & filters.user(ADMIN_ID))
async def banned_list(client, message):
    cr.execute("SELECT user_id FROM users WHERE is_banned=1")
    banned = cr.fetchall()
    if not banned:
        return await message.reply_text("✅ **No banned users!**")
    text = "🚫 **Banned Users:**\n\n" + "\n".join([f"👤 `{u[0]}`" for u in banned[:20]])
    await message.reply_text(text)

# --------- 3. UPI PAYMENT SYSTEM ----------
@bot_app.on_message(filters.command("buy") & filters.private)
async def buy_points(client, message):
    if await is_banned_user(message.from_user.id):
        return await message.reply_text("🚫 **You are banned!**")
    
    upi_link = f"upi://pay?pa={UPI_ID}&pn=MovieBot&am=20&cu=INR"
    
    btn = InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 Pay ₹20 (100 Points)", url=upi_link)],
        [InlineKeyboardButton("💎 Pay ₹90 (500 Points)", callback_data="buy_500")]
    ])
    
    await message.reply_text(
        "💰 **Buy Points Instantly!**\n\n"
        f"🔗 **UPI ID:** `{UPI_ID}`\n\n"
        "💵 **₹20** = **100 Points**\n"
        "💎 **₹90** = **500 Points**\n\n"
        "**Payment ke baad admin ko bolo verify kare**\n"
        "`/addpoints YOUR_ID 100`",
        reply_markup=btn,
        disable_web_page_preview=True
    )

# --------- 3.1 ADMIN ADD POINTS ----------
@bot_app.on_message(filters.command("addpoints") & filters.user(ADMIN_ID))
async def add_points(client, message):
    try:
        parts = message.text.split()
        uid, pts = int(parts[1]), int(parts[2])
        cr.execute("UPDATE users SET points = points + ? WHERE user_id = ?", (pts, uid))
        db.commit()
        await message.reply_text(f"✅ **{pts} Points added to user** `{uid}`")
    except:
        await message.reply_text("❌ **Usage:** `/addpoints 123456789 100`")

# --------- 4. UPGRADED BROADCAST WITH PHOTO ----------
@bot_app.on_message(filters.command("broadcast") & filters.user(ADMIN_ID))
async def broadcast_handler(client, message):
    if not message.reply_to_message:
        return await message.reply_text("❌ **Reply to PHOTO/VIDEO/TEXT** to broadcast!")
    
    cr.execute("SELECT user_id FROM users WHERE is_banned=0")  # Skip banned
    users = cr.fetchall()
    
    if not users:
        return await message.reply_text("❌ **No active users!**")
    
    count = 0
    status_msg = await message.reply_text(f"🚀 **Broadcasting to {len(users)} users...**")
    
    for user_id in users:
        try:
            await message.reply_to_message.copy(user_id[0])
            count += 1
            await asyncio.sleep(0.1)
        except:
            pass
    
    await status_msg.edit_text(
        f"✅ **Broadcast Complete!**\n\n"
        f"📤 **Sent:** {count}/{len(users)} users\n"
        f"⏱️ **Time:** {datetime.now().strftime('%H:%M')}"
    )

# ===================== NEW FEATURES END =====================

# --- 5. TMDB ENGINE ---
def get_tmdb_results(query):
    try:
        cr.execute("INSERT INTO search_logs (query) VALUES (?) ON CONFLICT(query) DO UPDATE SET count = count + 1", (query.lower(),))
        db.commit()
    except: pass

    url = f"https://api.themoviedb.org/3/search/multi?api_key={TMDB_KEY}&query={query}&include_adult=false"
    try:
        res = requests.get(url, timeout=10).json().get('results', [])
        return [r for r in res if r.get('media_type') in ['movie', 'tv']]
    except: return []

def get_extra_details(m_type, m_id):
    url = f"https://api.themoviedb.org/3/{m_type}/{m_id}?api_key={TMDB_KEY}&append_to_response=credits"
    try:
        res = requests.get(url, timeout=10).json()
        genres = ", ".join([g['name'] for g in res.get('genres', [])[:3]]) or "N/A"
        runtime = f"{res.get('runtime', 0)} min" if m_type == "movie" else f"{res.get('episode_run_time', [0])[0]} min/ep"
        cast = ", ".join([c['name'] for c in res.get('credits', {}).get('cast', [])[:3]]) or "N/A"
        return genres, runtime, cast
    except: return "N/A", "N/A", "N/A"

# --- 6. AUTH + BAN CHECK ---
async def check_auth(client, message):
    uid = message.from_user.id
    
    # 🔥 BAN CHECK FIRST
    if await is_banned_user(uid):
        await message.reply_text("🚫 **You are BANNED from this bot!**\nContact admin.")
        return False
    
    if not FORCE_SUB_CHANNEL: return True
    try:
        await client.get_chat_member(FORCE_SUB_CHANNEL, uid)
        return True
    except:
        btn = InlineKeyboardMarkup([[InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{FORCE_SUB_CHANNEL}")]])
        await message.reply_text("❌ **Access Denied!**\nChannel join karein!", reply_markup=btn)
        return False

# --- 7. ADMIN STATS (Enhanced) ---
@bot_app.on_message(filters.command("stats") & filters.user(ADMIN_ID))
async def stats_handler(client, message):
    cr.execute("SELECT COUNT(*) FROM users WHERE is_banned=0")
    active = cr.fetchone()[0]
    cr.execute("SELECT COUNT(*) FROM users")
    total = cr.fetchone()[0]
    cr.execute("SELECT COUNT(*) FROM files")
    movies = cr.fetchone()[0]
    
    text = f"""📊 **FULL STATS:**

👥 **Active Users:** {active}
👤 **Total Users:** {total}
🚫 **Banned:** {total-active}
🎬 **Movies:** {movies}"""
    
    await message.reply_text(text)

# --- 8. ADMIN FILE ADD ---
@bot_app.on_message((filters.document | filters.video) & filters.user(ADMIN_ID))
async def smart_add_handler(client, message):
    if message.caption:
        m_name = message.caption.strip().lower()
        f_id = message.document.file_id if message.document else message.video.file_id
        try:
            cr.execute("INSERT INTO files (movie_name, file_id) VALUES (?, ?)", (m_name, f_id))
            db.commit()
            await message.reply_text(f"✅ **Movie Added!**\n🎬 `{m_name}`\n🆔 `{f_id[:30]}...`")
        except Exception as e:
            await message.reply_text(f"❌ **Error:** {e}")
    else:
        f_id = message.document.file_id if message.document else message.video.file_id
        await message.reply_text(f"🆔 **File ID:** `{f_id}`\n💡 Caption add karo auto-save!")

# --- 9. START COMMAND ---
@bot_app.on_message(filters.command("start") & filters.private)
async def start_cmd(client, message):
    uid = message.from_user.id
    
    # Skip banned users
    if await is_banned_user(uid):
        return await message.reply_text("🚫 **BANNED USER**")
    
    now = datetime.now().strftime("%d-%m-%Y")
    
    # Referral
    if len(message.command) > 1 and message.command[1].isdigit():
        ref_id = int(message.command[1])
        cr.execute("SELECT user_id FROM users WHERE user_id=?", (uid,))
        if not cr.fetchone() and ref_id != uid:
            cr.execute("UPDATE users SET points=points+20 WHERE user_id=?", (ref_id,))
            db.commit()
            try:
                await client.send_message(ref_id, "🎁 **+20 Points!** New referral!")
            except: pass
    
    cr.execute("INSERT OR IGNORE INTO users (user_id, joined_date) VALUES (?, ?)", (uid, now))
    db.commit()
    
    btns = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔍 Search Movies", callback_data="search_menu")],
        [InlineKeyboardButton("💰 Buy Points", callback_data="buy_menu")],
        [InlineKeyboardButton("📱 Menu", callback_data="main_menu")]
    ])
    
    await message.reply_text(
        f"🔥 **Welcome {message.from_user.first_name}!**\n\n"
        "🎬 **Pro Movie Bot**\n"
        "✅ Search & Download\n"
        "✅ Auto-delete protection\n"
        "✅ Points system\n\n"
        "**Just type movie name!** 🎥",
        reply_markup=btns
    )

# --- 10. MOVIE SEARCH (With Ban Check + Auto-delete ready) ---
@bot_app.on_message(filters.text & filters.private & ~filters.command(["start", "buy"]))
async def movie_search(client, message):
    # 🔥 BAN CHECK
    if await is_banned_user(message.from_user.id):
        return await message.reply_text("🚫 **You are banned!**")
    
    if not await check_auth(client, message): return
    if len(message.text) < 2: return
    
    query = message.text.lower().strip()
    status = await message.reply_text("🔎 **Searching...**")
    
    # Local DB
    cr.execute("SELECT id, movie_name, file_id FROM files WHERE movie_name LIKE ?", (f"%{query}%",))
    local_data = cr.fetchone()
    
    # TMDB
    results = get_tmdb_results(query)
    
    if not results and not local_data:
        btn = InlineKeyboardMarkup([[InlineKeyboardButton("🎟 Request", callback_data=f"req_{query[:20]}")]])
        return await status.edit(f"❌ **'{query.title()}'** not found!", reply_markup=btn)
    
    item = results[0] if results else {'id': 0, 'title': local_data[1], 'media_type': 'movie'}
    title = item.get('title') or item.get('name')
    m_type = item.get('media_type', 'movie')
    
    caption = f"🎬 **{title}**\n\n⚠️ **File auto-deletes in 5 mins!**"
    
    btns = [[InlineKeyboardButton("📺 Watch Online", url=f"https://vidsrc.me/embed/{m_type}/{item.get('id', 0)}")]]
    
    if local_data:
        btns.append([InlineKeyboardButton("📥 Download (5 Points)", callback_data=f"dl_{local_data[0]}")])
    
    btns.append([InlineKeyboardButton("🔍 Search Again", callback_data="search_menu")])
    
    try:
        await message.reply_photo(
            photo=f"https://image.tmdb.org/t/p/w500{item.get('poster_path', '')}",
            caption=caption,
            reply_markup=InlineKeyboardMarkup(btns)
        )
    except:
        await message.reply_text(caption, reply_markup=InlineKeyboardMarkup(btns))
    
    await status.delete()

# --- 11. CALLBACK HANDLERS (Updated) ---
@bot_app.on_callback_query()
async def handle_callbacks(client, cb):
    uid = cb.from_user.id
    data = cb.data
    
    # Ban check
    if await is_banned_user(uid):
        return await cb.answer("🚫 BANNED!", show_alert=True)
    
    try:
        if data.startswith("dl_"):
            # Points check
            cr.execute("SELECT points FROM users WHERE user_id=?", (uid,))
            points = cr.fetchone()[0] if cr.fetchone() else 0
            
            if points < 5:
                return await cb.answer("❌ **Need 5 points!** Refer karo!", show_alert=True)
            
            file_id = data.split("_")[1]
            cr.execute("SELECT file_id, movie_name FROM files WHERE id=?", (file_id,))
            file_data = cr.fetchone()
            
            if file_data:
                # Deduct points
                cr.execute("UPDATE users SET points=points-5 WHERE user_id=?", (uid,))
                db.commit()
                
                # Send file WITH AUTO-DELETE 🔥
                msg = await client.send_cached_media(
                    chat_id=uid,
                    file_id=file_data[0],
                    caption=f"🎬 **{file_data[1]}**\n🪙 **-5 Points**\n⚠️ **AUTO-DELETES IN 5 MINS**",
                    protect_content=True
                )
                
                # 🚀 AUTO DELETE ACTIVATED
                asyncio.create_task(auto_delete(client, uid, msg.id))
                
                await cb.answer("✅ **File sent!** (Auto-delete 5min)", show_alert=True)
            else:
                await cb.answer("❌ **File not found!**", show_alert=True)
        
        elif data == "buy_menu":
            await buy_points(client, cb.message)
        
        elif data == "main_menu":
            await start_cmd(client, cb.message)
            
    except Exception as e:
        print(f"Callback error: {e}")
        await cb.answer("⚠️ Error!", show_alert=True)

# --- 12. LAUNCH ---
if __name__ == "__main__":
    print("🚀 === PRO BOT LAUNCHING ===")
    print(f"👑 Admin: {ADMIN_ID}")
    print(f"🔗 UPI: {UPI_ID}")
    keep_alive()
    print("✅ Flask running | Bot starting...")
    bot_app.run()
