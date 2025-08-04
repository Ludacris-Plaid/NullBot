import os
import json
import requests
import asyncio
import nest_asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
from telegram.error import NetworkError
from flask import Flask, request, redirect
from threading import Thread
from PIL import Image
from weasyprint import HTML
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
import base64
import random
import logging
import time

# Apply nest_asyncio for local testing
nest_asyncio.apply()

BOT_TOKEN = "8132539541:AAFTibgRmTRfUZJhDFkbHzzXD8yG1KHs8Dg"  # Replace with BotFather token
BLOCKONOMICS_API_KEY = "A1Jo0fa6eNXZ7Ajc07IBYiqHALMqTFvF7AaAJNS56k0"  # Replace with Blockonomics API key
CALLBACK_SECRET = "nullbotsecret666"  # Replace with your callback secret
XMR_ADDRESS = "8B5A9XUE4oEMNTiMXbVwuEU321YS8y2p1g4v3UumgVXXBib6LMxDTVu4A8DsxLiW5x5oXSc8smXzKcD4QUMxLo3A138zxQz"  # Replace with your Monero address
ADMIN_ID = 7260656020  # Replace with your Telegram user ID (get via @userinfobot)
INVENTORY_FILE = "inventory.json"
SALES_FILE = "sales.json"
BLACK_MARKET_USERS_FILE = "black_market_users.json"
DISCOUNTS_FILE = "discounts.json"
PENDING_ORDERS_FILE = "pending_orders.json"
WEBHOOK_URL = "https://your-bot-host/webhook"  # Replace with your Render URL

# Initialize Flask
app = Flask(__name__)

# Initialize files
for file in [INVENTORY_FILE, SALES_FILE, BLACK_MARKET_USERS_FILE, PENDING_ORDERS_FILE]:
    if not os.path.exists(file):
        with open(file, "w") as f:
            json.dump([], f)
if not os.path.exists(DISCOUNTS_FILE):
    with open(DISCOUNTS_FILE, "w") as f:
        json.dump({}, f)

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Utility functions
def load_inventory():
    with open(INVENTORY_FILE, "r") as f:
        return json.load(f)

def save_inventory(inventory):
    with open(INVENTORY_FILE, "w") as f:
        json.dump(inventory, f, indent=4)

def load_sales():
    with open(SALES_FILE, "r") as f:
        return json.load(f)

def save_sales(sales):
    with open(SALES_FILE, "w") as f:
        json.dump(sales, f, indent=4)

def load_black_market_users():
    with open(BLACK_MARKET_USERS_FILE, "r") as f:
        return json.load(f)

def save_black_market_users(users):
    with open(BLACK_MARKET_USERS_FILE, "w") as f:
        json.dump(users, f, indent=4)

def load_pending_orders():
    with open(PENDING_ORDERS_FILE, "r") as f:
        return json.load(f)

def save_pending_orders(orders):
    with open(PENDING_ORDERS_FILE, "w") as f:
        json.dump(orders, f, indent=4)

def generate_screenshot(file_path, output_path):
    try:
        if file_path.endswith(".pdf"):
            html = f'<iframe src="{file_path}" width="100%" height="100%"></iframe>'
            HTML(string=html).write_png(output_path)
        elif file_path.endswith(".txt"):
            with open(file_path, "r") as f:
                text = f.read()[:200]
            html = f'<pre>{text}</pre>'
            HTML(string=html).write_png(output_path)
        img = Image.open(output_path)
        img.thumbnail((200, 200))
        img.save(output_path)
    except Exception as e:
        logger.error(f"Failed to generate screenshot: {e}")

def encrypt_file(file_path, key):
    try:
        cipher = AES.new(key, AES.MODE_EAX)
        with open(file_path, "rb") as f:
            data = f.read()
        ciphertext, tag = cipher.encrypt_and_digest(data)
        encrypted_path = file_path + ".enc"
        with open(encrypted_path, "wb") as f:
            [f.write(x) for x in (cipher.nonce, tag, ciphertext)]
        return encrypted_path, key
    except Exception as e:
        logger.error(f"Failed to encrypt file: {e}")
        return None, None

def get_btc_price():
    try:
        response = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd", timeout=5)
        response.raise_for_status()
        return response.json()["bitcoin"]["usd"]
    except requests.RequestException as e:
        logger.error(f"Failed to fetch BTC price: {e}")
        return 50000  # Fallback price

def get_xmr_price():
    try:
        response = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=monero&vs_currencies=usd", timeout=5)
        response.raise_for_status()
        return response.json()["monero"]["usd"]
    except requests.RequestException as e:
        logger.error(f"Failed to fetch XMR price: {e}")
        return 150  # Fallback price

# Telegram commands
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_message = """
████████╗████████╗██╗    ██╗
╚══██╔══╝╚══██╔══╝██║    ██║
   ██║      ██║   ██║ █╗ ██║
   ██║      ██║   ██║███╗██║
   ██║      ██║   ╚███╔███╔╝
   ╚═╝      ╚═╝    ╚══╝╚══╝ 
Welcome to Tax The World NullBot ☠️—where the dark web thrives.
Browse stolen CCs, PII, and hacking guides with /list.
Test your skills with /hack, unlock the Black Market with /join_black_market.
Admin? Use /admin to rule the abyss.
Stay sharp. Trust no one. Tax the world.
"""
    await update.message.reply_text(welcome_message)

async def list_items(update: Update, context: ContextTypes.DEFAULT_TYPE):
    inventory = load_inventory()
    user_id = update.message.from_user.id
    black_market_users = load_black_market_users()
    is_black_market = str(user_id) in black_market_users
    items = [i for i in inventory if i["tier"] == "standard" or (i["tier"] == "black_market" and is_black_market)]
    if not items:
        await update.message.reply_text("No items available. Join the Black Market with /join_black_market for the good stuff.")
        return
    for item in items:
        keyboard = [[InlineKeyboardButton("Buy Now", callback_data=f"buy_{item['id']}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        caption = (
            f"{item['title']} [{item['tier'].upper()}]\n"
            f"Description: {item['description']}\n"
            f"Price: {item['price_btc']} BTC / {item['price_btc'] / get_btc_price() * get_xmr_price():.4f} XMR (${item['price_usd']})\n"
            "Only 5 copies left! Grab it before the feds do."
        )
        try:
            await update.message.reply_photo(
                photo=open(item['thumbnail'], "rb"),
                caption=caption,
                reply_markup=reply_markup
            )
        except Exception as e:
            logger.error(f"Failed to send photo: {e}")
            await update.message.reply_text(caption, reply_markup=reply_markup)

async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        await update.message.reply_text("Access denied. You’re not the king of this abyss.")
        return
    await update.message.reply_text(
        "Tax The World NullBot ☠️ Admin Panel: Open https://your-bot-host/admin in a secure browser.",
        disable_web_page_preview=True
    )

async def join_black_market(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"Unlock the Black Market for 0.01 XMR. Send to: {XMR_ADDRESS}\n"
        "Reply with your transaction ID to enter the shadows."
    )
    context.user_data["pending_black_market"] = True

async def hack(update: Update, context: ContextTypes.DEFAULT_TYPE):
    challenge = base64.b64encode(b"CrackMeToWin").decode("utf-8")
    await update.message.reply_text(
        f"Prove you’re not a script kiddie. Crack this Base64: {challenge}\n"
        "Reply with the answer for a 10% discount."
    )
    context.user_data["hack_challenge"] = "CrackMeToWin"

async def refer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    referral_link = f"https://t.me/TaxTheWorldNullBot?start=ref_{user_id}"
    await update.message.reply_text(
        f"Spread the chaos: {referral_link}\nEarn 0.001 BTC per referred buyer (min 0.01 BTC spend)."
    )

async def reviews(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "What the shadows say:\n"
        "- 'Scored 5k valid CCs. NullBot is fire 🔥' - Anon\n"
        "- 'Best PII dump ever. Taxed the world!' - ShadowHacker\n"
        "Join the chaos at /list."
    )

async def ddos_teaser(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "DDoS-for-hire coming soon. Want to crash a site? Stay tuned and join /list for updates."
    )

async def burn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"Burn a dataset for 0.01 BTC to create scarcity. Send to [BTC_ADDRESS] and reply with TX ID."
    )

async def demo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "NullBot just cracked a DB: 10k PII leaked! Buy the full dump at /list."
    )

async def custom(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Request custom malware for 0.05 BTC. DM @NullBotAdmin with specs."
    )

async def auction(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Rare 1M CC dump auction! Bid in XMR via /list. Ends in 24h."
    )

async def subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"Subscribe for daily dark web alerts: 0.005 XMR/month to {XMR_ADDRESS}. Reply with TX ID."
    )

async def poison(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"Poison a dataset with fake CCs for 0.02 BTC. Send to [BTC_ADDRESS] and reply with TX ID."
    )

async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sales = load_sales()
    top_buyers = {}
    for sale in sales:
        user_id = sale["user_id"]
        top_buyers[user_id] = top_buyers.get(user_id, 0) + 1
    leaderboard = "\n".join(f"User {k}: {v} scores" for k, v in sorted(top_buyers.items(), key=lambda x: x[1], reverse=True)[:5])
    await update.message.reply_text(f"Top Operatives:\n{leaderboard}\nJoin the ranks at /list.")

async def alert(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Urgent: New 10M CC leak! Buy now at /list before it’s gone.")

async def radio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Tune into NullBot Radio: Cyberpunk tracks to fuel your hacks. Try /list for the real vibes."
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "pending_black_market" in context.user_data:
        tx_id = update.message.text
        black_market_users = load_black_market_users()
        black_market_users.append(str(update.message.from_user.id))
        save_black_market_users(black_market_users)
        await update.message.reply_text("Black Market unlocked! Check /list for exclusive loot.")
        del context.user_data["pending_black_market"]
    elif "hack_challenge" in context.user_data:
        if update.message.text == context.user_data["hack_challenge"]:
            discount_code = f"NULL{random.randint(1000, 9999)}"
            discounts = json.load(open(DISCOUNTS_FILE, "r"))
            discounts[discount_code] = 0.1
            with open(DISCOUNTS_FILE, "w") as f:
                json.dump(discounts, f, indent=4)
            await update.message.reply_text(
                f"Respect. Use code {discount_code} for 10% off your next score."
            )
            del context.user_data["hack_challenge"]
        else:
            await update.message.reply_text("Lame. Try again or get lost.")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    item_id = query.data.split("_")[1]
    inventory = load_inventory()
    item = next((i for i in inventory if i["id"] == item_id), None)
    if not item:
        await query.message.reply_text("Item gone. The dark web moves fast.")
        return
    keyboard = [
        [InlineKeyboardButton("Pay with BTC", callback_data=f"pay_btc_{item['id']}")],
        [InlineKeyboardButton("Pay with XMR", callback_data=f"pay_xmr_{item['id']}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.reply_text(
        f"Choose payment method for {item['title']} ({item['price_btc']} BTC / {item['price_btc'] / get_btc_price() * get_xmr_price():.4f} XMR):",
        reply_markup=reply_markup
    )

async def payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data.split("_")
    method, item_id = data[1], data[2]
    inventory = load_inventory()
    item = next((i for i in inventory if i["id"] == item_id), None)
    if not item:
        await query.message.reply_text("Item gone. The dark web moves fast.")
        return
    if method == "btc":
        try:
            response = requests.post(
                "https://www.blockonomics.co/api/new_address",
                headers={"Authorization": f"Bearer {BLOCKONOMICS_API_KEY}"},
                json={"callback": f"https://your-bot-host/callback?secret={CALLBACK_SECRET}"},
                timeout=5
            )
            response.raise_for_status()
            address = response.json().get("address")
            if not address:
                await query.message.reply_text("Error generating BTC address. Try XMR.")
                return
            pending_orders = load_pending_orders()
            pending_orders.append({
                "address": address,
                "item_id": item_id,
                "user_id": query.from_user.id,
                "method": "btc"
            })
            save_pending_orders(pending_orders)
            await query.message.reply_text(
                f"Send {item['price_btc']} BTC to {address}. Link drops when confirmed."
            )
        except requests.RequestException as e:
            logger.error(f"Failed to generate BTC address: {e}")
            await query.message.reply_text("Error generating BTC address. Try XMR.")
    else:  # XMR
        await query.message.reply_text(
            f"Send {item['price_btc'] / get_btc_price() * get_xmr_price():.4f} XMR to {XMR_ADDRESS}. Reply with TX ID."
        )
        pending_orders = load_pending_orders()
        pending_orders.append({
            "address": XMR_ADDRESS,
            "item_id": item_id,
            "user_id": query.from_user.id,
            "method": "xmr"
        })
        save_pending_orders(pending_orders)

# Flask routes
@app.route("/")
def home():
    return "Tax The World NullBot ☠️: Access /admin for control."

@app.route("/callback", methods=["POST"])
def callback():
    if request.args.get("secret") != CALLBACK_SECRET:
        return "Invalid secret", 403
    data = request.json
    if data["status"] == 2:
        address = data["address"]
        pending_orders = load_pending_orders()
        pending = next((p for p in pending_orders if p["address"] == address and p["method"] == "btc"), None)
        if pending:
            inventory = load_inventory()
            item = next((i for i in inventory if i["id"] == pending["item_id"]), None)
            if item:
                sales = load_sales()
                sales.append({
                    "item_id": item["id"],
                    "title": item["title"],
                    "price_btc": item["price_btc"],
                    "price_usd": item["price_usd"],
                    "user_id": pending["user_id"],
                    "timestamp": data["time"]
                })
                save_sales(sales)
                key = get_random_bytes(16)
                encrypted_path, key = encrypt_file(item["file_path"], key)
                if encrypted_path and key:
                    bot = Application.builder().token(BOT_TOKEN).build()
                    asyncio.get_event_loop().run_until_complete(
                        bot.bot.send_document(
                            chat_id=pending["user_id"],
                            document=open(encrypted_path, "rb"),
                            caption=f"Payment confirmed! Encrypted file. Decryption key: {key.hex()}\nUse OpenSSL to decrypt."
                        )
                    )
                pending_orders.remove(pending)
                save_pending_orders(pending_orders)
    return "OK", 200

@app.route("/webhook", methods=["POST"])
async def webhook():
    try:
        update = Update.de_json(request.get_json(force=True), application.bot)
        await application.process_update(update)
        return "OK", 200
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return "Error", 500

@app.route("/admin")
def admin_panel():
    inventory = load_inventory()
    sales = load_sales()
    total_sales = len(sales)
    total_revenue_btc = sum(float(s["price_btc"]) for s in sales)
    total_revenue_usd = sum(float(s["price_usd"]) for s in sales)
    top_buyers = {}
    for sale in sales:
        user_id = sale["user_id"]
        top_buyers[user_id] = top_buyers.get(user_id, 0) + 1
    top_buyers_html = "".join(f"<li>User {k}: {v} scores</li>" for k, v in sorted(top_buyers.items(), key=lambda x: x[1], reverse=True)[:5])
    html = """
    <html>
    <head>
        <title>Tax The World NullBot ☠️ Admin</title>
        <style>
            body { font-family: 'Courier New', monospace; background: #000; color: #0f0; }
            table { border-collapse: collapse; width: 100%; color: #0f0; }
            th, td { border: 1px solid #0f0; padding: 8px; text-align: left; }
            th { background-color: #111; }
            .form-group { margin-bottom: 15px; }
            a { color: #0ff; }
            h1 { text-align: center; }
        </style>
    </head>
    <body>
        <h1>Tax The World NullBot ☠️ Admin Panel</h1>
        <h2>Dark Pool Stats</h2>
        <p>Total Scores: {}</p>
        <p>Total Loot: {} BTC (${} USD)</p>
        <h3>Top Operatives</h3>
        <ul>{}</ul>
        <h2>Inventory Control</h2>
        <table>
            <tr><th>ID</th><th>Title</th><th>Tier</th><th>Price (BTC)</th><th>Price (USD)</th><th>Thumbnail</th><th>Actions</th></tr>
            {}
        </table>
        <h2>Add New Loot</h2>
        <form action="/add_item" method="POST" enctype="multipart/form-data">
            <div class="form-group">
                <label>Title:</label><input type="text" name="title" required>
            </div>
            <div class="form-group">
                <label>Description:</label><textarea name="description" required></textarea>
            </div>
            <div class="form-group">
                <label>Tier:</label><select name="tier"><option value="standard">Standard</option><option value="black_market">Black Market</option></select>
            </div>
            <div class="form-group">
                <label>Price (BTC):</label><input type="number" step="0.00000001" name="price_btc" required>
            </div>
            <div class="form-group">
                <label>Price (USD):</label><input type="number" step="0.01" name="price_usd" required>
            </div>
            <div class="form-group">
                <label>File:</label><input type="file" name="file" accept=".pdf,.txt" required>
            </div>
            <button type="submit">Add Loot</button>
        </form>
    </body>
    </html>
    """.format(
        total_sales,
        total_revenue_btc,
        total_revenue_usd,
        top_buyers_html,
        "".join(
            f"<tr><td>{i['id']}</td><td>{i['title']}</td><td>{i['tier']}</td><td>{i['price_btc']}</td><td>{i['price_usd']}</td><td><img src='{i['thumbnail']}' width='50'></td><td><a href='/delete_item/{i['id']}'>Delete</a></td></tr>"
            for i in inventory
        )
    )
    return html

@app.route("/add_item", methods=["POST"])
def add_item():
    try:
        title = request.form["title"]
        description = request.form["description"]
        tier = request.form["tier"]
        price_btc = float(request.form["price_btc"])
        price_usd = float(request.form["price_usd"])
        file = request.files["file"]
        file_path = os.path.join("uploads", file.filename)
        os.makedirs("uploads", exist_ok=True)
        file.save(file_path)
        thumbnail_path = f"thumbnails/{file.filename}.png"
        os.makedirs("thumbnails", exist_ok=True)
        generate_screenshot(file_path, thumbnail_path)
        inventory = load_inventory()
        item_id = str(len(inventory) + 1)
        inventory.append({
            "id": item_id,
            "title": title,
            "description": description,
            "tier": tier,
            "price_btc": price_btc,
            "price_usd": price_usd,
            "file_path": file_path,
            "thumbnail": thumbnail_path
        })
        save_inventory(inventory)
        return redirect("/admin")
    except Exception as e:
        logger.error(f"Failed to add item: {e}")
        return "Error adding item", 500

@app.route("/delete_item/<item_id>")
def delete_item(item_id):
    try:
        inventory = load_inventory()
        inventory = [i for i in inventory if i["id"] != item_id]
        save_inventory(inventory)
        return redirect("/admin")
    except Exception as e:
        logger.error(f"Failed to delete item: {e}")
        return "Error deleting item", 500

# Run Flask in a separate thread for local testing
def run_flask():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)

async def main():
    global application
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("list", list_items))
    application.add_handler(CommandHandler("admin", admin))
    application.add_handler(CommandHandler("join_black_market", join_black_market))
    application.add_handler(CommandHandler("hack", hack))
    application.add_handler(CommandHandler("refer", refer))
    application.add_handler(CommandHandler("reviews", reviews))
    application.add_handler(CommandHandler("ddos_teaser", ddos_teaser))
    application.add_handler(CommandHandler("burn", burn))
    application.add_handler(CommandHandler("demo", demo))
    application.add_handler(CommandHandler("custom", custom))
    application.add_handler(CommandHandler("auction", auction))
    application.add_handler(CommandHandler("subscribe", subscribe))
    application.add_handler(CommandHandler("poison", poison))
    application.add_handler(CommandHandler("leaderboard", leaderboard))
    application.add_handler(CommandHandler("alert", alert))
    application.add_handler(CommandHandler("radio", radio))
    application.add_handler(CallbackQueryHandler(button_callback, pattern="^buy_"))
    application.add_handler(CallbackQueryHandler(payment_callback, pattern="^pay_"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    # Retry initialization on network error
    for attempt in range(3):
        try:
            await application.initialize()
            break
        except NetworkError as e:
            logger.error(f"Network error during initialization: {e}. Retrying in 5 seconds...")
            await asyncio.sleep(5)
    else:
        raise NetworkError("Failed to initialize bot after 3 attempts due to network issues.")
    return application

if __name__ == "__main__":
    # Start Flask in a separate thread
    flask_thread = Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    # Run Telegram bot with polling
    try:
        application = asyncio.run(main())
        asyncio.run(application.run_polling())
    except NetworkError as e:
        logger.error(f"Bot failed to start: {e}")
        print("Network error. Check your internet connection and DNS settings.")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        print("An unexpected error occurred. Check logs for details.")