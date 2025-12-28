import json, os, asyncio
from threading import Thread
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

# --- FLASK SERVER (For Render) ---
app = Flask(__name__)
@app.route('/')
def home(): return "Bot is Online"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# --- CONFIGURATION ---
BOT_TOKEN = "8297951307:AAG1q8b2FweFpgtOQTlGkkocbHDOizhdapI"
ADMIN_ID = 7415661180
PAYOUT_LINK = "https://t.me/YourPayoutChannel" # 👈 Apna Payout link yahan daalein
STARS_PER_REFERRAL = 2
MIN_WITHDRAW = 15
WELCOME_BONUS = 1
MAX_REFER_LIMIT = 14 

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

# --- CORE LOGIC ---
async def is_subscribed(context, uid):
    chans = load_json(CHANNELS_FILE, [])
    if not chans: return True
    for c in chans:
        try:
            m = await context.bot.get_chat_member(c, uid)
            if m.status in ['left', 'kicked']: return False
        except: return False
    return True

# --- MENUS ---
def main_menu():
    keys = [
        [KeyboardButton("👤 Profile"), KeyboardButton("🌟 Earn Stars")],
        [KeyboardButton("💸 Withdraw"), KeyboardButton("🎁 Payouts")],
        [KeyboardButton("📊 Stats")]
    ]
    return ReplyKeyboardMarkup(keys, resize_keyboard=True)

# --- HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user: return
    uid = str(update.effective_user.id)
    first_name = update.effective_user.first_name

    # Force Join Check
    if not await is_subscribed(context, uid):
        chans = load_json(CHANNELS_FILE, [])
        markup = []
        for i, c in enumerate(chans, 1):
            try:
                chat = await context.bot.get_chat(c)
                link = f"https://t.me/{chat.username}" if chat.username else PAYOUT_LINK
                markup.append([InlineKeyboardButton(f"📢 Join Channel {i}", url=link)])
            except: continue
        markup.append([InlineKeyboardButton("✅ I HAVE JOINED", callback_data="verify")])
        
        txt = f"<b>👋 Welcome {first_name}!</b>\n\n⚠️ <b>Access Locked!</b> Join our channels below to use the bot and earn stars."
        return await update.message.reply_text(txt, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(markup))

    # User Registration
    if uid not in data["users"]:
        ref_id = context.args[0] if context.args else None
        data["users"][uid] = {"stars": WELCOME_BONUS, "referrals": 0, "paid": 0}
        
        # Referral Logic with 14 Star Limit
        if ref_id and ref_id in data["users"] and ref_id != uid:
            u_ref = data["users"][ref_id]
            if u_ref["stars"] >= MAX_REFER_LIMIT:
                # Limit cross: No reward and error message
                try: await context.bot.send_message(ref_id, "<b>❌ Referral Failed!</b>\n\nAapke dost ne saare channels join nahi kiye hain, isliye aapko reward nahi mila.", parse_mode='HTML')
                except: pass
            else:
                # Give reward
                u_ref["stars"] += STARS_PER_REFERRAL
                u_ref["referrals"] += 1
                try: await context.bot.send_message(ref_id, f"<b>🌟 Referral Success!</b>\n\nYou received <b>+{STARS_PER_REFERRAL} Stars</b>.", parse_mode='HTML')
                except: pass
        save_json(DATA_FILE, data)

    welcome_txt = f"<b>✨ NEW YEAR STAR BOT ✨</b>\n\nWelcome <b>{first_name}</b>, start inviting friends to earn real stars!"
    await update.message.reply_text(welcome_txt, parse_mode='HTML', reply_markup=main_menu())

async def handle_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not update.message.text: return
    uid, txt = str(update.effective_user.id), update.message.text
    if uid not in data["users"]: return await start(update, context)
    u = data["users"][uid]

    if txt == "👤 Profile":
        p_txt = (f"<b>👤 MY PROFILE</b>\n\n"
                 f"<b>🆔 ID:</b> <code>{uid}</code>\n"
                 f"<b>💰 Balance:</b> <code>{u['stars']}</code> Stars\n"
                 f"<b>👥 Referrals:</b> <code>{u['referrals']}</code>\n"
                 f"<b>💸 Total Paid:</b> <code>{u['paid']}</code> Stars")
        await update.message.reply_text(p_txt, parse_mode='HTML')

    elif txt == "🌟 Earn Stars":
        bot = await context.bot.get_me()
        link = f"https://t.me/{bot.username}?start={uid}"
        e_txt = (f"<b>🌟 EARN STARS</b>\n\n"
                 f"Share your link and get <b>{STARS_PER_REFERRAL} Stars</b> per friend!\n\n"
                 f"<b>🔗 Your Link:</b> <code>{link}</code>")
        await update.message.reply_text(e_txt, parse_mode='HTML')

    elif txt == "💸 Withdraw":
        if u['stars'] < MIN_WITHDRAW:
            await update.message.reply_text(f"<b>❌ Insufficient Balance!</b>\n\nMinimum withdraw is <b>{MIN_WITHDRAW} Stars</b>.", parse_mode='HTML')
        else:
            await update.message.reply_text("<b>📝 Send your Wallet Address:</b>\n(Example: UPI ID, TRX Address, or BTC)", parse_mode='HTML')
            context.user_data['wait_wallet'] = True

    elif txt == "🎁 Payouts":
        p_markup = InlineKeyboardMarkup([[InlineKeyboardButton("📢 View Payout Channel", url=PAYOUT_LINK)]])
        await update.message.reply_text("<b>✅ Click below to see payment proofs:</b>", parse_mode='HTML', reply_markup=p_markup)

    elif txt == "📊 Stats":
        total = len(data["users"])
        await update.message.reply_text(f"<b>📊 LIVE STATISTICS</b>\n\n<b>Total Users:</b> <code>{total}</code>\n<b>Bot Status:</b> 🟢 <code>Online</code>", parse_mode='HTML')

    elif context.user_data.get('wait_wallet'):
        # Admin Notification
        admin_msg = (f"<b>🚨 NEW WITHDRAW REQUEST</b>\n\n"
                     f"<b>User ID:</b> <code>{uid}</code>\n"
                     f"<b>Amount:</b> <code>{u['stars']}</code> Stars\n"
                     f"<b>Wallet:</b> <code>{txt}</code>")
        await context.bot.send_message(ADMIN_ID, admin_msg, parse_mode='HTML')
        
        u['paid'] += u['stars']
        u['stars'] = 0
        save_json(DATA_FILE, data)
        context.user_data['wait_wallet'] = False
        await update.message.reply_text("<b>✅ Success!</b>\nYour request has been sent to Admin. Payment will arrive within 24 hours.", parse_mode='HTML')

# --- ADMIN ACTIONS ---
async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    txt = update.message.text
    
    if txt.startswith("/addchannel"):
        try:
            channel_username = txt.split()[1].replace("@", "").split("/")[-1]
            chat = await context.bot.get_chat(f"@{channel_username}")
            chans = load_json(CHANNELS_FILE, [])
            if chat.id not in chans:
                chans.append(chat.id)
                save_json(CHANNELS_FILE, chans)
                await update.message.reply_text(f"✅ <b>Success!</b>\nAdded: <b>{chat.title}</b>", parse_mode='HTML')
        except Exception as e:
            await update.message.reply_text(f"<b>❌ Error:</b> <code>{e}</code>", parse_mode='HTML')

    elif txt == "/broadcast" and update.message.reply_to_message:
        users = list(data["users"].keys())
        await update.message.reply_text(f"🚀 <b>Broadcasting to {len(users)} users...</b>", parse_mode='HTML')
        for u in users:
            try:
                await context.bot.copy_message(u, update.effective_chat.id, update.message.reply_to_message.message_id)
                await asyncio.sleep(0.04)
            except: continue
        await update.message.reply_text("<b>✅ Broadcast Completed!</b>", parse_mode='HTML')

# --- CALLBACKS ---
async def query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if q.data == "verify":
        if await is_subscribed(context, q.from_user.id):
            await q.message.delete()
            # Fake a message object to call start
            update._effective_user = q.from_user
            await start(update, context)
        else: await q.answer("❌ You haven't joined all channels!", show_alert=True)

def main():
    Thread(target=run_flask).start()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("addchannel", admin_cmd))
    app.add_handler(CommandHandler("broadcast", admin_cmd))
    app.add_handler(CallbackQueryHandler(query_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_msg))
    print("Bot is Live...")
    app.run_polling()

if __name__ == "__main__": main()
