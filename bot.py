from flask import Flask
from threading import Thread
import os
import requests
import sqlite3
import asyncio
import random
import re
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InlineQueryResultArticle, InputTextMessageContent

# --- 1. RENDER PORT BINDING (24/7 Hosting) ---
flask_app = Flask('')

@flask_app.route('/')
def home():
    return "Bot is alive! Sherlock-Defense Level: MAX. All Systems Nominal."

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    flask_app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_flask)
    t.start()

# --- 2. CONFIGURATION ---
API_ID = 34976268
API_HASH = "3ccae7cee8251da06d019c49a6aedb9e"
BOT_TOKEN = "8213871486:AAGxo8PnNzV28CvnCnz_lCRCOWN_9HxRXgg"
TMDB_KEY = "9309466d747d6bf6e91a81d01ec98cd0"
FORCE_SUB_CHANNEL = "Movies_Uttam_Official" 
ADMIN_ID = 5615686466 

bot_app = Client("Movie_Pro_Netflix_Final", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- 3. DATABASE SETUP ---
db = sqlite3.connect("bot_data.db", check_same_thread=False)
cr = db.cursor()

def init_db():
    cr.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER UNIQUE, joined_date TEXT, lang TEXT DEFAULT 'en', referred_by INTEGER, points INTEGER DEFAULT 0, theme TEXT DEFAULT 'dark')")
    cr.execute("CREATE TABLE IF NOT EXISTS files (id INTEGER PRIMARY KEY AUTOINCREMENT, movie_name TEXT, file_id TEXT, tags TEXT)")
    cr.execute("CREATE TABLE IF NOT EXISTS watchlist (user_id INTEGER, movie_id TEXT, movie_name TEXT)")
    cr.execute("CREATE TABLE IF NOT EXISTS last_watch (user_id INTEGER UNIQUE, movie_name TEXT, file_id TEXT)")
    db.commit()

init_db()

# --- 4. SHERLOCK DEFENSE SYSTEM ---
def is_sherlock_spam(message):
    if not message.text and not message.caption:
        return False
    text = (message.text or message.caption).lower()
    # Russian Cyrillic Script Check
    if re.search(r'[\u0400-\u04FF]', text):
        return True
    # Blacklisted Keywords & Commands
    bad_words = ["sherlock", "поисковая", "система", "snils", "inn", "passport", "навальный", "vu", "ввод", "команд"]
    if any(word in text for word in bad_words):
        return True
    return False

# --- 5. TMDB & ENGINE UTILS ---
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

# --- 6. AUTH & SUBSCRIPTION ---
async def is_subscribed(client, message):
    if not FORCE_SUB_CHANNEL: return True
    try:
        await client.get_chat_member(FORCE_SUB_CHANNEL, message.from_user.id)
        return True
    except:
        btn = InlineKeyboardMarkup([[InlineKeyboardButton("Join Channel 📢", url=f"https://t.me/{FORCE_SUB_CHANNEL}")]])
        await message.reply_text("❌ **Bot use karne ke liye channel join karein!**", reply_markup=btn)
        return False

# --- 7. DEFENSE & START HANDLERS ---
@bot_app.on_message(filters.private, group=-1)
async def defense_layer(client, message):
    if is_sherlock_spam(message):
        try: await message.delete()
        except: pass
        return message.stop_propagation()

@bot_app.on_message(filters.command("start") & filters.private)
async def start_cmd(client, message):
    uid = message.from_user.id
    now = datetime.now().strftime("%d-%m-%Y")
    
    # Referral Logic
    if len(message.command) > 1 and message.command[1].isdigit():
        ref_id = int(message.command[1])
        if ref_id != uid:
            cr.execute("SELECT user_id FROM users WHERE user_id = ?", (uid,))
            if not cr.fetchone(): 
                cr.execute("UPDATE users SET points = points + 10 WHERE user_id = ?", (ref_id,))
                try: await client.send_message(ref_id, "🎁 **Referral Reward!** You got 10 points.")
                except: pass

    cr.execute("INSERT OR IGNORE INTO users (user_id, joined_date) VALUES (?, ?)", (uid, now))
    db.commit()

    btns = InlineKeyboardMarkup([
        [InlineKeyboardButton("English 🇺🇸", callback_data="setlang_en"), InlineKeyboardButton("Hindi 🇮🇳", callback_data="setlang_hi")],
        [InlineKeyboardButton("🎨 Settings & Theme", callback_data="open_settings")]
    ])
    await message.reply_text(f"👋 **Namaste {message.from_user.first_name}!**\n\nWelcome to Movie Pro Netflix. Please select your language / Kripya bhasha chunein:", reply_markup=btns)

# --- 8. MOVIE SEARCH LOGIC ---
@bot_app.on_message(filters.text & filters.private & ~filters.me)
async def movie_search(client, message):
    if message.text.startswith("/") or "🔎" in message.text: return
    if not await is_subscribed(client, message): return
    
    query = message.text.lower().strip()
    if len(query) < 2: return
        
    status = await message.reply_text("🔎 **Searching Database...**")
    
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
    poster = f"https://image.tmdb.org/t/p/w500{item.get('poster_path')}" if item.get('poster_path') else "https://telegra.ph/file/default.jpg"

    caption = (f"🎬 **{title}**\n\n🎭 **Genre:** {genres}\n⏳ **Runtime:** {runtime}\n"
               f"⭐ **Rating:** {item.get('vote_average', 'N/A')}/10\n👥 **Cast:** {cast}\n\n"
               f"✨ **Powered By Thakur Uttam**")

    btns = [
        [InlineKeyboardButton("📺 Stream Online", url=f"https://vidsrc.me/embed/{m_type}/{m_id}"),
         InlineKeyboardButton("🎬 Trailer", url=f"https://www.youtube.com/results?search_query={title.replace(' ', '+')}+trailer")],
        [InlineKeyboardButton("🍿 Watch Party", url=f"https://vidsrc.me/embed/{m_type}/{m_id}"),
         InlineKeyboardButton("➕ Watchlist", callback_data=f"wls_{m_type}_{m_id}")]
    ]
    if local_data:
        btns.insert(0, [InlineKeyboardButton("📥 Download Movie", callback_data=f"dl_{local_data[1]}")] )

    try:
        await message.reply_photo(photo=poster, caption=caption, reply_markup=InlineKeyboardMarkup(btns))
        await status.delete()
    except:
        await status.edit(caption, reply_markup=InlineKeyboardMarkup(btns))

# --- 9. EXTRA FEATURES (Trending, Shayari, Refer) ---
@bot_app.on_message(filters.command("trending"))
async def trending_cmd(client, message):
    res = requests.get(f"https://api.themoviedb.org/3/trending/all/day?api_key={TMDB_KEY}").json().get('results', [])[:10]
    text = "🔥 **Trending Today:**\n\n" + "\n".join([f"{i+1}. {m.get('title') or m.get('name')}" for i, m in enumerate(res)])
    await message.reply_text(text)

@bot_app.on_message(filters.command("refer"))
async def refer_cmd(client, message):
    me = await client.get_me()
    await message.reply_text(f"🚀 **Your Referral Link:**\nhttps://t.me/{me.username}?start={message.from_user.id}")

@bot_app.on_message(filters.command("shayari"))
async def shayari_cmd(client, message):
    list_s = ["Zindagi ek safar hai suhana...", "Dil se roye magar honto se muskura beithe...", "Aapki dosti ne humein jeena sikha diya..."]
    await message.reply_text(f"✍️ **Shayari:**\n\n{random.choice(list_s)}")

# --- 10. ADMIN CONTROLS ---
@bot_app.on_message(filters.command("add") & filters.user(ADMIN_ID))
async def add_movie_manual(client, message):
    try:
        _, data = message.text.split(" ", 1)
        name, fid = data.split("|")
        cr.execute("INSERT INTO files (movie_name, file_id) VALUES (?, ?)", (name.strip().lower(), fid.strip()))
        db.commit()
        await message.reply_text("✅ Added!")
    except: await message.reply_text("`/add Name | file_id`")

@bot_app.on_message((filters.document | filters.video) & filters.user(ADMIN_ID))
async def auto_add_file(client, message):
    if message.caption:
        name = message.caption.strip().lower()
        fid = message.document.file_id if message.document else message.video.file_id
        cr.execute("INSERT INTO files (movie_name, file_id) VALUES (?, ?)", (name, fid))
        db.commit()
        await message.reply_text(f"✅ Added: {name}")
    else:
        fid = message.document.file_id if message.document else message.video.file_id
        await message.reply_text(f"🆔 File ID: `{fid}`")

# --- 11. CALLBACK & WATCHLIST ---
@bot_app.on_callback_query()
async def cb_handler(client, cb):
    uid = cb.from_user.id
    if cb.data.startswith("dl_"):
        cr.execute("SELECT file_id, movie_name FROM files WHERE id = ?", (cb.data.split("_")[1],))
        res = cr.fetchone()
        if res:
            cr.execute("INSERT OR REPLACE INTO last_watch (user_id, movie_name, file_id) VALUES (?, ?, ?)", (uid, res[1], res[0]))
            db.commit()
            await client.send_cached_media(chat_id=uid, file_id=res[0], caption=f"✅ {res[1]}", protect_content=True)
            await cb.answer("Sending...")
    
    elif cb.data.startswith("setlang_"):
        cr.execute("UPDATE users SET lang = ? WHERE user_id = ?", (cb.data.split("_")[1], uid))
        db.commit()
        await cb.message.edit_text("✅ Language Updated! Send movie name.")

    elif cb.data == "open_settings":
        btns = InlineKeyboardMarkup([[InlineKeyboardButton("🌑 Dark Mode", callback_data="theme_dark"), InlineKeyboardButton("☀️ Light Mode", callback_data="theme_light")]])
        await cb.message.edit_text("🎨 **Bot Theme Customization**", reply_markup=btns)

    elif cb.data.startswith("wls_"):
        _, m_type, m_id = cb.data.split("_")
        res = requests.get(f"https://api.themoviedb.org/3/{m_type}/{m_id}?api_key={TMDB_KEY}").json()
        name = res.get('title') or res.get('name')
        cr.execute("INSERT INTO watchlist (user_id, movie_id, movie_name) VALUES (?, ?, ?)", (uid, m_id, name))
        db.commit()
        await cb.answer(f"✅ Added: {name}", show_alert=True)

# --- 12. RUN BOT ---
if __name__ == "__main__":
    keep_alive()
    bot_app.run()
