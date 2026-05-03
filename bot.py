from flask import Flask
from threading import Thread
import os
import requests
import sqlite3
import asyncio
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InlineQueryResultArticle, InputTextMessageContent

# --- 1. RENDER PORT BINDING ---
flask_app = Flask('')

@flask_app.route('/')
def home():
    return "Bot is alive and kicking with AI DNA & Scene Search!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    flask_app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_flask)
    t.start()

# --- 2. CONFIGURATION ---
API_ID = 34976268
API_HASH = "3ccae7cee8251da06d019c49a6aedb9e"
BOT_TOKEN = "8213871486:AAG7UjcvDCEWA8kxLsQinllOcGSplZKVT2s"
TMDB_KEY = "9309466d747d6bf6e91a81d01ec98cd0"
FORCE_SUB_CHANNEL = "Movies_Uttam_Official" 
ADMIN_ID = 5615686466 

bot_app = Client("Movie_Pro_Netflix_Final", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- 3. DATABASE SETUP (Fully Integrated) ---
db = sqlite3.connect("bot_data.db", check_same_thread=False)
cr = db.cursor()

def init_db():
    # Purane features ke columns + New Features (dna_score, tags)
    cr.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER UNIQUE, joined_date TEXT, lang TEXT, referred_by INTEGER, points INTEGER DEFAULT 0, theme TEXT DEFAULT 'dark', dna_score TEXT DEFAULT 'Explorer')")
    cr.execute("CREATE TABLE IF NOT EXISTS files (id INTEGER PRIMARY KEY AUTOINCREMENT, movie_name TEXT, file_id TEXT, tags TEXT)")
    cr.execute("CREATE TABLE IF NOT EXISTS watchlist (user_id INTEGER, movie_id TEXT, movie_name TEXT)")
    cr.execute("CREATE TABLE IF NOT EXISTS last_watch (user_id INTEGER UNIQUE, movie_name TEXT, file_id TEXT)")
    
    # Safety Check: Agar purana DB hai toh tags column add karna
    try: cr.execute("ALTER TABLE files ADD COLUMN tags TEXT")
    except: pass
    try: cr.execute("ALTER TABLE users ADD COLUMN dna_score TEXT DEFAULT 'Explorer'")
    except: pass
    
    db.commit()

init_db()

# --- 4. TMDB ENGINE ---
def get_tmdb_results(query):
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

# --- 5. AUTH & SUBSCRIPTION ---
async def is_subscribed(client, message):
    if not FORCE_SUB_CHANNEL: return True
    try:
        await client.get_chat_member(FORCE_SUB_CHANNEL, message.from_user.id)
        return True
    except:
        btn = InlineKeyboardMarkup([[InlineKeyboardButton("Join Channel 📢", url=f"https://t.me/{FORCE_SUB_CHANNEL}")]])
        await message.reply_text("❌ **Bot use karne ke liye channel join karein!**", reply_markup=btn)
        return False

# --- 6. ADMIN COMMANDS (Updated with Tag Support) ---
@bot_app.on_message(filters.command("add") & filters.user(ADMIN_ID))
async def add_movie_handler(client, message):
    try:
        input_str = message.text.split(" ", 1)[1]
        # Logic: Name | ID | Tags(Optional)
        parts = input_str.split("|")
        m_name = parts[0].strip().lower()
        f_id = parts[1].strip()
        tags = parts[2].strip().lower() if len(parts) > 2 else ""
        
        cr.execute("INSERT INTO files (movie_name, file_id, tags) VALUES (?, ?, ?)", (m_name, f_id, tags))
        db.commit()
        await message.reply_text(f"✅ **Database Updated!**\n🎬 **Movie:** `{m_name}`\n🏷 **Tags:** `{tags or 'None'}`")
    except:
        await message.reply_text("❌ **Usage:** `/add Movie Name | file_id | tags` (Tags are optional)")

@bot_app.on_message((filters.document | filters.video) & filters.user(ADMIN_ID))
async def smart_add_handler(client, message):
    if message.caption:
        m_name = message.caption.strip().lower()
        f_id = message.document.file_id if message.document else message.video.file_id
        cr.execute("INSERT INTO files (movie_name, file_id) VALUES (?, ?)", (m_name, f_id))
        db.commit()
        await message.reply_text(f"✅ **Auto-Added to DB!**\n🎬 **Name:** `{m_name}`")
        
        cr.execute("SELECT user_id FROM users")
        users = cr.fetchall()
        for user in users:
            try: await client.send_message(user[0], f"🎉 **New Movie Added:** {m_name.upper()}\nSearch now to download!")
            except: pass
    else:
        f_id = message.document.file_id if message.document else message.video.file_id
        await message.reply_text(f"🆔 **File ID:** `{f_id}`\n\n(Tip: Caption mein naam likh kar forward karein add karne ke liye)")

# --- 7. TRENDING FEATURE ---
@bot_app.on_message(filters.command("trending"))
async def trending_cmd(client, message):
    if not await is_subscribed(client, message): return
    url = f"https://api.themoviedb.org/3/trending/all/day?api_key={TMDB_KEY}"
    try:
        res = requests.get(url).json().get('results', [])[:10]
        text = "🔥 **Trending Today:**\n\n"
        for i, m in enumerate(res, 1):
            name = m.get('title') or m.get('name')
            text += f"{i}. {name} ({m.get('media_type', '').upper()})\n"
        await message.reply_text(text)
    except:
        await message.reply_text("❌ Error fetching trending movies.")

# --- 8. START & REFERRAL SYSTEM ---
@bot_app.on_message(filters.command("start"))
async def start_cmd(client, message):
    uid = message.from_user.id
    now = datetime.now().strftime("%d-%m-%Y")
    
    if len(message.command) > 1 and message.command[1].isdigit():
        ref_id = int(message.command[1])
        if ref_id != uid:
            cr.execute("SELECT user_id FROM users WHERE user_id = ?", (uid,))
            if not cr.fetchone(): 
                cr.execute("UPDATE users SET points = points + 10 WHERE user_id = ?", (ref_id,))
                try: await client.send_message(ref_id, "🎁 **Referral Reward!** You got 10 points for inviting a friend.")
                except: pass
    
    cr.execute("INSERT OR IGNORE INTO users (user_id, joined_date) VALUES (?, ?)", (uid, now))
    db.commit()

    btns = InlineKeyboardMarkup([
        [InlineKeyboardButton("English 🇺🇸", callback_data="setlang_en"),
         InlineKeyboardButton("Hindi 🇮🇳", callback_data="setlang_hi")],
        [InlineKeyboardButton("🧬 Movie DNA", callback_data="view_dna"),
         InlineKeyboardButton("🎨 Settings", callback_data="open_settings")]
    ])
    
    await message.reply_text(
        f"👋 **Namaste {message.from_user.first_name}!**\n\n"
        "Welcome to Netflix Pro Bot. Select your language:",
        reply_markup=btns
    )

@bot_app.on_message(filters.command("refer"))
async def refer_cmd(client, message):
    bot_username = (await client.get_me()).username
    ref_link = f"https://t.me/{bot_username}?start={message.from_user.id}"
    await message.reply_text(f"🚀 **Your Referral Link:**\n`{ref_link}`\n\nInviting friends gives you points!")

# --- 9. NEW: ADVANCED FEATURES (Find Scene, DNA, WatchParty) ---
@bot_app.on_message(filters.command("find"))
async def find_scene(client, message):
    if not await is_subscribed(client, message): return
    if len(message.command) < 2:
        return await message.reply_text("❌ Usage: `/find hero train fight`")
    
    query = message.text.split(" ", 1)[1].lower()
    status = await message.reply_text("🔎 **Searching Scene...**")
    
    cr.execute("SELECT id, movie_name FROM files WHERE tags LIKE ?", (f"%{query}%",))
    res = cr.fetchall()
    
    if res:
        text = f"🎯 **Found Movies matching scene:**\n\n"
        btns = []
        for m in res[:5]:
            text += f"🎬 **{m[1].upper()}**\n"
            btns.append([InlineKeyboardButton(f"Get {m[1]}", callback_data=f"dl_{m[0]} text")])
        await status.edit(text, reply_markup=InlineKeyboardMarkup(btns))
    else:
        await status.edit("❌ No movie found for this scene description.")

@bot_app.on_message(filters.command("mydna"))
async def my_dna(client, message):
    uid = message.from_user.id
    cr.execute("SELECT dna_score FROM users WHERE user_id = ?", (uid,))
    res = cr.fetchone()
    dna = res[0] if res else "Explorer"
    await message.reply_text(f"🧬 **Your Movie DNA Profile:**\n\nStatus: **{dna}**\n\nAnalyze your taste with every download!")

@bot_app.on_message(filters.command("watchparty"))
async def watchparty(client, message):
    room_id = f"party_{message.from_user.id}"
    btn = InlineKeyboardMarkup([[InlineKeyboardButton("Join Now 🍿", url=f"https://t.me/share/url?url=Watch+Together+Room:+{room_id}")]])
    await message.reply_text("🎉 **Watch Party Created!**\nInvite friends to sync play.", reply_markup=btn)

# --- 10. NETFLIX STYLE INLINE SEARCH ---
@bot_app.on_inline_query()
async def inline_netflix_search(client, query):
    if not query.query:
        results = []
        cr.execute("SELECT movie_name FROM last_watch WHERE user_id = ?", (query.from_user.id,))
        hist = cr.fetchone()
        if hist:
            results.append(InlineQueryResultArticle(title=f"⏯ Resume: {hist[0]}", input_message_content=InputTextMessageContent("/continue"), description="Continue watching your last movie"))
        
        trending = requests.get(f"https://api.themoviedb.org/3/trending/all/day?api_key={TMDB_KEY}").json().get('results', [])[:5]
        for m in trending:
            name = m.get('title') or m.get('name')
            results.append(InlineQueryResultArticle(title=f"🔥 {name}", input_message_content=InputTextMessageContent(name)))
        
        await query.answer(results, cache_time=1)
        return

    tmdb_res = get_tmdb_results(query.query)
    results = []
    for m in tmdb_res[:10]:
        title = m.get('title') or m.get('name')
        results.append(InlineQueryResultArticle(
            title=title,
            description=f"⭐ {m.get('vote_average', 'N/A')}/10 | {m.get('media_type', 'movie').upper()}",
            input_message_content=InputTextMessageContent(title),
            thumb_url=f"https://image.tmdb.org/t/p/w200{m.get('poster_path')}" if m.get('poster_path') else None
        ))
    await query.answer(results)

# --- 11. MOVIE SEARCH (Standard) ---
@bot_app.on_message(filters.text & ~filters.command(["start", "add", "watchlist", "trending", "refer", "continue", "settings", "find", "mydna", "watchparty"]))
async def movie_search(client, message):
    if not await is_subscribed(client, message): return
    
    cr.execute("SELECT lang FROM users WHERE user_id = ?", (message.from_user.id,))
    user_lang = cr.fetchone()
    if not user_lang or not user_lang[0]:
        return await message.reply_text("❌ Please /start and select language.")

    query = message.text.lower().strip()
    status = await message.reply_text("🔎 Searching...")
    
    cr.execute("SELECT file_id, id, movie_name FROM files WHERE movie_name LIKE ?", (f"%{query}%",))
    local_data = cr.fetchone()
    results = get_tmdb_results(query)

    if not results and not local_data:
        btn = InlineKeyboardMarkup([[InlineKeyboardButton("🎟 Request File", callback_data=f"req_{query[:15]}")]])
        return await status.edit(f"❌ '{query}' not found.", reply_markup=btn)

    item = results[0] if results else {'id': 0, 'title': local_data[2], 'media_type': 'movie'}
    m_id, m_type = item.get('id', 0), item.get('media_type', 'movie')
    title = item.get('title') or item.get('name')
    genres, runtime, cast = get_extra_details(m_type, m_id)
    poster_path = item.get('poster_path')
    poster = f"https://image.tmdb.org/t/p/w500{poster_path}" if poster_path else "https://telegra.ph/file/default.jpg"

    caption = (f"🎬 **{title}**\n\n🎭 **Genre:** {genres}\n⏳ **Runtime:** {runtime}\n"
               f"⭐ **Rating:** {item.get('vote_average', 'N/A')}/10\n👥 **Cast:** {cast}\n\n"
               f"✨ **Powered By Thakur Uttam**")

    btns = [[
        InlineKeyboardButton("📺 Stream Online", url=f"https://vidsrc.me/embed/{m_type}/{m_id}"),
        InlineKeyboardButton("🎬 Trailer", url=f"https://www.youtube.com/results?search_query={title.replace(' ', '+')}+trailer")
    ]]
    
    if local_data:
        btns.insert(0, [InlineKeyboardButton("📥 Download Movie", callback_data=f"dl_{local_data[1]}")] )
    
    btns.append([InlineKeyboardButton("➕ Add Watchlist", callback_data=f"wls_{m_type}_{m_id}")])

    try:
        await message.reply_photo(photo=poster, caption=caption, reply_markup=InlineKeyboardMarkup(btns))
        await status.delete()
    except:
        await status.edit(caption, reply_markup=InlineKeyboardMarkup(btns))

# --- 12. WATCHLIST & CONTINUE ---
@bot_app.on_message(filters.command("watchlist"))
async def show_watchlist(client, message):
    if not await is_subscribed(client, message): return
    uid = message.from_user.id
    cr.execute("SELECT movie_name FROM watchlist WHERE user_id = ?", (uid,))
    res = cr.fetchall()
    if not res: return await message.reply_text("📑 Watchlist is empty!")
    text = "📑 **Your Watchlist:**\n\n" + "\n".join([f"{i+1}. {m[0].title()}" for i, m in enumerate(res)])
    await message.reply_text(text)

@bot_app.on_message(filters.command("continue"))
async def continue_cmd(client, message):
    cr.execute("SELECT movie_name, file_id FROM last_watch WHERE user_id = ?", (message.from_user.id,))
    res = cr.fetchone()
    if res: await client.send_cached_media(chat_id=message.chat.id, file_id=res[1], caption=f"⏯ **Resume:** {res[0]}", protect_content=True)
    else: await message.reply_text("❌ No history found.")

# --- 13. CALLBACK HANDLER ---
@bot_app.on_callback_query()
async def cb_handler(client, cb):
    uid = cb.from_user.id
    if cb.data.startswith("dl_"):
        cr.execute("SELECT file_id, movie_name FROM files WHERE id = ?", (cb.data.split("_")[1],))
        res = cr.fetchone()
        if res:
            dna = "Action Lover" if any(x in res[1].lower() for x in ['war','fight','kill']) else "Drama Explorer"
            cr.execute("UPDATE users SET dna_score = ? WHERE user_id = ?", (dna, uid))
            cr.execute("INSERT OR REPLACE INTO last_watch (user_id, movie_name, file_id) VALUES (?, ?, ?)", (uid, res[1], res[0]))
            db.commit()
            await client.send_cached_media(chat_id=uid, file_id=res[0], caption=f"🍿 **Enjoy:** {res[1]}", protect_content=True)
            await cb.answer("Sending...")
    elif cb.data == "view_dna":
        cr.execute("SELECT dna_score FROM users WHERE user_id = ?", (uid,))
        await cb.answer(f"🧬 Your DNA: {cr.fetchone()[0]}", show_alert=True)
    elif cb.data.startswith("setlang_"):
        cr.execute("UPDATE users SET lang = ? WHERE user_id = ?", (cb.data.split("_")[1], uid))
        db.commit()
        await cb.message.edit_text("✅ Language Updated! Send movie name.")
    elif cb.data.startswith("req_"):
        await client.send_message(ADMIN_ID, f"📢 **Request:** {cb.data.split('_')[1]}\n👤 ID: {uid}")
        await cb.answer("✅ Requested!", show_alert=True)
    elif cb.data.startswith("wls_"):
        m_type, m_id = cb.data.split("_")[1], cb.data.split("_")[2]
        _, _, _, title = get_extra_details(m_type, m_id)
        cr.execute("INSERT OR IGNORE INTO watchlist (user_id, movie_id, movie_name) VALUES (?, ?, ?)", (uid, m_id, title))
        db.commit()
        await cb.answer(f"✅ Added to Watchlist: {title}", show_alert=True)
    elif cb.data == "open_settings":
        btns = InlineKeyboardMarkup([[InlineKeyboardButton("🌑 Dark Mode", callback_data="theme_dark"), InlineKeyboardButton("☀️ Light Mode", callback_data="theme_light")]])
        await cb.message.edit_text("🎨 **Settings**:", reply_markup=btns)
# --- 14. LAUNCH ---
if __name__ == "__main__":
    keep_alive()
    bot_app.run()
