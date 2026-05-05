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
    return "✅ Movie Bot is ALIVE and RUNNING!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    flask_app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_flask)
    t.daemon = True
    t.start()

# --- 2. YOUR CREDENTIALS (CHANGE THESE) ---
API_ID = "YOUR_NEW_API_ID"  # my.telegram.org se naya lo
API_HASH = "YOUR_NEW_API_HASH"
BOT_TOKEN = "YOUR_NEW_BOT_TOKEN"  # BotFather se naya lo
TMDB_KEY = "9309466d747d6bf6e91a81d01ec98cd0"
FORCE_SUB_CHANNEL = "Movies_Uttam_Official" 
ADMIN_ID = 5615686466 

bot_app = Client("MovieBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- 3. DATABASE ---
db = sqlite3.connect("bot_data.db", check_same_thread=False)
cr = db.cursor()

def init_db():
    cr.execute("""CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY, joined_date TEXT, lang TEXT DEFAULT 'en', 
        points INTEGER DEFAULT 50
    )""")
    cr.execute("CREATE TABLE IF NOT EXISTS files (id INTEGER PRIMARY KEY AUTOINCREMENT, movie_name TEXT, file_id TEXT)")
    cr.execute("CREATE TABLE IF NOT EXISTS watchlist (user_id INTEGER, movie_name TEXT)")
    cr.execute("CREATE TABLE IF NOT EXISTS last_watch (user_id INTEGER PRIMARY KEY, movie_name TEXT, file_id TEXT)")
    db.commit()

init_db()

# --- 4. TMDB API ---
def get_tmdb_results(query):
    url = f"https://api.themoviedb.org/3/search/multi?api_key={TMDB_KEY}&query={query}&include_adult=false"
    try:
        res = requests.get(url, timeout=8).json()
        return [r for r in res.get('results', []) if r.get('media_type') in ['movie', 'tv']]
    except:
        return []

# --- 5. FORCE SUB CHECK ---
async def check_sub(client, user_id):
    if not FORCE_SUB_CHANNEL:
        return True
    try:
        await client.get_chat_member(FORCE_SUB_CHANNEL, user_id)
        return True
    except UserNotParticipant:
        return False
    except:
        return True

# --- 6. START COMMAND (FIXED) ---
@bot_app.on_message(filters.command("start") & filters.private)
async def start_cmd(client, message):
    try:
        uid = message.from_user.id
        user_name = message.from_user.first_name or "User"
        
        # Referral check
        if len(message.command) > 1:
            try:
                ref_id = int(message.command[1])
                cr.execute("SELECT user_id FROM users WHERE user_id=?", (uid,))
                if not cr.fetchone() and ref_id != uid:
                    cr.execute("UPDATE users SET points = points + 20 WHERE user_id=?", (ref_id,))
                    cr.execute("INSERT OR IGNORE INTO users (user_id, joined_date, points) VALUES (?, ?, 50)", (ref_id, datetime.now().strftime("%d-%m-%Y")))
                    db.commit()
            except:
                pass
        
        # Add user to DB
        cr.execute("INSERT OR IGNORE INTO users (user_id, joined_date) VALUES (?, ?)", 
                  (uid, datetime.now().strftime("%d-%m-%Y")))
        db.commit()
        
        # Check subscription
        if not await check_sub(client, uid):
            btn = InlineKeyboardMarkup([[InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{FORCE_SUB_CHANNEL}")]])
            return await message.reply_text(
                "❌ **Access Denied!**\n\n"
                "Bot use karne ke liye pehle hamara channel join karein:",
                reply_markup=btn
            )
        
        # Welcome message
        welcome_text = (
            f"🔥 **Welcome {user_name}!**\n\n"
            f"✅ **Movie Bot Ready!**\n\n"
            f"🎬 Search any movie name\n"
            f"📱 /watchlist - Your list\n"
            f"⏯️ /continue - Last movie\n"
            f"🚀 /refer - Earn points"
        )
        
        btns = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔥 Search Movies", callback_data="search_menu")],
            [InlineKeyboardButton("📱 Watchlist", callback_data="show_wl"), 
             InlineKeyboardButton("⭐ Trending", callback_data="trending")]
        ])
        
        await message.reply_text(welcome_text, reply_markup=btns)
        
    except Exception as e:
        print(f"Start error: {e}")
        await message.reply_text("🚀 Bot started successfully!")

# --- 7. SIMPLE SEARCH ---
@bot_app.on_message(filters.text & filters.private & ~filters.command(["start", "help"]))
async def search_movies(client, message):
    try:
        if not await check_sub(client, message.from_user.id):
            return
        
        query = message.text.strip()
        if len(query) < 2:
            return
            
        await message.reply_chat_action("typing")
        
        results = get_tmdb_results(query)
        if not results:
            await message.reply_text(f"❌ **'{query}'** not found!\nTry different spelling.")
            return
        
        movie = results[0]
        title = movie.get('title') or movie.get('name')
        poster = f"https://image.tmdb.org/t/p/w500{movie.get('poster_path')}" if movie.get('poster_path') else None
        
        caption = f"🎬 **{title}**\n⭐ Rating: {movie.get('vote_average', 0):.1f}/10"
        
        btns = InlineKeyboardMarkup([
            [InlineKeyboardButton("📺 Watch Online", url=f"https://vidsrc.me/embed/movie/{movie.get('id')}")],
            [InlineKeyboardButton("➕ Add to Watchlist", callback_data=f"add_wl_{movie.get('id')}")]
        ])
        
        if poster:
            await message.reply_photo(photo=poster, caption=caption, reply_markup=btns)
        else:
            await message.reply_text(caption, reply_markup=btns)
            
    except Exception as e:
        print(f"Search error: {e}")
        await message.reply_text("❌ Search error! Try again.")

# --- 8. BASIC CALLBACKS ---
@bot_app.on_callback_query()
async def cb_handler(client, callback_query):
    try:
        data = callback_query.data
        uid = callback_query.from_user.id
        
        if data == "search_menu":
            await callback_query.message.edit_text(
                "🔍 **Search any movie name!**\n\nExample: `Avengers`, `RRR`, `Pushpa`",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]])
            )
            
        elif data == "show_wl":
            cr.execute("SELECT movie_name FROM watchlist WHERE user_id=?", (uid,))
            movies = cr.fetchall()
            if movies:
                text = "📋 **Your Watchlist:**\n\n" + "\n".join([f"• {m[0]}" for m in movies[:10]])
            else:
                text = "📋 **Watchlist is empty!**"
            await callback_query.message.edit_text(text)
            
        elif data.startswith("add_wl_"):
            movie_id = data.split("_")[2]
            cr.execute("INSERT INTO watchlist (user_id, movie_name) VALUES (?, ?)", 
                      (uid, f"Movie {movie_id}"))
            db.commit()
            await callback_query.answer("✅ Added to Watchlist!")
            
    except:
        pass

# --- 9. START BOT ---
if __name__ == "__main__":
    print("🚀 Starting Movie Bot...")
    keep_alive()
    print("✅ Flask server started")
    bot_app.run()
    print("✅ Bot started successfully!")
