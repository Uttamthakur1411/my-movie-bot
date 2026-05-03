from flask import Flask
from threading import Thread
import os
import requests
import sqlite3
import asyncio
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# --- 1. RENDER PORT BINDING (KEEP ALIVE) ---
flask_app = Flask('')

@flask_app.route('/')
def home():
    return "Bot is alive and kicking!"

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

bot_app = Client("Movie_Pro_Final_V2", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- 3. DATABASE SETUP (SQLite) ---
db = sqlite3.connect("bot_data.db", check_same_thread=False)
cr = db.cursor()

def init_db():
    cr.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER UNIQUE, joined_date TEXT)")
    cr.execute("CREATE TABLE IF NOT EXISTS files (id INTEGER PRIMARY KEY AUTOINCREMENT, movie_name TEXT, file_id TEXT)")
    cr.execute("CREATE TABLE IF NOT EXISTS watchlist (user_id INTEGER, movie_id TEXT, movie_name TEXT)")
    db.commit()

init_db()

# --- 4. TMDB & DETAILS ENGINE ---
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

# --- 5. AUTH CHECK ---
async def is_subscribed(client, message):
    if not FORCE_SUB_CHANNEL: return True
    try:
        await client.get_chat_member(FORCE_SUB_CHANNEL, message.from_user.id)
        return True
    except:
        btn = InlineKeyboardMarkup([[InlineKeyboardButton("Join Channel 📢", url=f"https://t.me/{FORCE_SUB_CHANNEL}")]])
        await message.reply_text("❌ **Bot use karne ke liye channel join karein!**", reply_markup=btn)
        return False

# --- 6. ADMIN COMMANDS (DATA ENTRY) ---
@bot_app.on_message(filters.command("add") & filters.user(ADMIN_ID))
async def add_movie_handler(client, message):
    try:
        # Format: /add Movie Name | file_id
        input_str = message.text.split(" ", 1)[1]
        m_name, f_id = input_str.split("|")
        m_name = m_name.strip().lower()
        f_id = f_id.strip()
        
        cr.execute("INSERT INTO files (movie_name, file_id) VALUES (?, ?)", (m_name, f_id))
        db.commit()
        await message.reply_text(f"✅ **Database Updated!**\n🎬 **Movie:** `{m_name}`\n🆔 **ID:** `{f_id}`")
    except:
        await message.reply_text("❌ **Usage:** `/add Movie Name | file_id`")

# --- 7. USER SEARCH & COMMANDS ---
@bot_app.on_message(filters.command("start"))
async def start_cmd(client, message):
    if not await is_subscribed(client, message): return
    uid = message.from_user.id
    now = datetime.now().strftime("%d-%m-%Y")
    cr.execute("INSERT OR IGNORE INTO users (user_id, joined_date) VALUES (?, ?)", (uid, now))
    db.commit()
    await message.reply_text(f"👋 **Namaste {message.from_user.first_name}!**\n\nMovie ka naam bhejiye, main download link aur details nikaal dunga.")

@bot_app.on_message(filters.text & ~filters.command(["start", "add", "watchlist"]))
async def movie_search(client, message):
    if not await is_subscribed(client, message): return
    query = message.text.lower().strip()
    status = await message.reply_text("🔎 Searching in Database...")
    
    # Check Database for Download Link
    cr.execute("SELECT file_id, id FROM files WHERE movie_name LIKE ?", (f"%{query}%",))
    local_data = cr.fetchone()
    
    results = get_tmdb_results(query)
    if not results:
        btn = InlineKeyboardMarkup([[InlineKeyboardButton("🎟 Request File", callback_data=f"req_{query[:15]}")]])
        return await status.edit(f"❌ '{query}' nahi mila.", reply_markup=btn)

    item = results[0]
    m_id, m_type = item['id'], item.get('media_type', 'movie')
    title = item.get('title') or item.get('name')
    genres, runtime, cast = get_extra_details(m_type, m_id)
    poster_path = item.get('poster_path')
    poster = f"https://image.tmdb.org/t/p/w500{poster_path}" if poster_path else "https://telegra.ph/file/default.jpg"

    caption = (f"🎬 **{title}**\n\n🎭 **Genre:** {genres}\n⏳ **Runtime:** {runtime}\n"
               f"⭐ **Rating:** {item.get('vote_average', 'N/A')}/10\n👥 **Cast:** {cast}\n\n"
               f"✨ **Powered By Thakur Uttam**")

    # Buttons Logic
    btns = [
        [InlineKeyboardButton("📺 Stream Online", url=f"https://vidsrc.me/embed/{m_type}/{m_id}"),
         InlineKeyboardButton("🎬 Trailer", url=f"https://www.youtube.com/results?search_query={title.replace(' ', '+')}+trailer")]
    ]
    
    # AGAR FILE DATABASE MEIN HAI TO DOWNLOAD BUTTON DIKHAO
    if local_data:
        btns.insert(0, [InlineKeyboardButton("📥 Download Movie (Direct)", callback_data=f"dl_{local_data[1]}")])
    
    btns.append([InlineKeyboardButton("➕ Add Watchlist", callback_data=f"wls_{m_type}_{m_id}")])

    try:
        await message.reply_photo(photo=poster, caption=caption, reply_markup=InlineKeyboardMarkup(btns))
        await status.delete()
    except:
        await status.edit(caption, reply_markup=InlineKeyboardMarkup(btns))

# --- 8. CALLBACKS ---
@bot_app.on_callback_query()
async def cb_handler(client, cb):
    uid = cb.from_user.id
    if cb.data.startswith("dl_"):
        cr.execute("SELECT file_id FROM files WHERE id = ?", (cb.data.split("_")[1],))
        res = cr.fetchone()
        if res:
            await client.send_cached_media(chat_id=uid, file_id=res[0], caption="✅ **Aapki Movie! Enjoy!**")
            await cb.answer("Sending File...")
    
    elif cb.data.startswith("wls_"):
        _, m_type, m_id = cb.data.split("_")
        url = f"https://api.themoviedb.org/3/{m_type}/{m_id}?api_key={TMDB_KEY}"
        res = requests.get(url).json()
        name = res.get('title') or res.get('name')
        cr.execute("INSERT INTO watchlist (user_id, movie_id, movie_name) VALUES (?, ?, ?)", (uid, m_id, name))
        db.commit()
        await cb.answer(f"✅ '{name}' added to watchlist!", show_alert=True)

    elif cb.data.startswith("req_"):
        await client.send_message(ADMIN_ID, f"🚨 **New File Request:** `{cb.data.split('_')[1]}`")
        await cb.answer("Request sent to Admin!")

# --- 9. LAUNCH ---
if __name__ == "__main__":
    keep_alive()
    print("Bot is Live on Render!")
    bot_app.run()
