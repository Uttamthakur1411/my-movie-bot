from flask import Flask
from threading import Thread
import os
import requests
import sqlite3
import asyncio
import random
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import urllib.parse

# ==================== FLASK HOSTING ====================
flask_app = Flask(__name__)

@flask_app.route('/')
@flask_app.route('/home')
def home():
    return "<h1>🎬 MovieBot is Running Perfectly! ✅</h1>"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    flask_app.run(host="0.0.0.0", port=port, debug=False)

def keep_alive():
    server_thread = Thread(target=run_flask)
    server_thread.daemon = True
    server_thread.start()

# ==================== CONFIGURATION ====================
API_ID = 34976268
API_HASH = "3ccae7cee8251da06d019c49a6aedb9e"
BOT_TOKEN = "8213871486:AAECaJwnXmup3JEwEnV2cAKMGl3NCl9Y6A4"
TMDB_KEY = "9309466d747d6bf6e91a81d01ec98cd0"
FORCE_SUB_CHANNEL = "@Movies_Uttam_Official"
ADMIN_ID = 5615686466

# Bot Client
bot = Client(
    "MovieBot_Ultimate",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# ==================== DATABASE ====================
db_connection = sqlite3.connect("moviebot.db", check_same_thread=False)
db_cursor = db_connection.cursor()

def create_tables():
    db_cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            joined_date TEXT DEFAULT CURRENT_TIMESTAMP,
            points INTEGER DEFAULT 50,
            is_premium INTEGER DEFAULT 0
        )
    """)
    
    db_cursor.execute("""
        CREATE TABLE IF NOT EXISTS movies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            movie_name TEXT,
            tmdb_id TEXT,
            file_id TEXT,
            quality TEXT DEFAULT '720p',
            size TEXT DEFAULT '1.2GB',
            added_date TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    db_cursor.execute("""
        CREATE TABLE IF NOT EXISTS watchlist (
            user_id INTEGER,
            movie_name TEXT,
            tmdb_id TEXT,
            added_date TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, tmdb_id)
        )
    """)
    
    db_cursor.execute("""
        CREATE TABLE IF NOT EXISTS referrals (
            referrer_id INTEGER,
            referred_id INTEGER,
            points_earned INTEGER DEFAULT 25,
            date TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    db_connection.commit()

create_tables()

# ==================== TMDB API FUNCTIONS ====================
def search_movies(query):
    """Search movies on TMDB"""
    try:
        search_url = f"https://api.themoviedb.org/3/search/multi?api_key={TMDB_KEY}&query={urllib.parse.quote(query)}&page=1&include_adult=false"
        response = requests.get(search_url, timeout=10)
        data = response.json()
        return data.get('results', [])[:8]
    except:
        return []

def get_movie_details(tmdb_id):
    """Get detailed movie info"""
    try:
        detail_url = f"https://api.themoviedb.org/3/movie/{tmdb_id}?api_key={TMDB_KEY}&append_to_response=credits,videos"
        response = requests.get(detail_url, timeout=10)
        data = response.json()
        
        genres = ", ".join([genre['name'] for genre in data.get('genres', [])[:4]])
        runtime = f"{data.get('runtime', 0)} mins" if data.get('runtime') else "N/A"
        rating = f"{data.get('vote_average', 0):.1f}/10"
        cast = ", ".join([actor['name'] for actor in data.get('credits', {}).get('cast', [])[:4]])
        poster = f"https://image.tmdb.org/t/p/w500{data.get('poster_path', '')}"
        backdrop = f"https://image.tmdb.org/t/p/original{data.get('backdrop_path', '')}"
        
        return {
            'title': data.get('title', 'Unknown Movie'),
            'overview': data.get('overview', 'No description available.'),
            'genres': genres,
            'runtime': runtime,
            'rating': rating,
            'cast': cast,
            'poster': poster,
            'backdrop': backdrop,
            'release_date': data.get('release_date', 'N/A')
        }
    except:
        return None

# ==================== STREAMING LINKS (100% WORKING) ====================
def generate_streaming_links(tmdb_id, media_type='movie'):
    """Generate multiple working streaming links"""
    links = []
    
    # Primary - VIDSRC (Best for mobile + desktop)
    if media_type == 'movie':
        links.append(f"https://vidsrc.to/embed/movie/{tmdb_id}")
        links.append(f"https://vidsrc.me/embed/movie/{tmdb_id}")
        links.append(f"https://flixhq.to/embed/movie/{tmdb_id}")
    else:
        links.append(f"https://vidsrc.to/embed/tv/{tmdb_id}")
        links.append(f"https://vidsrc.me/embed/tv/{tmdb_id}")
    
    return links[0]  # Return best link

# ==================== USER MANAGEMENT ====================
async def check_subscription(client, user_id):
    """Check if user joined force sub channel"""
    if not FORCE_SUB_CHANNEL:
        return True
    
    try:
        await client.get_chat_member(FORCE_SUB_CHANNEL, user_id)
        return True
    except:
        return False

def register_user(user_id, username=None, first_name=None):
    """Register new user"""
    try:
        db_cursor.execute("""
            INSERT OR IGNORE INTO users (user_id, username, first_name, joined_date)
            VALUES (?, ?, ?, ?)
        """, (user_id, username, first_name, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        db_connection.commit()
        return True
    except:
        return False

# ==================== ADMIN COMMANDS ====================
@bot.on_message(filters.command("stats") & filters.user(ADMIN_ID))
async def stats_command(client, message):
    db_cursor.execute("SELECT COUNT(*) FROM users")
    total_users = db_cursor.fetchone()[0]
    
    db_cursor.execute("SELECT COUNT(*) FROM movies")
    total_movies = db_cursor.fetchone()[0]
    
    db_cursor.execute("SELECT SUM(points) FROM users")
    total_points = db_cursor.fetchone()[0] or 0
    
    stats_text = f"""
📊 **BOT STATISTICS**
━━━━━━━━━━━━━━━━
👥 Total Users: `{total_users}`
🎬 Total Movies: `{total_movies}`
💎 Total Points: `{total_points}`
🔥 Bot Status: **Online**
    """
    
    await message.reply(stats_text)

@bot.on_message(filters.command("broadcast") & filters.user(ADMIN_ID) & filters.reply)
async def broadcast_command(client, message):
    """Broadcast message to all users"""
    db_cursor.execute("SELECT user_id FROM users")
    users = [row[0] for row in db_cursor.fetchall()]
    
    success_count = 0
    fail_count = 0
    
    status_msg = await message.reply("🚀 **Starting broadcast...**")
    
    for user_id in users:
        try:
            await message.reply_to_message.copy(user_id)
            success_count += 1
            await asyncio.sleep(0.05)  # Rate limit
        except:
            fail_count += 1
    
    await status_msg.edit_text(
        f"✅ **Broadcast Complete!**\n"
        f"📤 Sent: `{success_count}`\n"
        f"❌ Failed: `{fail_count}`\n"
        f"👥 Total: `{len(users)}`"
    )

@bot.on_message((filters.document | filters.video) & filters.user(ADMIN_ID))
async def add_movie_file(client, message):
    """Admin can add movie files"""
    if not message.caption:
        file_id = message.document.file_id if message.document else message.video.file_id
        await message.reply(f"**File ID:** `{file_id}`\n\n**Usage:** Send file with caption `Movie Name | 720p`")
        return
    
    caption = message.caption.strip()
    file_id = message.document.file_id if message.document else message.video.file_id
    
    # Parse caption: "Movie Name | Quality"
    parts = caption.split("|")
    movie_name = parts[0].strip()
    quality = parts[1].strip() if len(parts) > 1 else "720p"
    
    db_cursor.execute("""
        INSERT INTO movies (movie_name, file_id, quality)
        VALUES (?, ?, ?)
    """, (movie_name, file_id, quality))
    db_connection.commit()
    
    await message.reply(f"✅ **Movie Added Successfully!**\n🎬 `{movie_name}`\n📱 `{quality}`")

# ==================== USER COMMANDS ====================
@bot.on_message(filters.command("start") & filters.private)
async def start_command(client, message):
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    
    # Referral system
    if len(message.command) > 1:
        try:
            referrer_id = int(message.command[1])
            if referrer_id != user_id:
                db_cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
                if not db_cursor.fetchone():
                    # Give 25 points to referrer
                    db_cursor.execute("UPDATE users SET points = points + 25 WHERE user_id = ?", (referrer_id,))
                    db_cursor.execute("""
                        INSERT INTO referrals (referrer_id, referred_id)
                        VALUES (?, ?)
                    """, (referrer_id, user_id))
                    db_connection.commit()
                    
                    try:
                        await client.send_message(
                            referrer_id,
                            f"🎉 **Referral Bonus!**\n"
                            f"💎 **+25 Points** earned!\n"
                            f"👤 New user: `{first_name}`"
                        )
                    except:
                        pass
        except:
            pass
    
    register_user(user_id, username, first_name)
    
    main_menu = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔍 Search Movies", switch_inline_query_current_chat="")],
        [InlineKeyboardButton("🔥 Trending", callback_data="trending")],
        [InlineKeyboardButton("📱 My Watchlist", callback_data="watchlist")],
        [InlineKeyboardButton("👥 Refer & Earn", callback_data="refer")],
        [InlineKeyboardButton("📊 My Stats", callback_data="stats")]
    ])
    
    welcome_text = f"""
🎬 **Welcome {first_name}!**

🔥 **Ultimate Movie Bot**
✅ Search any movie
✅ Direct streaming links
✅ Mobile + Desktop support
✅ HD Quality streams
✅ Watchlist & Referrals

**Start searching movies now!**
    """
    
    await message.reply_text(welcome_text, reply_markup=main_menu)

@bot.on_message(filters.command("help") & filters.private)
async def help_command(client, message):
    help_text = """
🎬 **MovieBot Help**

**Commands:**
- `/start` - Main menu
- `/help` - This help
- `/watchlist` - Your watchlist

**How to use:**
1️⃣ Search movie name
2️⃣ Click **📺 PLAY ONLINE**
3️⃣ Enjoy HD streaming!

**Admin Commands:**
- `/stats` - Bot statistics
- `/broadcast` - Mass message

**Works on:** Mobile 📱 | PC 💻 | Tablet 📟
    """
    await message.reply_text(help_text)

# ==================== MOVIE SEARCH ====================
@bot.on_message(filters.text & filters.private & ~filters.command(["start", "help"]))
async def movie_search(client, message):
    user_id = message.from_user.id
    
    # Check subscription
    if not await check_subscription(client, user_id):
        join_btn = InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 Join Channel First", url=f"https://t.me/{FORCE_SUB_CHANNEL.lstrip('@')}")]
        ])
        return await message.reply(
            "❌ **Access Denied!**\n\n"
            "📢 **Join our channel first** to use the bot!",
            reply_markup=join_btn
        )
    
    query = message.text.strip()
    search_msg = await message.reply("🔍 **Searching movies...**")
    
    # Search TMDB
    movies = search_movies(query)
    
    if not movies:
        await search_msg.edit("❌ **No movies found!** Try different keywords.")
        return
    
    # Get details of first movie
    first_movie = movies[0]
    movie_info = get_movie_details(first_movie['id'])
    
    if not movie_info:
        await search_msg.edit("❌ **Error loading movie details!**")
        return
    
    # Generate perfect streaming link
    stream_link = generate_streaming_links(first_movie['id'])
    
    # Create beautiful movie card
    movie_card = f"""
🎬 **{movie_info['title']}**
━━━━━━━━━━━━━━━━━━━━━━━━

⭐ **IMDB:** {movie_info['rating']}
🎭 **Genre:** {movie_info['genres']}
⏱ **Duration:** {movie_info['runtime']}
👥 **Cast:** {movie_info['cast']}
📅 **Release:** {movie_info['release_date']}

📖 **{movie_info['overview'][:200]}...**
━━━━━━━━━━━━━━━━━━━━━━━━

📱 **Perfect Mobile + Desktop Player**
    """
    
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("📺 PLAY ONLINE", url=stream_link)],
        [InlineKeyboardButton("🎥 YouTube Trailer", url=f"https://www.youtube.com/results?search_query={urllib.parse.quote(movie_info['title'])}+trailer")],
        [InlineKeyboardButton("🌐 IMDB Page", url=f"https://www.imdb.com/find?q={urllib.parse.quote(movie_info['title'])}")],
        [InlineKeyboardButton("➕ Add to Watchlist", callback_data=f"watchlist_add_{first_movie['id']}")],
        [InlineKeyboardButton("🔍 View All Results", switch_inline_query_current_chat=query)],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
    ])
    
    try:
        await search_msg.delete()
        await message.reply_photo(
            photo=movie_info['poster'],
            caption=movie_card,
            reply_markup=buttons
        )
    except:
        await search_msg.edit(movie_card, reply_markup=buttons)

# ==================== CALLBACK HANDLERS ====================
@bot.on_callback_query()
async def callback_handler(client, callback):
    data = callback.data
    user_id = callback.from_user.id
    
    if data == "trending":
        # Trending movies
        trending_movies = requests.get(
            f"https://api.themoviedb.org/3/trending/movie/day?api_key={TMDB_KEY}"
        ).json().get('results', [])[:10]
        
        trending_text = "🔥 **TRENDING MOVIES TODAY**\n\n"
        buttons = []
        
        for movie in trending_movies:
            title = movie['title'][:30]
            trending_text += f"🎬 **{title}**\n⭐ {movie['vote_average']:.1f}\n\n"
            buttons.append([InlineKeyboardButton(title, switch_inline_query_current_chat=movie['title'])])
        
        buttons.append([InlineKeyboardButton("🏠 Back to Home", callback_data="main_menu")])
        
        await callback.message.edit_text(trending_text, reply_markup=InlineKeyboardMarkup(buttons))
    
    elif data == "main_menu":
        await start_command(client, callback.message)
    
    elif data.startswith("watchlist_add_"):
        tmdb_id = data.split("_")[2]
        movie_title = get_movie_details(tmdb_id)['title'] if get_movie_details(tmdb_id) else "Movie"
        
        db_cursor.execute("""
            INSERT OR IGNORE INTO watchlist (user_id, movie_name, tmdb_id)
            VALUES (?, ?, ?)
        """, (user_id, movie_title, tmdb_id))
        db_connection.commit()
        
        await callback.answer(f"✅ **{movie_title}** added to watchlist!", show_alert=True)
    
    elif data == "refer":
        bot_username = (await client.get_me()).username
        referral_link = f"https://t.me/{bot_username}?start={user_id}"
        
        db_cursor.execute("SELECT points FROM users WHERE user_id = ?", (user_id,))
        points = db_cursor.fetchone()[0] if db_cursor.fetchone() else 50
        
        refer_text = f"""
🚀 **Referral Program**

💎 **Your Points:** `{points}`
🎁 **25 Points per referral**

📎 **Your Link:**
`{referral_link}`

👥 **Share with friends!**
        """
        
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("📤 Share Link", url=f"https://t.me/share/url?url={urllib.parse.quote(referral_link)}&text=Best Movie Bot!")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
        ])
        
        await callback.message.edit_text(refer_text, reply_markup=buttons)
    
    elif data == "stats":
        db_cursor.execute("""
            SELECT points FROM users WHERE user_id = ?
        """, (user_id,))
        result = db_cursor.fetchone()
        points = result[0] if result else 50
        
        db_cursor.execute("""
            SELECT COUNT(*) FROM watchlist WHERE user_id = ?
        """, (user_id,))
        watchlist_count = db_cursor.fetchone()[0]
        
        stats_text = f"""
📊 **Your Stats**

💎 **Points:** `{points}`
📱 **Watchlist:** `{watchlist_count}` movies
🆔 **User ID:** `{user_id}`
        """
        
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
        ])
        
        await callback.message.edit_text(stats_text, reply_markup=buttons)

# ==================== INLINE QUERY ====================
@bot.on_inline_query()
async def inline_query_handler(client, inline_query):
    query_text = inline_query.query.strip() if inline_query.query else ""
    
    if len(query_text) < 2:
        await inline_query.answer([])
        return
    
    movies = search_movies(query_text)
    inline_results = []
    
    for movie in movies[:10]:
        stream_url = generate_streaming_links(movie['id'])
        title = movie.get('title', 'Unknown Movie')
        
        inline_results.append(
            InlineKeyboardButton(
                f"🎬 {title[:50]}",
                url=stream_url
            )
        )
    
    await inline_query.answer(inline_results)

# ==================== START BOT ====================
if __name__ == "__main__":
    print("🚀 Starting Ultimate MovieBot...")
    print("📡 Flask server starting...")
    keep_alive()
    print("🤖 Bot connecting...")
    bot.run()
