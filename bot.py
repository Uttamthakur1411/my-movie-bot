from flask import Flask
from threading import Thread
import os
import requests
import sqlite3
import asyncio
import random
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InlineQueryResultArticle, InputTextMessageContent

# --- 1. RENDER PORT BINDING (For 24/7 Deployment) ---
flask_app = Flask('')

@flask_app.route('/')
def home():
    return "Bot is alive and running smoothly!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    flask_app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_flask)
    t.start()

# --- 2. CONFIGURATION (Apne Credentials Daalein) ---
API_ID = 34976268
API_HASH = "3ccae7cee8251da06d019c49a6aedb9e
"
BOT_TOKEN = "8213871486:AAECaJwnXmup3JEwEnV2cAKMGl3NCl9Y6A4"
TMDB_KEY = "9309466d747d6bf6e91a81d01ec98cd0"
FORCE_SUB_CHANNEL = "Movies_Uttam_Official" 
ADMIN_ID = 5615686466 

bot_app = Client("Movie_Pro_Netflix_Final", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- 3. HARDENED DATABASE SETUP ---
db = sqlite3.connect("bot_data.db", check_same_thread=False)
cr = db.cursor()

def init_db():
    cr.execute("""CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER UNIQUE, joined_date TEXT, lang TEXT DEFAULT 'en', 
        points INTEGER DEFAULT 50, is_premium INTEGER DEFAULT 0, theme TEXT DEFAULT 'dark'
    )""")
    cr.execute("CREATE TABLE IF NOT EXISTS files (id INTEGER PRIMARY KEY AUTOINCREMENT, movie_name TEXT, file_id TEXT, clicks INTEGER DEFAULT 0)")
    cr.execute("CREATE TABLE IF NOT EXISTS watchlist (user_id INTEGER, movie_id TEXT, movie_name TEXT)")
    cr.execute("CREATE TABLE IF NOT EXISTS last_watch (user_id INTEGER UNIQUE, movie_name TEXT, file_id TEXT)")
    cr.execute("CREATE TABLE IF NOT EXISTS search_logs (query TEXT, count INTEGER DEFAULT 1)")
    db.commit()

init_db()

# --- 4. TMDB ENGINE (With Extra Details) ---
def get_tmdb_results(query):
    try:
        cr.execute("INSERT INTO search_logs (query) VALUES (?) ON CONFLICT(query) DO UPDATE SET count = count + 1", (query.lower(),))
        db.commit()
    except: pass # Ignore DB lock errors for analytics

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

# --- 5. STRICT AUTH & SUBSCRIPTION CHECK ---
async def check_auth(client, message):
    if not FORCE_SUB_CHANNEL: return True
    try:
        await client.get_chat_member(FORCE_SUB_CHANNEL, message.from_user.id)
        return True
    except Exception:
        btn = InlineKeyboardMarkup([[InlineKeyboardButton("Join Channel 📢", url=f"https://t.me/{FORCE_SUB_CHANNEL}")]])
        await message.reply_text("❌ **Access Denied!**\nBot use karne ke liye hamare channel ko join karein.", reply_markup=btn)
        return False

# --- 6. ADMIN PRO FEATURES (Broadcast, Stats & Add) ---
@bot_app.on_message(filters.command("broadcast") & filters.user(ADMIN_ID))
async def broadcast_handler(client, message):
    if not message.reply_to_message:
        return await message.reply_text("❌ Reply to a message to broadcast!")
    
    cr.execute("SELECT user_id FROM users")
    users = cr.fetchall()
    count = 0
    msg = await message.reply_text(f"🚀 Starting Broadcast to {len(users)} users...")
    
    for user in users:
        try:
            await message.reply_to_message.copy(user[0])
            count += 1
            await asyncio.sleep(0.1)
        except: pass
    await msg.edit(f"✅ **Broadcast Finished!**\nSent successfully to: {count} users.")

@bot_app.on_message(filters.command("stats") & filters.user(ADMIN_ID))
async def stats_handler(client, message):
    cr.execute("SELECT COUNT(*) FROM users")
    t_users = cr.fetchone()[0]
    cr.execute("SELECT COUNT(*) FROM files")
    t_files = cr.fetchone()[0]
    await message.reply_text(f"📊 **Bot Analytics:**\n\n👤 Total Users: {t_users}\n🎬 Total Movies: {t_files}")

@bot_app.on_message((filters.document | filters.video) & filters.user(ADMIN_ID))
async def smart_add_handler(client, message):
    if message.caption:
        m_name = message.caption.strip().lower()
        f_id = message.document.file_id if message.document else message.video.file_id
        try:
            cr.execute("INSERT INTO files (movie_name, file_id) VALUES (?, ?)", (m_name, f_id))
            db.commit()
            await message.reply_text(f"✅ **Auto-Added to DB!**\n🎬 Name: `{m_name}`")
        except Exception as e:
            await message.reply_text(f"❌ Error: {e}")
    else:
        f_id = message.document.file_id if message.document else message.video.file_id
        await message.reply_text(f"🆔 **File ID:** `{f_id}`\n\n(Tip: Add movie name in caption to auto-save)")

# --- 7. COMMANDS (Start, Refer, Watchlist, Continue) ---
@bot_app.on_message(filters.command("start") & filters.private)
async def start_cmd(client, message):
    uid = message.from_user.id
    now = datetime.now().strftime("%d-%m-%Y")
    
    if len(message.command) > 1 and message.command[1].isdigit():
        ref_id = int(message.command[1])
        cr.execute("SELECT user_id FROM users WHERE user_id = ?", (uid,))
        if not cr.fetchone() and ref_id != uid:
            cr.execute("UPDATE users SET points = points + 20 WHERE user_id = ?", (ref_id,))
            try: await client.send_message(ref_id, "🎁 **Referral Bonus!** Aapko 20 points mile naye user ke liye.")
            except: pass

    # Set default language explicitly
    cr.execute("INSERT OR IGNORE INTO users (user_id, joined_date, lang) VALUES (?, ?, 'en')", (uid, now))
    db.commit()

    cr.execute("SELECT lang FROM users WHERE user_id = ?", (uid,))
    user_lang = cr.fetchone()[0]

    if user_lang == 'en':
        welcome_text = f"🔥 **Welcome {message.from_user.first_name}!**\n\nI am an advanced Netflix-style movie bot.\n✅ Search & Stream\n✅ Create Watchlists\n✅ Earn Points"
    else:
        welcome_text = f"🔥 **Namaste {message.from_user.first_name}!**\n\nMain ek advanced movie bot hoon.\n✅ Filmein khojein aur dekhein\n✅ Watchlist banayein\n✅ Points kamayein"

    btns = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔥 Trending", callback_data="trending_data"), InlineKeyboardButton("📑 Watchlist", callback_data="show_wls")],
        [InlineKeyboardButton("🚀 Refer & Earn", callback_data="refer_info"), InlineKeyboardButton("🇺🇸 / 🇮🇳 Change Lang", callback_data="change_lang")]
    ])
    await message.reply_text(welcome_text, reply_markup=btns)

@bot_app.on_message(filters.command("watchlist") & filters.private)
async def show_watchlist_cmd(client, message):
    if not await check_auth(client, message): return
    uid = message.from_user.id
    cr.execute("SELECT movie_name FROM watchlist WHERE user_id = ?", (uid,))
    res = cr.fetchall()
    if not res: return await message.reply_text("📑 Aapki watchlist abhi khali hai. Movies search karke '+' dabayein!")
    
    text = "📑 **Your Watchlist:**\n\n" + "\n".join([f"🎬 {m[0]}" for m in res])
    await message.reply_text(text)

@bot_app.on_message(filters.command("continue") & filters.private)
async def continue_cmd(client, message):
    if not await check_auth(client, message): return
    cr.execute("SELECT movie_name, file_id FROM last_watch WHERE user_id = ?", (message.from_user.id,))
    res = cr.fetchone()
    if res:
        try:
            await client.send_cached_media(chat_id=message.chat.id, file_id=res[1], caption=f"⏯ **Resume:** {res[0]}", protect_content=True)
        except:
            await message.reply_text("❌ File unavailable or deleted.")
    else:
        await message.reply_text("❌ Aapne abhi tak koi movie download nahi ki hai.")

# --- 8. MOVIE SEARCH ENGINE (Strict Restrictions Applied) ---
@bot_app.on_message(filters.text & filters.private & ~filters.me)
async def movie_search(client, message):
    if message.text.startswith("/") or len(message.text) < 2: return
    if not await check_auth(client, message): return

    query = message.text.lower().strip()
    status = await message.reply_text("🔎 **Searching...**")

    # Local DB Check
    cr.execute("SELECT id, movie_name, file_id FROM files WHERE movie_name LIKE ?", (f"%{query}%",))
    local_data = cr.fetchone()
    
    # TMDB Check
    results = get_tmdb_results(query)

    if not results and not local_data:
        btn = InlineKeyboardMarkup([[InlineKeyboardButton("🎟 Request Movie", callback_data=f"req_{query[:20]}")]])
        return await status.edit(f"❌ **'{query}'** not found in database.", reply_markup=btn)

    # Compile data
    item = results[0] if results else {'id': 0, 'title': local_data[1], 'media_type': 'movie'}
    m_id, m_type = item.get('id', 0), item.get('media_type', 'movie')
    title = item.get('title') or item.get('name')
    genres, runtime, cast = get_extra_details(m_type, m_id)
    poster = f"https://image.tmdb.org/t/p/w500{item.get('poster_path')}" if item.get('poster_path') else "https://telegra.ph/file/default.jpg"

    caption = (f"🎬 **{title}**\n\n🎭 **Genre:** {genres}\n⏳ **Runtime:** {runtime}\n"
               f"⭐ **Rating:** {item.get('vote_average', 'N/A')}/10\n👥 **Cast:** {cast}\n\n"
               f"✨ **Powered By Thakur Uttam**")

    btns = [
        [
            InlineKeyboardButton("📺 Play Online", url=f"https://vidsrc.me/embed/{m_type}/{m_id}"),
            InlineKeyboardButton("🎬 Trailer", url=f"https://www.youtube.com/results?search_query={title.replace(' ', '+')}+trailer")
        ],
        [InlineKeyboardButton("➕ Add Watchlist", callback_data=f"wls_{m_id}")]
    ]
    
    if local_data:
        btns.insert(0, [InlineKeyboardButton("📥 Download Movie (5 Points)", callback_data=f"dl_{local_data[0]}")] )

    try:
        await message.reply_photo(photo=poster, caption=caption, reply_markup=InlineKeyboardMarkup(btns))
        await status.delete()
    except Exception:
        await status.edit(caption, reply_markup=InlineKeyboardMarkup(btns))

# --- 9. CALLBACK HANDLERS ---
@bot_app.on_callback_query()
async def handle_callbacks(client, cb):
    uid = cb.from_user.id
    data = cb.data
    
    try:
        if data == "trending_data":
            res = requests.get(f"https://api.themoviedb.org/3/trending/all/day?api_key={TMDB_KEY}").json().get('results', [])[:10]
            text = "🔥 **Top 10 Trending Today:**\n\n"
            for i, m in enumerate(res, 1): text += f"{i}. {m.get('title') or m.get('name')}\n"
            await cb.message.edit_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back_start")]]))

        elif data == "refer_info":
            bot_user = (await client.get_me()).username
            cr.execute("SELECT points FROM users WHERE user_id = ?", (uid,))
            pts = cr.fetchone()[0]
            link = f"https://t.me/{bot_user}?start={uid}"
            await cb.message.edit_text(f"🚀 **Referral System**\n\n🪙 Your Points: **{pts}**\n\nShare this link to get 20 points per join:\n`{link}`", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back_start")]]))

        elif data == "show_wls":
            cr.execute("SELECT movie_name FROM watchlist WHERE user_id = ?", (uid,))
            res = cr.fetchall()
            text = "📑 **Your Watchlist:**\n\n" + "\n".join([f"🎬 {m[0]}" for m in res]) if res else "📑 Watchlist is empty!"
            await cb.message.edit_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back_start")]]))

        elif data == "change_lang":
            btns = InlineKeyboardMarkup([[InlineKeyboardButton("English 🇺🇸", callback_data="setlang_en"), InlineKeyboardButton("Hindi 🇮🇳", callback_data="setlang_hi")]])
            await cb.message.edit_text("🌍 Select your language:", reply_markup=btns)

        elif data.startswith("setlang_"):
            lang = data.split("_")[1]
            cr.execute("UPDATE users SET lang = ? WHERE user_id = ?", (lang, uid))
            db.commit()
            msg = "✅ Language locked to English!" if lang == "en" else "✅ Bhasha Hindi par set ho gayi hai!"
            await cb.answer(msg, show_alert=True)
            await start_cmd(client, cb.message) # Restart menu

        elif data.startswith("req_"):
            req_movie = data.split("_")[1]
            await client.send_message(ADMIN_ID, f"📢 **Movie Request:** {req_movie}\n👤 **User ID:** `{uid}`")
            await cb.answer("✅ Request sent to Admin!", show_alert=True)

        elif data.startswith("wls_"):
            m_id = data.split("_")[1]
            try:
                m_name = requests.get(f"https://api.themoviedb.org/3/movie/{m_id}?api_key={TMDB_KEY}").json().get('title', 'Unknown')
            except: m_name = "Saved Movie"
            
            cr.execute("INSERT INTO watchlist (user_id, movie_id, movie_name) VALUES (?, ?, ?)", (uid, m_id, m_name))
            db.commit()
            await cb.answer(f"✅ Added {m_name} to Watchlist!", show_alert=True)

        elif data.startswith("dl_"):
            # Fetch points
            cr.execute("SELECT points FROM users WHERE user_id = ?", (uid,))
            points_row = cr.fetchone()
            points = points_row[0] if points_row else 0
            
            if points < 5:
                return await cb.answer("❌ Kam se kam 5 points chahiye! /refer karke points badhayein.", show_alert=True)
            
            file_db_id = data.split("_")[1]
            cr.execute("SELECT file_id, movie_name FROM files WHERE id = ?", (file_db_id,))
            res = cr.fetchone()
            
            if res:
                # Deduct points & Update Last Watch
                cr.execute("UPDATE users SET points = points - 5 WHERE user_id = ?", (uid,))
                cr.execute("INSERT OR REPLACE INTO last_watch (user_id, movie_name, file_id) VALUES (?, ?, ?)", (uid, res[1], res[0]))
                db.commit()
                
                await client.send_cached_media(chat_id=uid, file_id=res[0], caption=f"🎬 **File:** {res[1]}\n🪙 5 Points deducted.", protect_content=True)
                await cb.answer("✅ Check your chat! File sent.", show_alert=True)
            else:
                await cb.answer("❌ File missing from database.", show_alert=True)

        elif data == "back_start":
            await start_cmd(client, cb.message)

    except Exception as e:
        print(f"Callback Error: {e}")
        await cb.answer("⚠️ An error occurred.", show_alert=True)

# --- 10. LAUNCH ---
if __name__ == "__main__":
    print("🚀 PRO Bot is starting with strict restrictions...")
    keep_alive()
    bot_app.run()
