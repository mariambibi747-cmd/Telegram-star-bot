import json
import os
import asyncio
from threading import Thread
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

# --- 1. DUMMY SERVER FOR RENDER (Keep Alive) ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is Running! (Made for Render)"

def run_flask():
    # Render automatically assigns a PORT
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_flask)
    t.daemon = True
    t.start()

# --- 2. CONFIG ---
# Aapka Token seedha yahan hai (Environment Variable ki zaroorat nahi ab)
BOT_TOKEN = "8297951307:AAG1q8b2FweFpgtOQTlGkkocbHDOizhdapI"
ADMIN_ID = 7415661180
PAYOUT_CHANNEL = "https://t.me/YourChannel"  # 👈 Yahan apna channel link dalein
STARS_PER_REFERRAL = 2
MIN_WITHDRAW = 15
WELCOME_BONUS = 1

# --- 3. DATABASE (Temporary JSON) ---
DATA_FILE = "user_database.json"
CHANNELS_FILE = "force_channels.json"

def load_json(f, d):
    if os.path.exists(f):
        try:
            with open(f, 'r') as file: return json.load(file)
        except: return d
    return d

def save_json(f, d):
    try:
        with open(f, 'w') as out: json.dump(d, out, indent=2)
    except: pass

data = load_json(DATA_FILE, {"users": {}})

# --- 4. CORE FUNCTIONS ---
async def is_subscribed(context, uid):
    chans = load_json(CHANNELS_FILE, [])
    if not chans: return True
    for c in chans:
        try:
            m = await context.bot.get_chat_member(c, uid)
            if m.status in ['left', 'kicked']: return False
        except: return False
    return True

# --- 5. MENUS ---
def main_menu():
    return ReplyKeyboardMarkup([
        [KeyboardButton("👤 Profile"), KeyboardButton("🌟 Earn Stars")],
        [KeyboardButton("💸 Withdraw"), KeyboardButton("🎁 Payouts")],
        [KeyboardButton("📊 Stats")]
    ], resize_keyboard=True)

# --- 6. HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user: return
    uid = str(update.effective_user.id)
    
    # Force Join Check
    if not await is_subscribed(context, uid):
        chans = load_json(CHANNELS_FILE, [])
        markup = []
        if not chans:
             markup.append([InlineKeyboardButton("📢 Join Channel", url=PAYOUT_CHANNEL)])
        else:
            for i, c in enumerate(chans, 1):
                try:
                    chat = await context.bot.get_chat(c)
                    link = f"https://t.me/{chat.username}" if chat.username else PAYOUT_CHANNEL
                    markup.append([InlineKeyboardButton(f"📢 Join Channel {i}", url=link)])
                except: continue
        
        markup.append([InlineKeyboardButton("✅ I HAVE JOINED", callback_data="verify")])
        return await update.message.reply_text("<b>⚠️ Access Denied!</b>\nJoin our channels to use the bot.", parse_mode='HTML', reply_markup=InlineKeyboardMarkup(markup))

    # Register User
    if uid not in data["users"]:
        ref_id = context.args[0] if context.args else None
        data["users"][uid] = {"stars": WELCOME_BONUS, "referrals": 0, "paid": 0}
        
        # Referral Bonus
        if ref_id and ref_id in data["users"] and ref_id != uid:
            data["users"][ref_id]["stars"] += STARS_PER_REFERRAL
            data["users"][ref_id]["referrals"] += 1
            try: await context.bot.send_message(ref_id, f"<b>🌟 +{STARS_PER_REFERRAL} Stars! New Referral.</b>", parse_mode='HTML')
            except: pass
        save_json(DATA_FILE, data)

    await update.message.reply_text(f"<b>✨ Welcome {update.effective_user.first_name}!</b>\nStart earning stars now.", parse_mode='HTML', reply_markup=main_menu())

async def handle_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not update.message.text: return
    uid, txt = str(update.effective_user.id), update.message.text
    
    # Reload data if needed (Render reset protection logic)
    if uid not in data["users"]: return await start(update, context)
    u = data["users"][uid]

    if txt == "👤 Profile":
        await update.message.reply_text(f"<b>👤 PROFILE</b>\n\n🆔 ID: <code>{uid}</code>\n💰 Balance: <code>{u['stars']}</code> Stars\n👥 Referrals: {u['referrals']}", parse_mode='HTML')
    
    elif txt == "🌟 Earn Stars":
        bot = await context.bot.get_me()
        await update.message.reply_text(f"<b>🔗 Your Invite Link:</b>\nhttps://t.me/{bot.username}?start={uid}", parse_mode='HTML')

    elif txt == "💸 Withdraw":
        if u['stars'] < MIN_WITHDRAW:
            await update.message.reply_text(f"❌ <b>Min Withdraw: {MIN_WITHDRAW} Stars</b>", parse_mode='HTML')
        else:
            await update.message.reply_text("<b>📝 Send your Wallet Address:</b>", parse_mode='HTML')
            context.user_data['waiting_wallet'] = True

    elif txt == "🎁 Payouts":
        markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔗 View Proofs", url=PAYOUT_CHANNEL)]])
        await update.message.reply_text("<b>✅ Check Payments Here:</b>", parse_mode='HTML', reply_markup=markup)

    elif txt == "📊 Stats":
        await update.message.reply_text(f"<b>📊 Users:</b> {len(data['users'])}", parse_mode='HTML')

    elif context.user_data.get('waiting_wallet'):
        # Process Withdraw
        await context.bot.send_message(ADMIN_ID, f"🚨 <b>NEW WITHDRAWAL!</b>\nUser: {uid}\nAmount: {u['stars']}\nWallet: <code>{txt}</code>", parse_mode='HTML')
        u['paid'] += u['stars']
        u['stars'] = 0
        save_json(DATA_FILE, data)
        context.user_data['waiting_wallet'] = False
        await update.message.reply_text("✅ <b>Request Sent!</b>", parse_mode='HTML')

# --- 7. ADMIN TOOLS ---
async def admin_tools(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    txt = update.message.text
    
    if txt.startswith("/addchannel"):
        try:
            target = txt.split()[1].replace("@", "")
            c = await context.bot.get_chat(f"@{target}")
            chans = load_json(CHANNELS_FILE, [])
            if c.id not in chans:
                chans.append(c.id); save_json(CHANNELS_FILE, chans)
                await update.message.reply_text(f"✅ Added: {c.title}")
        except: await update.message.reply_text("Error: Make me admin in that channel first.")

    elif txt == "/broadcast" and update.message.reply_to_message:
        users = list(data["users"].keys())
        await update.message.reply_text(f"🚀 Sending to {len(users)} users...")
        for u in users:
            try:
                await context.bot.copy_message(u, update.effective_chat.id, update.message.reply_to_message.message_id)
                await asyncio.sleep(0.04)
            except: continue
        await update.message.reply_text("✅ Broadcast Done!")

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if q.data == "verify":
        if await is_subscribed(context, q.from_user.id):
            await q.message.delete()
            await start(update, context)
        else: await q.answer("❌ Join channels first!", show_alert=True)

# --- 8. RUNNER ---
def main():
    keep_alive() # Start Flask Server
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("broadcast", admin_tools))
    app.add_handler(CommandHandler("addchannel", admin_tools))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_msg))
    print("Bot is Live on Render!")
    app.run_polling()

if __name__ == "__main__":
    main()
