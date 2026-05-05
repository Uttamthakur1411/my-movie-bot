from flask import Flask
from threading import Thread
import os
import requests
import sqlite3
import asyncio
import random
from datetime import datetime, timedelta
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InlineQueryResultArticle, InputTextMessageContent
import time

# --- 1. RENDER PORT BINDING (For 24/7 Deployment) ---
flask_app = Flask('')

@flask_app.route('/')
def home():
    return "🚀 Movie Pro Bot is alive and running smoothly! Anti-Piracy Active!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    flask_app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_flask)
    t.start()

# --- 2. CONFIGURATION (Apne Credentials Daalein) ---
API_ID = 34976268
API_HASH = "3ccae7cee8251da06d019c49a6aedb9e"
BOT_TOKEN = "8213871486:AAECaJwnXmup3JEwEnV2cAKMGl3NCl9Y6A4"
TMDB_KEY = "9309466d747d6bf6e91a81d01ec98cd0"
FORCE_SUB_CHANNEL = "Movies_Uttam_Official" 
ADMIN_ID = 5615686466 

bot_app = Client("Movie_Pro_Netflix_Final", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- 3. HARDENED DATABASE SETUP (With Ban & Auto-Delete) ---
db = sqlite3.connect("bot_data.db", check_same_thread=False)
cr = db.cursor()

def init_db():
    cr.execute("""CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER UNIQUE, joined_date TEXT, lang TEXT DEFAULT 'en', 
        points INTEGER DEFAULT 50, is_premium INTEGER DEFAULT 0, theme TEXT DEFAULT 'dark',
        is_banned INTEGER DEFAULT 0
    )""")
    cr.execute("CREATE TABLE IF NOT EXISTS files (id INTEGER PRIMARY KEY AUTOINCREMENT, movie_name TEXT, file_id TEXT, clicks INTEGER DEFAULT 0)")
    cr.execute("CREATE TABLE IF NOT EXISTS watchlist (user_id INTEGER, movie_id TEXT, movie_name TEXT)")
    cr.execute("CREATE TABLE IF NOT EXISTS last_watch (user_id INTEGER UNIQUE, movie_name TEXT, file_id TEXT)")
    cr.execute("CREATE TABLE IF NOT EXISTS search_logs (query TEXT, count INTEGER DEFAULT 1)")
    cr.execute("CREATE TABLE IF NOT EXISTS temp_files (message_id INTEGER, chat_id INTEGER, file_id TEXT, movie_name TEXT, expire_time TEXT, PRIMARY KEY (message_id, chat_id))")
    cr.execute("CREATE TABLE IF NOT EXISTS banned_users (user_id INTEGER UNIQUE, ban_date TEXT, reason TEXT)")
    db.commit()

init_db()

# --- 4. ANTI-PIRACY AUTO-DELETE SYSTEM ---
async def schedule_file_deletion(client, message_id, chat_id, file_id, movie_name):
    expire_time = (datetime.now() + timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M:%S")
    cr.execute("INSERT INTO temp_files (message_id, chat_id, file_id, movie_name, expire_time) VALUES (?, ?, ?, ?, ?)",
               (message_id, chat_id, file_id, movie_name, expire_time))
    db.commit()
    
    # Schedule deletion
    await asyncio.sleep(300)  # 5 minutes
    try:
        await client.delete_messages(chat_id, message_id)
        cr.execute("DELETE FROM temp_files WHERE message_id = ? AND chat_id = ?", (message_id, chat_id))
        db.commit()
        print(f"🗑️ Auto-deleted: {movie_name} from {chat_id}")
    except: pass

# --- 5. BAN/UNBAN SYSTEM ---
def is_user_banned(user_id):
    cr.execute("SELECT is_banned FROM users WHERE user_id = ?", (user_id,))
    result = cr.fetchone()
    return result and result[0] == 1

@bot_app.on_message(filters.command("ban") & filters.user(ADMIN_ID))
async def ban_user(client, message):
    if len(message.command) < 2:
        return await message.reply_text("❌ Usage: `/ban user_id [reason]`")
    
    try:
        user_id = int(message.command[1])
        reason = " ".join(message.command[2:]) if len(message.command) > 2 else "Spamming"
        
        cr.execute("UPDATE users SET is_banned = 1 WHERE user_id = ?", (user_id,))
        cr.execute("INSERT OR REPLACE INTO banned_users (user_id, ban_date, reason) VALUES (?, ?, ?)",
                  (user_id, datetime.now().strftime("%d-%m-%Y %H:%M"), reason))
        db.commit()
        
        await message.reply_text(f"✅ **User Banned!**\n👤 ID: `{user_id}`\n📝 Reason: {reason}")
    except: await message.reply_text("❌ Invalid user ID!")

@bot_app.on_message(filters.command("unban") & filters.user(ADMIN_ID))
async def unban_user(client, message):
    if len(message.command) < 2:
        return await message.reply_text("❌ Usage: `/unban user_id`")
    
    try:
        user_id = int(message.command[1])
        cr.execute("UPDATE users SET is_banned = 0 WHERE user_id = ?", (user_id,))
        db.commit()
        await message.reply_text(f"✅ **User Unbanned!**\n👤 ID: `{user_id}`")
    except: await message.reply_text("❌ Invalid user ID!")

@bot_app.on_message(filters.command("bannedlist") & filters.user(ADMIN_ID))
async def banned_list(client, message):
    cr.execute("SELECT user_id, ban_date, reason FROM banned_users")
    banned = cr.fetchall()
    if not banned:
        return await message.reply_text("✅ No banned users!")
    
    text = "🚫 **Banned Users:**\n\n"
    for user in banned[:10]:  # Show top 10
        text += f"👤 `{user[0]}` - {user[1]}\n📝 {user[2]}\n\n"
    await message.reply_text(text)

# --- 6. TMDB ENGINE (With Extra Details) ---
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

# --- 7. STRICT AUTH & BAN CHECK ---
async def check_auth(client, message):
    uid = message.from_user.id
    
    # Check if banned
    if is_user_banned(uid):
        await message.reply_text("🚫 **You are BANNED!** Contact admin.")
        return False
    
    if not FORCE_SUB_CHANNEL: return True
    try:
        await client.get_chat_member(FORCE_SUB_CHANNEL, uid)
        return True
    except Exception:
        btn = InlineKeyboardMarkup([[InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{FORCE_SUB_CHANNEL}")]])
        await message.reply_text("❌ **Access Denied!**\nChannel join karein pehle!", reply_markup=btn)
        return False

# --- 8. UPI PAYMENT SYSTEM ---
UPI_LINK = "your-upi-link@paytm"  # Apna UPI link yahan daalein
@bot_app.on_message(filters.command("buy") & filters.private)
async def buy_points(client, message):
    if not await check_auth(client, message): return
    
    btns = InlineKeyboardMarkup([
        [InlineKeyboardButton("💰 Buy 100 Points (₹20)", callback_data="buy_100")],
        [InlineKeyboardButton("💎 Buy 500 Points (₹90)", callback_data="buy_500")]
    ])
    await message.reply_text(
        "💳 **Buy Points Instantly!**\n\n"
        "📱 **UPI Payment:** Scan QR or send to link\n"
        f"🔗 **{UPI_LINK}**\n\n"
        "Payment ke baad `/paid 100` ya `/paid 500` type karein!",
        reply_markup=btns
    )

@bot_app.on_message(filters.command("paid") & filters.private)
async def verify_payment(client, message):
    if not await check_auth(client, message): return
    if message.from_user.id != ADMIN_ID:  # Only admin verifies
        return await message.reply_text("❌ Sirf admin payment verify kar sakte hain!")
    
    if len(message.command) < 2:
        return await message.reply_text("❌ Usage: `/paid user_id points`")
    
    try:
        user_id = int(message.command[1])
        points = int(message.command[2])
        cr.execute("UPDATE users SET points = points + ? WHERE user_id = ?", (points, user_id))
        db.commit()
        await message.reply_text(f"✅ **Payment Verified!**\n👤 User: `{user_id}`\n🪙 Added: **{points}** points")
    except: await message.reply_text("❌ Invalid command!")

# --- 9. BROADCAST WITH PHOTO (UPGRADED) ---
@bot_app.on_message(filters.command("broadcast") & filters.user(ADMIN_ID))
async def broadcast_handler(client, message):
    if not message.reply_to_message:
        return await message.reply_text("❌ Reply to a message (with photo/text) to broadcast!")
    
    cr.execute("SELECT user_id FROM users WHERE is_banned = 0")
    users = cr.fetchall()
    count = 0
    msg = await message.reply_text(f"🚀 Starting Broadcast to {len(users)} users...")
    
    for user in users:
        try:
            await message.reply_to_message.copy(user[0])
            count += 1
            await asyncio.sleep(0.1)
        except: pass
    await msg.edit(f"✅ **Broadcast Finished!**\n📤 Sent to: **{count}/{len(users)}** users")

# --- 10. ADMIN STATS (Enhanced) ---
@bot_app.on_message(filters.command("stats") & filters.user(ADMIN_ID))
async def stats_handler(client, message):
    cr.execute("SELECT COUNT(*) FROM users WHERE is_banned = 0")
    active_users = cr.fetchone()[0]
    cr.execute("SELECT COUNT(*) FROM users")
    total_users = cr.fetchone()[0]
    cr.execute("SELECT COUNT(*) FROM files")
    t_files = cr.fetchone()[0]
    cr.execute("SELECT COUNT(*) FROM banned_users")
    banned_count = cr.fetchone()[0]
    
    text = f"""📊 **Bot Analytics:**

👥 **Active Users:** {active_users}
👤 **Total Users:** {total_users}
🚫 **Banned Users:** {banned_count}
🎬 **Total Movies:** {t_files}"""
    
    await message.reply_text(text)

# --- 11. ADMIN FILE ADD ---
@bot_app.on_message((filters.document | filters.video) & filters.user(ADMIN_ID))
async def smart_add_handler(client, message):
    if message.caption:
        m_name = message.caption.strip().lower()
        f_id = message.document.file_id if message.document else message.video.file_id
        try:
            cr.execute("INSERT INTO files (movie_name, file_id) VALUES (?, ?)", (m_name, f_id))
            db.commit()
            await message.reply_text(f"✅ **Movie Added!**\n🎬 `{m_name}`\n🆔 `{f_id[:20]}...`")
        except Exception as e:
            await message.reply_text(f"❌ Error: {e}")
    else:
        f_id = message.document.file_id if message.document else message.video.file_id
        await message.reply_text(f"🆔 **File ID:** `{f_id}`\n💡 Caption mein movie name daalein auto-save ke liye!")

# --- 12. START COMMAND ---
@bot_app.on_message(filters.command("start") & filters.private)
async def start_cmd(client, message):
    uid = message.from_user.id
    
    # Check ban status
    if is_user_banned(uid):
        return await message.reply_text("🚫 **You are BANNED from this bot!**")
    
    now = datetime.now().strftime("%d-%m-%Y")
    
    # Referral system
    if len(message.command) > 1 and message.command[1].isdigit():
        ref_id = int(message.command[1])
        cr.execute("SELECT user_id FROM users WHERE user_id = ?", (uid,))
        if not cr.fetchone() and ref_id != uid:
            cr.execute("UPDATE users SET points = points + 20 WHERE user_id = ?", (ref_id,))
            try: 
                await client.send_message(ref_id, "🎁 **+20 Points!** New referral joined!")
            except: pass

    cr.execute("INSERT OR IGNORE INTO users (user_id, joined_date, lang) VALUES (?, ?, 'en')", (uid, now))
    db.commit()

    welcome_text = f"""🔥 **Welcome {message.from_user.first_name}!**

🎬 **Movie Pro Bot** - Netflix Style
✅ Search & Download Movies
✅ Watchlist & Continue Watching
✅ Points System + Refer & Earn
⚡ **Anti-Piracy** - Files auto-delete in 5 mins

💎 **Premium Features Active!**"""
    
    btns = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔥 Trending", callback_data="trending_data"), 
         InlineKeyboardButton("📱 Buy Points", callback_data="buy_menu")],
        [InlineKeyboardButton("📑 Watchlist", callback_data="show_wls"), 
         InlineKeyboardButton("⏯ Continue", callback_data="continue_cb")],
        [InlineKeyboardButton("🚀 Refer & Earn", callback_data="refer_info")]
    ])
    await message.reply_text(welcome_text, reply_markup=btns, disable_web_page_preview=True)

# --- 13. MOVIE SEARCH (Strict) ---
@bot_app.on_message(filters.text & filters.private & ~filters.me & ~filters.command("buy"))
async def movie_search(client, message):
    if not await check_auth(client, message): return
    if len(message.text) < 2: return

    query = message.text.lower().strip()
    status = await message.reply_text("🔎 **Searching movies...**")

    # Local DB Check
    cr.execute("SELECT id, movie_name, file_id FROM files WHERE movie_name LIKE ?", (f"%{query}%",))
    local_data = cr.fetchone()
    
    # TMDB Check
    results = get_tmdb_results(query)

    if not results and not local_data:
        btn = InlineKeyboardMarkup([[InlineKeyboardButton("🎟 Request Movie", callback_data=f"req_{query[:20]}")]])
        return await status.edit(f"❌ **'{query.title()}'** not found!", reply_markup=btn)

    # Show result
    item = results[0] if results else {'id': 0, 'title': local_data[1], 'media_type': 'movie'}
    m_id, m_type = item.get('id', 0), item.get('media_type', 'movie')
    title = item.get('title') or item.get('name')
    genres, runtime, cast = get_extra_details(m_type, m_id)
    poster = f"https://image.tmdb.org/t/p/w500{item.get('poster_path')}" if item.get('poster_path') else None

    caption = f"""🎬 **{title}**
━━━━━━━━━━━━━━━━
🎭 **Genre:** {genres}
⏳ **Duration:** {runtime}
⭐ **Rating:** {item.get('vote_average', 'N/A')}/10
👥 **Cast:** {cast}
━━━━━━━━━━━━━━━━
⚠️ **File auto-deletes in 5 mins!**
✨ **Powered By Thakur Uttam**"""

    btns = [
        [InlineKeyboardButton("📺 Watch Online", url=f"https://vidsrc.me/embed/{m_type}/{m_id}")],
        [InlineKeyboardButton("🎬 Trailer", url=f"https://www.youtube.com/results?search_query={title.replace(' ', '+')}+trailer")],
        [InlineKeyboardButton("➕ Watchlist", callback_data=f"wls_{m_id}")] 
    ]
    
    if local_data:
        btns.insert(0, [InlineKeyboardButton("📥 Download (5 Points)", callback_data=f"dl_{local_data[0]}")])

    try:
        if poster:
            await message.reply_photo(photo=poster, caption=caption, reply_markup=InlineKeyboardMarkup(btns))
        else:
            await message.reply_text(caption, reply_markup=InlineKeyboardMarkup(btns), disable_web_page_preview=True)
        await status.delete()
    except Exception as e:
        await status.edit(caption, reply_markup=InlineKeyboardMarkup(btns))

# --- 14. CALLBACK HANDLERS (Enhanced) ---
@bot_app.on_callback_query()
async def handle_callbacks(client, cb):
    uid = cb.from_user.id
    data = cb.data
    
    if is_user_banned(uid):
        return await cb.answer("🚫 You are BANNED!", show_alert=True)

    try:
        if data == "trending_data":
            res = requests.get(f"https://api.themoviedb.org/3/trending/all/day?api_key={TMDB_KEY}").json().get('results', [])[:8]
            text = "🔥 **Top Trending Today:**\n\n"
            for i, m in enumerate(res, 1): 
                text += f"{i}. {m.get('title') or m.get('name')}\n"
            await cb.message.edit_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Main Menu", callback_data="back_start")]]))

        elif data == "buy_menu":
            btns = InlineKeyboardMarkup([
                [InlineKeyboardButton("💰 100 Points (₹20)", callback_data="buy_100")],
                [InlineKeyboardButton("💎 500 Points (₹90)", callback_data="buy_500")],
                [InlineKeyboardButton("⬅️ Back", callback_data="back_start")]
            ])
            await cb.message.edit_text(
                f"💳 **Buy Points**\n\n"
                f"🔗 **UPI:** `{UPI_LINK}`\n\n"
                "Payment → `/paid YOUR_ID points` (Admin verify karega)",
                reply_markup=btns, disable_web_page_preview=True
            )

        elif data.startswith("buy_"):
            points = 100 if data.endswith("100") else 500
            price = "₹20" if points == 100 else "₹90"
            await cb.answer(f"💰 {points} points = {price}\nSend payment then ask admin!", show_alert=True)

        elif data == "continue_cb":
            cr.execute("SELECT movie_name, file_id FROM last_watch WHERE user_id = ?", (uid,))
            res = cr.fetchone()
            if res:
                msg = await client.send_cached_media(chat_id=uid, file_id=res[1], 
                                                   caption=f"⏯ **Continue: {res[0]}\n⚠️ Auto-delete in 5 mins**", 
                                                   protect_content=True)
                # Schedule auto-delete
                asyncio.create_task(schedule_file_deletion(client, msg.id, uid, res[1], res[0]))
                await cb.answer("✅ Check your chat!")
            else:
                await cb.answer("❌ No previous download found!", show_alert=True)

        elif data.startswith("dl_"):
            cr.execute("SELECT points FROM users WHERE user_id = ?", (uid,))
            points_row = cr.fetchone()
            points = points_row[0] if points_row else 0
            
            if points < 5:
                return await cb.answer("❌ Need 5+ points! Use /refer", show_alert=True)
            
            file_db_id = data.split("_")[1]
            cr.execute("SELECT file_id, movie_name FROM files WHERE id = ?", (file_db_id,))
            res = cr.fetchone()
            
            if res:
                # Deduct points & Update last watch
                cr.execute("UPDATE users SET points = points - 5 WHERE user_id = ?", (uid,))
                cr.execute("INSERT OR REPLACE INTO last_watch (user_id, movie_name, file_id) VALUES (?, ?, ?)", 
                          (uid, res[1], res[0]))
                db.commit()
                
                # Send file with auto-delete
                msg = await client.send_cached_media(chat_id=uid, file_id=res[0], 
                                                   caption=f"🎬 **{res[1]}**\n🪙 **-5 Points**\n⚠️ **Auto-delete in 5 mins!**", 
                                                   protect_content=True)
                
                # Schedule deletion
                asyncio.create_task(schedule_file_deletion(client, msg.id, uid, res[0], res[1]))
                
                await cb.answer("✅ File sent! (5 min auto-delete)", show_alert=True)
            else:
                await cb.answer("❌ File not found!", show_alert=True)

        elif data == "back_start":
            await start_cmd(client, cb.message)

        # Other callbacks remain same...
        elif data == "refer_info":
            bot_user = (await client.get_me()).username
            cr.execute("SELECT points FROM users WHERE user_id = ?", (uid,))
            pts = cr.fetchone()[0]
            link = f"https://t.me/{bot_user}?start={uid}"
            await cb.message.edit_text(
                f"🚀 **Refer & Earn**\n\n🪙 **Your Points:** {pts}\n\n"
                f"🔗 **Share:** `{link}`\n\n"
                "**+20 points per referral!**",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Menu", callback_data="back_start")]]),
                disable_web_page_preview=True
            )

        elif data == "show_wls":
            cr.execute("SELECT movie_name FROM watchlist WHERE user_id = ?", (uid,))
            res = cr.fetchall()
            text = "📑 **Watchlist:**\n\n" + "\n".join([f"🎬 {m[0]}" for m in res]) if res else "📑 Empty watchlist!"
            await cb.message.edit_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Menu", callback_data="back_start")]]))

        elif data.startswith("wls_"):
            m_id = data.split("_")[1]
            try:
                m_name = requests.get(f"https://api.themoviedb.org/3/movie/{m_id}?api_key={TMDB_KEY}").json().get('title', 'Movie')
            except: m_name = "Movie"
            cr.execute("INSERT INTO watchlist (user_id, movie_id, movie_name) VALUES (?, ?, ?)", (uid, m_id, m_name))
            db.commit()
            await cb.answer(f"✅ {m_name} added to watchlist!", show_alert=True)

        elif data.startswith("req_"):
            req_movie = data.split("_")[1]
            await client.send_message(ADMIN_ID, f"📢 **Movie Request:** {req_movie}\n👤 `{uid}`")
            await cb.answer("✅ Request sent to admin!", show_alert=True)

    except Exception as e:
        print(f"Callback Error: {e}")
        await cb.answer("⚠️ Error occurred!", show_alert=True)

# --- 15. BACKGROUND TASK - CLEAN EXPIRED FILES ---
async def clean_expired_files():
    while True:
        try:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cr.execute("SELECT message_id, chat_id FROM temp_files WHERE expire_time < ?", (now,))
            expired = cr.fetchall()
            for msg in expired:
                try:
                    await bot_app.delete_messages(msg[1], msg[0])
                except: pass
            cr.execute("DELETE FROM temp_files WHERE expire_time < ?", (now,))
            db.commit()
        except: pass
        await asyncio.sleep(60)  # Check every minute

# --- 16. LAUNCH ---
if __name__ == "__main__":
    print("🚀 PRO Movie Bot Starting...")
    print("✅ Anti-Piracy Active | Ban System | UPI Ready | Broadcast Photo")
    keep_alive()
    
    # Start background cleaner
    asyncio.create_task(clean_expired_files())
    
    bot_app.run()
