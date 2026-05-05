from flask import Flask
from threading import Thread
import os
import requests
import sqlite3
import asyncio
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import FloodWait, UserNotParticipant

# --- 1. RENDER PORT BINDING ---
flask_app = Flask('')

@flask_app.route('/')
def home():
    return "✅ Movie Bot ALIVE & RUNNING 24/7!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    flask_app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_flask, daemon=True)
    t.start()

# --- 2. CONFIG (CHANGE THESE) ---
API_ID = int(os.environ.get("API_ID", "YOUR_API_ID"))
API_HASH = os.environ.get("API_HASH", "YOUR_API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN")
TMDB_KEY = "9309466d747d6bf6e91a81d01ec98cd0"
FORCE_SUB_CHANNEL = "Movies_Uttam_Official"
ADMIN_ID = 5615686466

bot_app = Client("MovieBotPro", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- 3. DATABASE ---
db = sqlite3.connect("bot_data.db", check_same_thread=False)
cr = db.cursor()

def init_db():
    cr.execute("""CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY, joined_date TEXT, lang TEXT DEFAULT 'en', 
        points INTEGER DEFAULT 50, is_premium INTEGER DEFAULT 0
    )""")
    cr.execute("""CREATE TABLE IF NOT EXISTS files (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        movie_name TEXT, file_id TEXT, clicks INTEGER DEFAULT 0
    )""")
    cr.execute("CREATE TABLE IF NOT EXISTS watchlist (user_id INTEGER, movie_id TEXT, movie_name TEXT)")
    cr.execute("CREATE TABLE IF NOT EXISTS last_watch (user_id INTEGER PRIMARY KEY, movie_name TEXT, file_id TEXT)")
    cr.execute("CREATE TABLE IF NOT EXISTS search_logs (query TEXT PRIMARY KEY, count INTEGER DEFAULT 1)")
    db.commit()

init_db()

# --- 4. TMDB API ---
def get_tmdb_results(query):
    try:
        cr.execute("INSERT OR REPLACE INTO search_logs (query, count) VALUES (?, COALESCE((SELECT count FROM search_logs WHERE query=?), 0) + 1)", 
                  (query.lower(), query.lower()))
        db.commit()
    except: pass

    url = f"https://api.themoviedb.org/3/search/multi?api_key={TMDB_KEY}&query={query}&include_adult=false&language=en-US"
    try:
        response = requests.get(url, timeout=10)
        data = response.json()
        return [r for r in data.get('results', []) if r.get('media_type') in ['movie', 'tv']]
    except:
        return []

def get_movie_details(m_type, m_id):
    url = f"https://api.themoviedb.org/3/{m_type}/{m_id}?api_key={TMDB_KEY}&language=en-US&append_to_response=credits"
    try:
        res = requests.get(url, timeout=10).json()
        genres = ", ".join([g['name'] for g in res.get('genres', [])[:3]]) or "N/A"
        runtime = f"{res.get('runtime', 0)} mins" if m_type == 'movie' else f"{res.get('episode_run_time', [0])[0] or 0} min/ep"
        cast = ", ".join([c['name'] for c in res.get('credits', {}).get('cast', [])[:4]]) or "N/A"
        return genres, runtime, cast
    except:
        return "Action", "120 mins", "Hollywood Stars"

# --- 5. FORCE SUB CHECK ---
async def check_auth(client, user_id):
    if not FORCE_SUB_CHANNEL:
        return True
    try:
        await client.get_chat_member(FORCE_SUB_CHANNEL, user_id)
        return True
    except UserNotParticipant:
        return False
    except:
        return True

# --- 6. ADMIN COMMANDS ---
@bot_app.on_message(filters.command("stats") & filters.user(ADMIN_ID))
async def stats_cmd(client, message):
    cr.execute("SELECT COUNT(*) FROM users")
    users = cr.fetchone()[0]
    cr.execute("SELECT COUNT(*) FROM files")
    files = cr.fetchone()[0]
    cr.execute("SELECT SUM(points) FROM users")
    total_points = cr.fetchone()[0] or 0
    text = f"📊 **BOT STATS**\n\n👥 Users: `{users}`\n🎬 Movies: `{files}`\n💰 Total Points: `{total_points}`"
    await message.reply_text(text)

@bot_app.on_message((filters.document | filters.video) & filters.user(ADMIN_ID))
async def add_movie(client, message):
    if message.caption:
        name = message.caption.strip()
        file_id = message.document.file_id if message.document else message.video.file_id
        try:
            cr.execute("INSERT INTO files (movie_name, file_id) VALUES (?, ?)", (name.lower(), file_id))
            db.commit()
            await message.reply_text(f"✅ **Movie Added!**\n🎬 `{name}`\n🆔 `{file_id[:20]}...`")
        except:
            await message.reply_text("❌ **Error adding movie!**")

# --- 7. START COMMAND (FIXED) ---
@bot_app.on_message(filters.command("start") & filters.private)
async def start_handler(client, message):
    uid = message.from_user.id
    name = message.from_user.first_name or "User"
    
    # Referral System FIXED
    if len(message.command) > 1:
        try:
            ref_id = int(message.command[1])
            if ref_id != uid:
                cr.execute("INSERT OR IGNORE INTO users (user_id, joined_date, points) VALUES (?, ?, 50)", (ref_id, datetime.now().strftime("%Y-%m-%d")))
                cr.execute("UPDATE users SET points = points + 20 WHERE user_id = ?", (ref_id,))
                db.commit()
                try:
                    await client.send_message(ref_id, f"🎁 **+20 Points!**\nNew user joined via your referral!")
                except: pass
        except: pass
    
    # Add user
    cr.execute("INSERT OR IGNORE INTO users (user_id, joined_date, points) VALUES (?, ?, 50)", 
              (uid, datetime.now().strftime("%Y-%m-%d")))
    db.commit()
    
    # Check subscription
    if not await check_auth(client, uid):
        btn = InlineKeyboardMarkup([[InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{FORCE_SUB_CHANNEL}")]])
        return await message.reply_text(
            "🔒 **JOIN CHANNEL FIRST!**\n\nBot use करने के लिए channel join करें:",
            reply_markup=btn
        )
    
    # Main menu
    btns = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔥 Trending", callback_data="trending"), 
         InlineKeyboardButton("📱 Watchlist", callback_data="watchlist")],
        [InlineKeyboardButton("💰 My Points", callback_data="points"), 
         InlineKeyboardButton("⏯️ Continue", callback_data="continue")],
        [InlineKeyboardButton("🚀 Refer & Earn", callback_data="refer")]
    ])
    
    text = f"""🔥 **Welcome {name}!**

🎬 **Netflix Style Movie Bot**
✅ Search Movies
✅ Download Files (5 Points)
✅ Watchlist & Continue
✅ Referral System

**Search any movie name to start!**"""
    
    await message.reply_text(text, reply_markup=btns)

# --- 8. WATCHLIST COMMAND ---
@bot_app.on_message(filters.command("watchlist") & filters.private)
async def watchlist_cmd(client, message):
    if not await check_auth(client, message.from_user.id):
        return
    uid = message.from_user.id
    cr.execute("SELECT movie_name FROM watchlist WHERE user_id=? ORDER BY rowid DESC LIMIT 10", (uid,))
    movies = cr.fetchall()
    if not movies:
        return await message.reply_text("📱 **Watchlist Empty!**\nSearch movies and click ➕")
    
    text = "📱 **Your Watchlist:**\n\n"
    for i, movie in enumerate(movies, 1):
        text += f"{i}. 🎬 {movie[0]}\n"
    await message.reply_text(text)

# --- 9. CONTINUE COMMAND (FIXED) ---
@bot_app.on_message(filters.command("continue") & filters.private)
async def continue_cmd(client, message):
    if not await check_auth(client, message.from_user.id):
        return
    uid = message.from_user.id
    cr.execute("SELECT movie_name, file_id FROM last_watch WHERE user_id=?", (uid,))
    data = cr.fetchone()
    if data:
        try:
            await client.send_cached_media(
                message.chat.id, 
                file_id=data[1], 
                caption=f"⏯️ **Continue Watching:** {data[0]}\n💾 Saved progress"
            )
        except:
            await message.reply_text("❌ **File not available!**\nDownload again.")
    else:
        await message.reply_text("❌ **No saved movie!**\nDownload first.")

# --- 10. MOVIE SEARCH (ENGLISH ONLY) ---
@bot_app.on_message(filters.text & filters.private & ~filters.command(["start", "help", "watchlist", "continue"]))
async def search_handler(client, message):
    if not await check_auth(client, message.from_user.id):
        return
        
    query = message.text.strip()
    if len(query) < 2:
        return
        
    await message.reply_chat_action("typing")
    status_msg = await message.reply_text("🔎 **Searching movies...**")
    
    # Local files first
    cr.execute("SELECT id, movie_name, file_id FROM files WHERE LOWER(movie_name) LIKE ? LIMIT 1", (f"%{query.lower()}%",))
    local_file = cr.fetchone()
    
    # TMDB search
    tmdb_results = get_tmdb_results(query)
    
    if not tmdb_results and not local_file:
        await status_msg.edit_text(f"❌ **'{query}'** not found!\nTry: Avengers, Pushpa, RRR")
        return
    
    # Movie details
    if tmdb_results:
        movie = tmdb_results[0]
        mid = movie.get('id')
        mtype = movie.get('media_type', 'movie')
        title = movie.get('title') or movie.get('name') or "Unknown"
        poster = f"https://image.tmdb.org/t/p/w500{movie.get('poster_path')}" if movie.get('poster_path') else None
        rating = movie.get('vote_average', 0)
        
        genres, runtime, cast = get_movie_details(mtype, mid)
        
        caption = f"""🎬 **{title}**
⭐ **{rating:.1f}/10**
🎭 **{genres}**
⏱️ **{runtime}**
👨‍🎤 **{cast}**"""
        
        # Buttons
        btns = [
            [InlineKeyboardButton("📺 Watch Online", url=f"https://vidsrc.me/embed/{mtype}/{mid}")],
            [InlineKeyboardButton("🎥 Trailer", url=f"https://www.youtube.com/results?search_query={title}+trailer")],
            [InlineKeyboardButton("➕ Add Watchlist", callback_data=f"wl_{mid}_{title}")],
        ]
        
        if local_file:
            btns.insert(0, [InlineKeyboardButton("📥 Download (5 Points)", callback_data=f"dl_{local_file[0]}")])
        
        try:
            if poster:
                await message.reply_photo(poster, caption=caption, reply_markup=InlineKeyboardMarkup(btns))
            else:
                await message.reply_text(caption, reply_markup=InlineKeyboardMarkup(btns))
        except:
            await message.reply_text(caption, reply_markup=InlineKeyboardMarkup(btns))
    else:
        # Only local file
        file_id, name = local_file[2], local_file[1]
        btns = [[InlineKeyboardButton("📥 Download Movie (5 Points)", callback_data=f"dl_{local_file[0]}")]]
        await status_msg.edit_text(f"🎬 **{name.title()}**\n\n📥 **Available for Download!**", reply_markup=InlineKeyboardMarkup(btns))
    
    await status_msg.delete()

# --- 11. CALLBACK HANDLERS (ALL FIXED) ---
@bot_app.on_callback_query()
async def callback_handler(client, cb):
    uid = cb.from_user.id
    data = cb.data
    
    try:
        if data == "trending":
            movies = get_tmdb_results("trending")
            if movies:
                text = "🔥 **TRENDING MOVIES:**\n\n"
                for i, m in enumerate(movies[:8], 1):
                    title = m.get('title') or m.get('name')
                    text += f"{i}. {title}\n"
                btn = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main")]])
                await cb.message.edit_text(text, reply_markup=btn)
            await cb.answer()
            
        elif data == "watchlist":
            cr.execute("SELECT movie_name FROM watchlist WHERE user_id=? LIMIT 10", (uid,))
            movies = cr.fetchall()
            if movies:
                text = "📱 **Watchlist:**\n\n" + "\n".join([f"• {m[0]}" for m in movies])
            else:
                text = "📱 **Empty Watchlist!**"
            await cb.message.edit_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main")]]))
            
        elif data == "points":
            cr.execute("SELECT points FROM users WHERE user_id=?", (uid,))
            pts = cr.fetchone()[0] or 0
            bot_username = (await client.get_me()).username
            ref_link = f"https://t.me/{bot_username}?start={uid}"
            text = f"💰 **Your Points: `{pts}`**\n\nShare: `{ref_link}`\n*Get 20 points per referral!*"
            await cb.message.edit_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main")]]))
            
        elif data == "continue":
            cr.execute("SELECT movie_name, file_id FROM last_watch WHERE user_id=?", (uid,))
            data = cr.fetchone()
            if data:
                text = f"⏯️ **Last Movie:** {data[0]}\n\n✅ Use /continue command"
            else:
                text = "⏯️ **No saved movie!**"
            await cb.message.edit_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main")]]))
            
        elif data == "refer":
            cr.execute("SELECT points FROM users WHERE user_id=?", (uid,))
            pts = cr.fetchone()[0] or 0
            bot_username = (await client.get_me()).username
            ref_link = f"https://t.me/{bot_username}?start={uid}"
            text = f"""🚀 **REFERRAL SYSTEM**
💰 **Your Points:** `{pts}`
🎁 **20 Points per referral!**

**Share Link:**
`{ref_link}`"""
            await cb.message.edit_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main")]]))
            
        elif data == "main":
            await start_handler(client, cb.message)
            
        elif data.startswith("wl_"):
            _, mid, title = data.split("_", 2)
            cr.execute("INSERT OR IGNORE INTO watchlist (user_id, movie_id, movie_name) VALUES (?, ?, ?)", 
                      (uid, mid, title))
            db.commit()
            await cb.answer(f"✅ {title[:30]}... added to watchlist!")
            
        elif data.startswith("dl_"):
            # Points check
            cr.execute("SELECT points FROM users WHERE user_id=?", (uid,))
            points = cr.fetchone()[0] or 0
            
            if points < 5:
                return await cb.answer("❌ **Need 5 points!** Use referral system.", show_alert=True)
            
            file_id = int(data.split("_")[1])
            cr.execute("SELECT file_id, movie_name FROM files WHERE id=?", (file_id,))
            file_data = cr.fetchone()
            
            if file_data:
                fileid, name = file_data
                # Deduct points
                cr.execute("UPDATE users SET points = points - 5 WHERE user_id=?", (uid,))
                # Save to last watch
                cr.execute("INSERT OR REPLACE INTO last_watch VALUES (?, ?, ?)", (uid, name, fileid))
                db.commit()
                
                await client.send_cached_media(uid, fileid, caption=f"🎬 **{name.title()}**\n💰 -5 Points\n⏯️ Auto-saved to continue")
                await cb.answer("✅ **Check your saved messages!**")
            else:
                await cb.answer("❌ **File not found!**", show_alert=True)
                
    except Exception as e:
        print(f"Callback error: {e}")
        await cb.answer("⚠️ Something went wrong!", show_alert=True)

# --- 12. START BOT ---
if __name__ == "__main__":
    print("🚀 Starting Movie Bot Pro...")
    keep_alive()
    print("✅ Keep-alive server running")
    bot_app.run()
    print("✅ Bot started successfully!")
