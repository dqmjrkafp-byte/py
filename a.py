import random
import asyncio
import aiosqlite
import uuid
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandStart, CommandObject
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice, PreCheckoutQuery, Message, BotCommand, BotCommandScopeAllGroupChats
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# --- КОНФИГУРАЦИЯ ---
TOKEN = '8456017578:AAF6hR8gRFTZmWeXzYqfwltx8ASjm7meiQw'
ADMIN_ID = 7567154840
DB_NAME = 'main_market.db'

NFT_DATA = {
    "hat": {"name": "Шляпа", "emoji": "🎩", "stars": 3, "coins": 300},
    "backpack": {"name": "Рюкзак", "emoji": "🎒", "stars": 5, "coins": 500},
    "coconut": {"name": "Кокос", "emoji": "🥥", "stars": 2, "coins": 200},
    "snake": {"name": "Змея", "emoji": "🐍", "stars": 4, "coins": 400},
    "calendar": {"name": "Календарь", "emoji": "📅", "stars": 1, "coins": 100},
    "bag": {"name": "Сумка", "emoji": "👜", "stars": 6, "coins": 600},
    "redo": {"name": "РЕДО", "emoji": "🎁", "stars": 8, "coins": 800},
    "watch": {"name": "ЧАСЫ", "emoji": "⌚️", "stars": 10, "coins": 1000},
    "cigar": {"name": "СИГАРА", "emoji": "🚬", "stars": 5, "coins": 500},
    "helmet": {"name": "Шлем", "emoji": "⛑", "stars": 4, "coins": 400},
    "poop": {"name": "Какашка", "emoji": "💩", "stars": 1, "coins": 50},
    "socks": {"name": "Носки", "emoji": "🧦", "stars": 2, "coins": 150},
    "monkey": {"name": "Обезьяна", "emoji": "🐒", "stars": 7, "coins": 700},
    "sword": {"name": "Меч", "emoji": "⚔️", "stars": 9, "coins": 900},
    "frog": {"name": "Лягушка", "emoji": "🐸", "stars": 3, "coins": 300},
    "oscar": {"name": "Оскар", "emoji": "🗽", "stars": 15, "coins": 1500},
    "cap": {"name": "Кепка", "emoji": "🧢", "stars": 3, "coins": 250},
    "damirka": {"name": "Дамирка", "emoji": "🎁", "stars": 1, "coins": 500},
}

class Form(StatesGroup):
    transfer_id = State()
    transfer_amt = State()
    auc_price = State()
    adm_target = State()
    adm_coins = State()
    check_amt = State()

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# --- UTILS ---
def get_receipt(title, amt, sender, target=None, item=None):
    now = datetime.now().strftime("%d.%m %H:%M")
    txt = f"💚 **{title}**\n━━━━━━━━━━━━━━\n✅ **Исполнено**\n\n💰 **Сумма:** {amt}\n👤 **От:** `{sender}`\n"
    if target: txt += f"👥 **Кому:** `{target}`\n"
    if item: txt += f"🎁 **Товар:** {item}\n"
    txt += f"📅 **Дата:** {now}\n━━━━━━━━━━━━━━\n🏦 *Mystery Bank*"
    return txt

async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, coins INTEGER DEFAULT 100)')
        await db.execute('''CREATE TABLE IF NOT EXISTS inventory 
            (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, item_key TEXT, serial_num INTEGER, on_sale INTEGER DEFAULT 0, price INTEGER DEFAULT 0)''')
        await db.execute('CREATE TABLE IF NOT EXISTS checks (id TEXT PRIMARY KEY, creator_id INTEGER, amount INTEGER, active INTEGER DEFAULT 1)')
        await db.commit()

async def set_commands():
    commands = [
        BotCommand(command="start", description="регистрация / меню"),
        BotCommand(command="prof", description="мой профиль"),
        BotCommand(command="check", description="создать чек"),
        BotCommand(command="menu", description="главное меню")
    ]
    await bot.set_my_commands(commands)
    await bot.set_my_commands(commands, scope=BotCommandScopeAllGroupChats())

async def get_main_kb(uid, chat_type):
    if chat_type == "private":
        btns = [
            [InlineKeyboardButton(text="⭐ Магазин Stars", callback_data="go_stars"), InlineKeyboardButton(text="🪙 Магазин Coins", callback_data="go_coins")],
            [InlineKeyboardButton(text="🔨 Аукцион", callback_data="go_auc"), InlineKeyboardButton(text="🎫 Создать чек", callback_data="go_check")],
            [InlineKeyboardButton(text="👤 Профиль", callback_data="go_prof"), InlineKeyboardButton(text="💸 Перевод", callback_data="go_trans")]
        ]
        if uid == ADMIN_ID:
            btns.append([InlineKeyboardButton(text="👑 Админ-Панель", callback_data="go_adm")])
    else:
        me = await bot.get_me()
        btns = [
            [InlineKeyboardButton(text="👤 Мой Профиль", callback_data="go_prof")],
            [InlineKeyboardButton(text="💎 Перейти в Маркет", url=f"https://t.me/{me.username}")]
        ]
    return InlineKeyboardMarkup(inline_keyboard=btns)

# --- START & CHECKS ---
@dp.message(CommandStart())
async def cmd_start(m: Message, command: CommandObject, state: FSMContext):
    await state.clear()
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('INSERT OR IGNORE INTO users (user_id) VALUES (?)', (m.from_user.id,))
        await db.commit()
    
    args = command.args
    if args and args.startswith("act_"):
        cid = args.replace("act_", "")
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute('SELECT creator_id, amount, active FROM checks WHERE id=?', (cid,)) as cur:
                check = await cur.fetchone()
            if not check or check[2] == 0: return await m.answer("❌ Чек уже активирован.")
            if check[0] == m.from_user.id: return await m.answer("❌ Свой чек нельзя активировать.")
            await db.execute('UPDATE checks SET active = 0 WHERE id = ?', (cid,))
            await db.execute('UPDATE users SET coins = coins + ? WHERE user_id = ?', (check[1], m.from_user.id))
            await db.commit()
        return await m.answer(get_receipt("ЧЕК АКТИВИРОВАН", f"{check[1]} 🪙", check[0], target=m.from_user.id))

    kb = await get_main_kb(m.from_user.id, m.chat.type)
    await m.answer("💎 **NFT GIFT MARKET**", reply_markup=kb)

# --- PROFILE ---
async def show_profile_logic(user_id, first_name):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute('SELECT coins FROM users WHERE user_id=?', (user_id,)) as cur:
            row = await cur.fetchone(); bal = row[0] if row else 0
        async with db.execute('SELECT item_key, serial_num FROM inventory WHERE user_id=?', (user_id,)) as cur:
            items = await cur.fetchall()
    val = sum(NFT_DATA.get(i[0], {}).get('coins', 0) for i in items)
    txt = f"👤 **Профиль {first_name}:**\n💰 Баланс: {bal} 🪙\n📊 Ценность: {val} 🪙\n\n🖼 **Инвентарь:**\n"
    txt += "\n".join([f"• {NFT_DATA[i[0]]['emoji']} {NFT_DATA[i[0]]['name']} #{i[1]}" for i in items]) if items else "_Пусто_"
    return txt

@dp.message(Command("prof"))
async def cmd_prof(m: Message):
    txt = await show_profile_logic(m.from_user.id, m.from_user.first_name)
    kb = await get_main_kb(m.from_user.id, m.chat.type)
    await m.answer(txt, reply_markup=kb)

@dp.callback_query(F.data == "go_prof")
async def cb_prof(c: types.CallbackQuery):
    txt = await show_profile_logic(c.from_user.id, c.from_user.first_name)
    kb = await get_main_kb(c.from_user.id, c.message.chat.type)
    await c.message.edit_text(txt, reply_markup=kb)

# --- TRANSFERS ---
@dp.callback_query(F.data == "go_trans")
async def tr_start(c: types.CallbackQuery, state: FSMContext):
    if c.message.chat.type != "private": return await c.answer("Только в ЛС!", show_alert=True)
    await c.message.answer("Введите ID получателя:"); await state.set_state(Form.transfer_id)

@dp.message(Form.transfer_id)
async def tr_id(m: Message, state: FSMContext):
    if not m.text.isdigit(): return await m.answer("ID должен состоять из цифр!")
    await state.update_data(tid=int(m.text)); await m.answer("Введите сумму:"); await state.set_state(Form.transfer_amt)

@dp.message(Form.transfer_amt)
async def tr_fin(m: Message, state: FSMContext):
    if not m.text.isdigit(): return await m.answer("Сумма должна быть числом!")
    amt = int(m.text); d = await state.get_data()
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute('SELECT coins FROM users WHERE user_id=?', (m.from_user.id,)) as cur:
            row = await cur.fetchone(); bal = row[0] if row else 0
        if bal < amt: return await m.answer("❌ Недостаточно монет!")
        await db.execute('UPDATE users SET coins = coins - ? WHERE user_id = ?', (amt, m.from_user.id))
        await db.execute('INSERT OR IGNORE INTO users (user_id) VALUES (?)', (d['tid'],))
        await db.execute('UPDATE users SET coins = coins + ? WHERE user_id = ?', (amt, d['tid']))
        await db.commit()
    await m.answer(get_receipt("ПЕРЕВОД МОНЕТ", f"{amt} 🪙", m.from_user.id, target=d['tid']))
    await state.clear()

# --- SHOPS ---
@dp.callback_query(F.data == "go_stars")
async def shop_stars(c: types.CallbackQuery):
    if c.message.chat.type != "private": return await c.answer("Только в ЛС!", show_alert=True)
    btns = [[InlineKeyboardButton(text=f"{v['emoji']} {v['name']} - {v['stars']}⭐", callback_data=f"bst_{k}")] for k,v in NFT_DATA.items()]
    btns.append([InlineKeyboardButton(text="🔙 Назад", callback_data="to_main")])
    await c.message.edit_text("✨ Покупка через Stars:", reply_markup=InlineKeyboardMarkup(inline_keyboard=btns))

@dp.callback_query(F.data.startswith("bst_"))
async def pay_stars(c: types.CallbackQuery):
    k = c.data.split("_")[1]; v = NFT_DATA[k]
    await bot.send_invoice(c.from_user.id, f"NFT {v['name']}", "Покупка", f"pst_{k}", "XTR", [LabeledPrice(label="XTR", amount=v['stars'])])

@dp.pre_checkout_query()
async def pre_checkout(q: PreCheckoutQuery): await q.answer(True)

@dp.message(F.successful_payment)
async def got_payment(m: Message):
    k = m.successful_payment.invoice_payload.split("_")[1]; sn = random.randint(1000, 9999)
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('INSERT INTO inventory (user_id, item_key, serial_num) VALUES (?, ?, ?)', (m.from_user.id, k, sn))
        await db.commit()
    await m.answer(get_receipt("ПОКУПКА NFT", f"{NFT_DATA[k]['stars']} Stars", m.from_user.id, item=f"{NFT_DATA[k]['name']} #{sn}"))

@dp.callback_query(F.data == "go_coins")
async def shop_coins(c: types.CallbackQuery):
    if c.message.chat.type != "private": return await c.answer("Только в ЛС!", show_alert=True)
    btns = [[InlineKeyboardButton(text=f"{v['emoji']} {v['name']} - {v['coins']}🪙", callback_data=f"bco_{k}")] for k,v in NFT_DATA.items()]
    btns.append([InlineKeyboardButton(text="🔙 Назад", callback_data="to_main")])
    await c.message.edit_text("🪙 Покупка за монеты:", reply_markup=InlineKeyboardMarkup(inline_keyboard=btns))

@dp.callback_query(F.data.startswith("bco_"))
async def pay_coins(c: types.CallbackQuery):
    k = c.data.split("_")[1]; v = NFT_DATA[k]
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute('SELECT coins FROM users WHERE user_id=?', (c.from_user.id,)) as cur:
            row = await cur.fetchone(); bal = row[0] if row else 0
        if bal < v['coins']: return await c.answer("❌ Мало монет!", show_alert=True)
        sn = random.randint(1000, 9999)
        await db.execute('UPDATE users SET coins = coins - ? WHERE user_id = ?', (v['coins'], c.from_user.id))
        await db.execute('INSERT INTO inventory (user_id, item_key, serial_num) VALUES (?, ?, ?)', (c.from_user.id, k, sn))
        await db.commit()
    await c.message.answer(get_receipt("ПОКУПКА NFT", f"{v['coins']} 🪙", c.from_user.id, item=f"{v['name']} #{sn}"))

# --- AUCTION ---
@dp.callback_query(F.data == "go_auc")
async def auc_h(c: types.CallbackQuery):
    if c.message.chat.type != "private": return await c.answer("Только в ЛС!", show_alert=True)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🛒 Купить", callback_data="auc_buy"), InlineKeyboardButton(text="💰 Продать", callback_data="auc_sell")],[InlineKeyboardButton(text="🔙", callback_data="to_main")]])
    await c.message.edit_text("🔨 **АУКЦИОН**", reply_markup=kb)

@dp.callback_query(F.data == "auc_sell")
async def auc_s_l(c: types.CallbackQuery):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute('SELECT id, item_key, serial_num FROM inventory WHERE user_id=? AND on_sale=0', (c.from_user.id,)) as cur:
            items = await cur.fetchall()
    if not items: return await c.answer("❌ Нет NFT!", show_alert=True)
    btns = [[InlineKeyboardButton(text=f"{NFT_DATA[i[1]]['name']} #{i[2]}", callback_data=f"aset_{i[0]}")] for i in items]
    btns.append([InlineKeyboardButton(text="🔙", callback_data="go_auc")])
    await c.message.edit_text("Что продаем?", reply_markup=InlineKeyboardMarkup(inline_keyboard=btns))

@dp.callback_query(F.data.startswith("aset_"))
async def auc_s_p(c: types.CallbackQuery, state: FSMContext):
    await state.update_data(iid=int(c.data.split("_")[1])); await c.message.answer("Цена в 🪙:"); await state.set_state(Form.auc_price)

@dp.message(Form.auc_price)
async def auc_f_s(m: Message, state: FSMContext):
    if not m.text.isdigit(): return
    p = int(m.text); d = await state.get_data()
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('UPDATE inventory SET on_sale=1, price=? WHERE id=? AND user_id=?', (p, d['iid'], m.from_user.id))
        await db.commit()
    await m.answer(f"✅ Выставлено за {p} 🪙"); await state.clear()

@dp.callback_query(F.data == "auc_buy")
async def auc_b_l(c: types.CallbackQuery):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute('SELECT id, item_key, serial_num, price FROM inventory WHERE on_sale=1 AND user_id!=?', (c.from_user.id,)) as cur:
            lots = await cur.fetchall()
    if not lots: return await c.answer("Лотов нет!", show_alert=True)
    btns = [[InlineKeyboardButton(text=f"{NFT_DATA[l[1]]['name']} - {l[3]}🪙", callback_data=f"abuy_{l[0]}")] for l in lots]
    btns.append([InlineKeyboardButton(text="🔙", callback_data="go_auc")])
    await c.message.edit_text("Витрина:", reply_markup=InlineKeyboardMarkup(inline_keyboard=btns))

@dp.callback_query(F.data.startswith("abuy_"))
async def auc_f_b(c: types.CallbackQuery):
    lid = int(c.data.split("_")[1])
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute('SELECT user_id, price, item_key, serial_num FROM inventory WHERE id=? AND on_sale=1', (lid,)) as cur:
            lot = await cur.fetchone()
        if not lot: return await c.answer("Продано!")
        seller, pr, k, sn = lot
        async with db.execute('SELECT coins FROM users WHERE user_id=?', (c.from_user.id,)) as cur:
            row = await cur.fetchone(); bal = row[0] if row else 0
        if bal < pr: return await c.answer("Мало монет!", show_alert=True)
        await db.execute('UPDATE users SET coins=coins-? WHERE user_id=?', (pr, c.from_user.id))
        await db.execute('UPDATE users SET coins=coins+? WHERE user_id=?', (pr, seller))
        await db.execute('UPDATE inventory SET user_id=?, on_sale=0 WHERE id=?', (c.from_user.id, lid))
        await db.commit()
    await c.message.answer(get_receipt("ПОКУПКА (АУКЦИОН)", f"{pr} 🪙", c.from_user.id, target=seller, item=f"{NFT_DATA[k]['name']} #{sn}"))

# --- CHECKS ---
@dp.callback_query(F.data == "go_check")
async def check_start_cb(c: types.CallbackQuery, state: FSMContext):
    await c.message.answer("Сумма чека 🪙:"); await state.set_state(Form.check_amt)

@dp.message(Form.check_amt)
async def check_create(m: Message, state: FSMContext):
    if not m.text.isdigit(): return
    amt = int(m.text); cid = str(uuid.uuid4())[:12]
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute('SELECT coins FROM users WHERE user_id=?', (m.from_user.id,)) as cur:
            row = await cur.fetchone()
            if not row or row[0] < amt: return await m.answer("❌ Мало монет")
        await db.execute('UPDATE users SET coins = coins - ? WHERE user_id = ?', (amt, m.from_user.id))
        await db.execute('INSERT INTO checks (id, creator_id, amount) VALUES (?, ?, ?)', (cid, m.from_user.id, amt))
        await db.commit()
    bot_info = await bot.get_me()
    link = f"https://t.me/{bot_info.username}?start=act_{cid}"
    await m.answer(f"🎫 **Чек на {amt} 🪙**", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🚀 Активировать", url=link)]]))
    await state.clear()

# --- ADMIN PANEL ---
@dp.callback_query(F.data == "go_adm")
async def adm_m(c: types.CallbackQuery):
    if c.from_user.id != ADMIN_ID: return
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🙋‍♂️ Себе", callback_data="adm_t_me"), InlineKeyboardButton(text="🆔 По ID", callback_data="adm_t_id")],[InlineKeyboardButton(text="🔙", callback_data="to_main")]])
    await c.message.edit_text("👑 Панель управления", reply_markup=kb)

@dp.callback_query(F.data.startswith("adm_t_"))
async def adm_t(c: types.CallbackQuery, state: FSMContext):
    if "me" in c.data: 
        await state.update_data(target=c.from_user.id)
        await adm_act(c.message)
    else: 
        await c.message.answer("Введите ID пользователя:")
        await state.set_state(Form.adm_target)

@dp.message(Form.adm_target)
async def adm_t_v(m: Message, state: FSMContext):
    if not m.text.isdigit(): return
    await state.update_data(target=int(m.text)); await adm_act(m)

async def adm_act(m: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🪙 Монеты", callback_data="ag_c"), InlineKeyboardButton(text="🎁 NFT", callback_data="ag_n")]])
    await m.answer("Что выдать?", reply_markup=kb)

@dp.callback_query(F.data == "ag_c")
async def ag_c(c: types.CallbackQuery, state: FSMContext):
    await c.message.answer("Сколько монет?"); await state.set_state(Form.adm_coins)

@dp.message(Form.adm_coins)
async def ag_c_f(m: Message, state: FSMContext):
    if not m.text.isdigit(): return
    d = await state.get_data()
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('UPDATE users SET coins=coins+? WHERE user_id=?', (int(m.text), d['target']))
        await db.commit()
    await m.answer("✅ Готово!"); await state.clear()

@dp.callback_query(F.data == "ag_n")
async def ag_n(c: types.CallbackQuery):
    btns = [[InlineKeyboardButton(text=v['name'], callback_data=f"agn_{k}")] for k,v in NFT_DATA.items()]
    await c.message.answer("Выберите NFT:", reply_markup=InlineKeyboardMarkup(inline_keyboard=btns))

@dp.callback_query(F.data.startswith("agn_"))
async def ag_n_f(c: types.CallbackQuery, state: FSMContext):
    k = c.data.split("_")[1]; d = await state.get_data(); sn = random.randint(1000, 9999)
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('INSERT INTO inventory (user_id, item_key, serial_num) VALUES (?, ?, ?)', (d['target'], k, sn))
        await db.commit()
    await c.message.answer(f"✅ Выдан: {NFT_DATA[k]['name']} #{sn}"); await state.clear()

# --- MISC ---
@dp.callback_query(F.data == "to_main")
async def to_main(c: types.CallbackQuery, state: FSMContext):
    await state.clear(); kb = await get_main_kb(c.from_user.id, c.message.chat.type)
    await c.message.edit_text("💎 **NFT GIFT MARKET**", reply_markup=kb)

async def main():
    await init_db(); await set_commands()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
