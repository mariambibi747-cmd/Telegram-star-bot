import json, os, asyncio
from threading import Thread
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

# --- FLASK SERVER (For Render) ---
app = Flask(__name__)
@app.route('/')
def home(): return "Bot is Running!"

def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

# --- CONFIG ---
BOT_TOKEN = "8297951307:AAG1q8b2FweFpgtOQTlGkkocbHDOizhdapI"
ADMIN_ID = 7415661180
PAYOUT_CHANNEL = "https://t.me/YourChannel"
STARS_PER_REFERRAL = 2
MIN_WITHDRAW = 15
WELCOME_BONUS = 1
MAX_REFERRAL_STARS = 14 # Isse upar stars nahi milenge

DATA_FILE = "user_database.json"
CHANNELS_FILE = "force_channels.json"

def load_json(f, d):
    if os.path.exists(f):
        try:
            with open(f, 'r') as file: return json.load(file)
        except: return d
    return d

def save_json(f, d):
    with open(f, 'w') as out: json.dump(d, out, indent=2)

data = load_json(DATA_FILE, {"users": {}})

# --- HELPERS ---
async def is_subscribed(context, uid):
    chans = load_json(CHANNELS_FILE, [])
    if not chans: return True
    for c in chans:
        try:
            m = await context.bot.get_chat_member(c, uid)
            if m.status in ['left', 'kicked']: return False
        except: return False
    return True

# --- HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user: return
    uid = str(update.effective_user.id)
    
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
        return await update.message.reply_text("<b>⚠️ Access Denied!</b>\nJoin our channels first.", parse_mode='HTML', reply_markup=InlineKeyboardMarkup(markup))

    if uid not in data["users"]:
        ref_id = context.args[0] if context.args else None
        data["users"][uid] = {"stars": WELCOME_BONUS, "referrals": 0, "paid": 0}
        
        # Referral Limit Logic
        if ref_id and ref_id in data["users"] and ref_id != uid:
            current_stars = data["users"][ref_id]["stars"]
            
            if current_stars >= MAX_REFERRAL_STARS:
                # 14 star se upar hai toh jhoot bol do
                try: await context.bot.send_message(ref_id, "<b>❌ Referral Failed!</b>\nAapke dost ne saare channel complete join nahi kiye isliye reward nahi mila.", parse_mode='HTML')
                except: pass
            else:
                # 14 se kam hai toh reward do
                data["users"][ref_id]["stars"] += STARS_PER_REFERRAL
                data["users"][ref_id]["referrals"] += 1
                try: await context.bot.send_message(ref_id, f"<b>🌟 +{STARS_PER_REFERRAL} Stars!</b> New Referral Success.", parse_mode='HTML')
                except: pass
        save_json(DATA_FILE, data)

    keys = ReplyKeyboardMarkup([["👤 Profile", "🌟 Earn Stars"], ["💸 Withdraw", "🎁 Payouts"], ["📊 Stats"]], resize_keyboard=True)
    await update.message.reply_text("✨ <b>Welcome!</b> Bot is ready.", parse_mode='HTML', reply_markup=keys)

async def handle_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not update.message.text: return
    uid, txt = str(update.effective_user.id), update.message.text
    if uid not in data["users"]: return await start(update, context)
    u = data["users"][uid]

    if txt == "👤 Profile":
        await update.message.reply_text(f"💰 Balance: {u['stars']} Stars")
    elif txt == "🌟 Earn Stars":
        bot = await context.bot.get_me()
        await update.message.reply_text(f"Link: https://t.me/{bot.username}?start={uid}")
    elif txt == "💸 Withdraw":
        if u['stars'] < MIN_WITHDRAW: await update.message.reply_text(f"Min {MIN_WITHDRAW} required!")
        else:
            await update.message.reply_text("Send Wallet Address:")
            context.user_data['wait'] = True
    elif context.user_data.get('wait'):
        await context.bot.send_message(ADMIN_ID, f"🚨 Withdrawal: {uid}\nStars: {u['stars']}\nWallet: {txt}")
        u['paid'] += u['stars']; u['stars'] = 0; save_json(DATA_FILE, data)
        context.user_data['wait'] = False
        await update.message.reply_text("✅ Sent!")

# --- ADMIN COMMANDS ---
async def admin_tools(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    txt = update.message.text
    
    if txt.startswith("/addchannel"):
        try:
            # Username clean karne ka logic
            raw_user = txt.split()[1].replace("@", "").split("/")[-1]
            chat = await context.bot.get_chat(f"@{raw_user}")
            chans = load_json(CHANNELS_FILE, [])
            if chat.id not in chans:
                chans.append(chat.id)
                save_json(CHANNELS_FILE, chans)
                await update.message.reply_text(f"✅ Channel Added: {chat.title}")
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {e}\nCheck if Bot is admin in channel.")

def main():
    Thread(target=run_flask).start()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("addchannel", admin_tools))
    app.add_handler(CallbackQueryHandler(start, pattern="verify"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_msg))
    app.run_polling()

if __name__ == "__main__": main()

