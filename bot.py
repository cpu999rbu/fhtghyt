import telebot
from telebot.types import (InlineKeyboardMarkup, InlineKeyboardButton,
                           ReplyKeyboardMarkup, KeyboardButton)
import random
import string
import time
import threading
import json

TOKEN = "8152061099:AAE5k3IricRRWn-OuYnkkG8cJf1WS0utLps"
bot = telebot.TeleBot(TOKEN)

# ---------------------------------------------------------------------------------
# Вместо bad_words и censor_text – реализуем функцию для модерации.
def moderate_text(text):
    # Здесь можно добавить проверку текста на плохие слова и вернуть скорректированный текст.
    # Пока функция возвращает исходный текст и severity = 0.
    return text, 0

def get_ban_duration(severity):
    if severity == 1:
        return 10 * 60
    elif severity == 2:
        return 15 * 60
    elif severity == 3:
        return 30 * 60
    elif severity == 4:
        return 60 * 60
    elif severity == 5:
        return 3 * 60 * 60
    return 10 * 60

# ---------------------------------------------------------------------------------
# Данные пользователей и состояний
user_coins = {}           # Баланс пользователей (начальный баланс 0)
user_roles = {}           # Роли: "user", "admin", "banned"
waiting_for_username = {} # Состояния ввода (например, "About user")
waiting_for_message = {}  # Для отправки сообщений (чат, ответы)
waiting_for_input = {}    # Для ввода данных (промокоды, настройки и пр.)
waiting_for_transfer = {}             # Для перевода коинов (ключ – sender_id)
waiting_for_transfer_question = {}    # Для вопросов по переводу (ключ – получатель)

admin_id = 2120919981     # Основной ID администратора
promo_codes = {}          # Активные промокоды

# Новые глобальные переменные
click_value = 1         # Множитель для операции Click
last_click_time = {}      # Для антиспама кликов (user_id: время последнего клика)
transfer_block = {}       # Блокировка переводов для конкретного пользователя (user_id: bool)
autoclickers = {}         # Статус автокликера для пользователя (user_id: bool)
heavy_load = False        # Флаг симуляции высокой нагрузки

# ---------------------------------------------------------------------------------
# Функция для имитации нагрузки
def check_load(user_id):
    global heavy_load
    if heavy_load:
        bot.send_message(user_id, "Подождите!")
        time.sleep(1)

# Функции сохранения и загрузки данных (через JSON)
def save_data():
    data = {
        "user_coins": user_coins,
        "user_roles": user_roles,
        "promo_codes": promo_codes,
    }
    try:
        with open("data.json", "w") as f:
            json.dump(data, f)
        print("Данные сохранены")
    except Exception as e:
        print("Ошибка сохранения:", e)

def load_data():
    global user_coins, user_roles, promo_codes
    try:
        with open("data.json", "r") as f:
            data = json.load(f)
            user_coins = data.get("user_coins", {})
            user_roles = data.get("user_roles", {})
            promo_codes = data.get("promo_codes", {})
        print("Данные загружены")
    except Exception as e:
        print("Ошибка загрузки данных:", e)

# ---------------------------------------------------------------------------------
# Главное меню
def get_main_menu(user_id):
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(KeyboardButton("Click"), KeyboardButton("Users online"), KeyboardButton("Balance"))
    markup.row(KeyboardButton("About your account"), KeyboardButton("About user"))
    markup.row(KeyboardButton("Chat"))
    markup.row(KeyboardButton("Create promo code"), KeyboardButton("Activate promo code"))
    markup.row(KeyboardButton("Transfer coins"))
    markup.row(KeyboardButton("Rules"))
    if user_roles.get(user_id, "user") == "admin" or user_id == admin_id:
        markup.row(KeyboardButton("Settings"))
    markup.row(KeyboardButton("User Settings"))
    markup.row(KeyboardButton("Autoclicker (ON-OFF)"))
    markup.row(KeyboardButton("Reset all"))
    return markup

# ---------------------------------------------------------------------------------
# Команда /start
@bot.message_handler(commands=["start"])
def start(message):
    user_id = message.chat.id
    if user_id not in user_coins:
        user_coins[user_id] = 0
        user_roles[user_id] = "user"
    if user_roles[user_id] == "banned":
        bot.send_message(user_id, "Ты заблокирован и не можешь использовать бота.")
        return
    main_menu = get_main_menu(user_id)
    bot.send_message(user_id, "Выбери действие:", reply_markup=main_menu)

# ---------------------------------------------------------------------------------
# Обработчик основного меню (Reply Keyboard)
@bot.message_handler(func=lambda message: message.text in [
    "Click", "Users online", "About your account", "About user", "Chat",
    "Create promo code", "Activate promo code", "Balance", "Rules",
    "Settings", "Reset all", "Transfer coins", "User Settings", "Autoclicker (ON-OFF)"
])
def main_menu_handler(message):
    user_id = message.chat.id
    check_load(user_id)
    text = message.text
    if user_roles.get(user_id) == "banned":
        bot.send_message(user_id, "Ты заблокирован и не можешь использовать бота.")
        return

    if text == "Click":
        current_time = time.time()
        if user_id in last_click_time and current_time - last_click_time[user_id] < 1:
            bot.send_message(user_id, "Подождите!")
            return
        last_click_time[user_id] = current_time
        user_coins[user_id] += click_value
        bot.send_message(user_id, f"🟢 {message.from_user.first_name} нажал Click! Теперь у тебя {user_coins[user_id]} коинов.")
    elif text == "Users online":
        online_users = len([uid for uid in user_roles if user_roles[uid] != "banned"])
        bot.send_message(user_id, f"Сейчас онлайн: {online_users} пользователей.")
    elif text == "About your account":
        bot.send_message(user_id, f"Твой ID: {user_id}\nКоины: {user_coins[user_id]}\nСтатус: {user_roles[user_id]}")
    elif text == "Balance":
        bot.send_message(user_id, f"Твой баланс: {user_coins[user_id]} коинов")
    elif text == "About user":
        waiting_for_username[user_id] = "info"
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("Cancel", callback_data="cancel"))
        bot.send_message(user_id, "Введите username пользователя:", reply_markup=markup)
    elif text == "Reset all":
        user_coins[user_id] = 0
        bot.send_message(user_id, "🔄 Все коины сброшены!")
    elif text == "Chat":
        markup = InlineKeyboardMarkup()
        for uid in user_roles:
            if user_roles[uid] != "banned":
                markup.add(InlineKeyboardButton(f"{uid}", callback_data=f"chat_{uid}"))
        markup.add(InlineKeyboardButton("Cancel", callback_data="cancel"))
        bot.send_message(user_id, "Выбери пользователя для отправки сообщения:", reply_markup=markup)
    elif text == "Create promo code":
        waiting_for_input[user_id] = "coins"
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("Cancel", callback_data="cancel"))
        bot.send_message(user_id, "Введите количество коинов, которые будут списаны с вашего баланса:", reply_markup=markup)
    elif text == "Activate promo code":
        waiting_for_input[user_id] = "promo_code"
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("Cancel", callback_data="cancel"))
        bot.send_message(user_id, "Введите промокод для активации:", reply_markup=markup)
    elif text == "Settings":
        if user_roles.get(user_id) == "admin" or user_id == admin_id:
            waiting_for_input[user_id] = "settings_pending"
            markup = InlineKeyboardMarkup()
            markup.row(InlineKeyboardButton("Повысить юзера до админа", callback_data="set_promote"))
            markup.row(InlineKeyboardButton("Понизить юзера до юзера", callback_data="set_demote"))
            markup.row(InlineKeyboardButton("Забанить юзера", callback_data="set_ban"))
            markup.row(InlineKeyboardButton("Разбанить юзера", callback_data="set_unban"))
            markup.row(InlineKeyboardButton("Reset coins", callback_data="set_reset"))
            markup.row(InlineKeyboardButton("Get User Info", callback_data="get_user_info"))
            markup.row(InlineKeyboardButton("Send message", callback_data="send_message"))
            markup.row(InlineKeyboardButton("Save data", callback_data="save_data"),
                       InlineKeyboardButton("Load data", callback_data="load_data"))
            markup.row(InlineKeyboardButton("Cancel", callback_data="cancel"))
            bot.send_message(user_id, "Выберите действие для администратора:", reply_markup=markup)
        else:
            bot.send_message(user_id, "У вас нет прав администратора.")
    elif text == "Transfer coins":
        markup = InlineKeyboardMarkup()
        for uid in user_roles:
            if uid != user_id and user_roles[uid] != "banned":
                if transfer_block.get(uid, False):
                    continue
                markup.add(InlineKeyboardButton(f"{uid}", callback_data=f"transfer_{uid}"))
        markup.add(InlineKeyboardButton("Cancel", callback_data="cancel"))
        bot.send_message(user_id, "Выберите пользователя для перевода коинов:", reply_markup=markup)
    elif text == "User Settings":
        markup = InlineKeyboardMarkup()
        markup.row(InlineKeyboardButton("Set click", callback_data="set_click"))
        markup.row(InlineKeyboardButton("Block transfer for all", callback_data="block_transfer"))
        markup.row(InlineKeyboardButton("Unblock transfer for all", callback_data="unblock_transfer"))
        markup.row(InlineKeyboardButton("Cancel", callback_data="cancel"))
        bot.send_message(user_id, "Выберите действие:", reply_markup=markup)
    elif text == "Autoclicker (ON-OFF)":
        if autoclickers.get(user_id, False):
            autoclickers[user_id] = False
            bot.send_message(user_id, "Автокликер выключен.")
        else:
            autoclickers[user_id] = True
            bot.send_message(user_id, "Автокликер включен.")
            threading.Thread(target=autoclicker_thread, args=(user_id,), daemon=True).start()

# Фоновая функция автокликера для пользователя
def autoclicker_thread(user_id):
    while autoclickers.get(user_id, False):
        time.sleep(0.1)
        user_coins[user_id] += 1
        try:
            bot.send_message(user_id, f"Автокликер: +1 коин, теперь у тебя {user_coins[user_id]} коинов.")
        except Exception as e:
            print("Ошибка в автокликере:", e)

# ---------------------------------------------------------------------------------
# Обработчик inline‑кнопок
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.message.chat.id
    check_load(user_id)
    if user_roles.get(user_id) == "banned":
        bot.answer_callback_query(call.id, "Ты заблокирован и не можешь использовать бота.")
        return
    data = call.data

    if data.startswith("chat_"):
        target_user = int(data.split("_")[1])
        waiting_for_message[user_id] = target_user
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("Cancel", callback_data="cancel"))
        bot.send_message(user_id, "Введите сообщение для пользователя:", reply_markup=markup)
    elif data.startswith("reply_"):
        sender_id = call.message.chat.id
        receiver_id = int(data.split("_")[1])
        waiting_for_message[sender_id] = receiver_id
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("Cancel", callback_data="cancel"))
        bot.send_message(sender_id, "Введите ответное сообщение:", reply_markup=markup)
    elif data.startswith("transfer_") and not data.startswith("transfer_send") and not data.startswith("transfer_accept") and not data.startswith("transfer_decline") and not data.startswith("transfer_question"):
        target_user = int(data.split("_")[1])
        waiting_for_transfer[user_id] = {"target": target_user}
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("Cancel", callback_data="cancel"))
        bot.send_message(user_id, "Введите количество коинов для перевода:", reply_markup=markup)
    elif data.startswith("transfer_send_"):
        sender_id = int(data.replace("transfer_send_", ""))
        if sender_id in waiting_for_transfer:
            req = waiting_for_transfer[sender_id]
            if req.get("target") == call.message.chat.id:
                amount = req.get("amount", 0)
                if user_coins.get(sender_id, 0) >= amount:
                    user_coins[sender_id] -= amount
                    user_coins[call.message.chat.id] += amount
                    bot.send_message(call.message.chat.id, f"Перевод выполнен. Вам переведено {amount} коинов.")
                    bot.send_message(sender_id, f"Ваш перевод в размере {amount} коинов принят пользователем {call.message.chat.id}.")
                else:
                    bot.send_message(call.message.chat.id, "У отправителя недостаточно коинов для перевода.")
            else:
                bot.send_message(call.message.chat.id, "Ошибка: вы не являетесь выбранным получателем этого перевода.")
            waiting_for_transfer.pop(sender_id, None)
    elif data.startswith("transfer_accept_"):
        sender_id = int(data.replace("transfer_accept_", ""))
        if sender_id in waiting_for_transfer:
            req = waiting_for_transfer[sender_id]
            if req.get("target") == call.message.chat.id:
                amount = req.get("amount", 0)
                if user_coins.get(sender_id, 0) >= amount:
                    user_coins[sender_id] -= amount
                    user_coins[call.message.chat.id] += amount
                    bot.send_message(call.message.chat.id, f"Перевод выполнен. Вам переведено {amount} коинов.")
                    bot.send_message(sender_id, f"Ваш перевод в размере {amount} коинов принят пользователем {call.message.chat.id}.")
                else:
                    bot.send_message(call.message.chat.id, "У отправителя недостаточно коинов для перевода.")
            else:
                bot.send_message(call.message.chat.id, "Ошибка: вы не являетесь выбранным получателем этого перевода.")
            waiting_for_transfer.pop(sender_id, None)
    elif data.startswith("transfer_decline_"):
        sender_id = int(data.replace("transfer_decline_", ""))
        if sender_id in waiting_for_transfer:
            bot.send_message(call.message.chat.id, "Вы отказались от перевода. Перевод отменён.")
            bot.send_message(sender_id, f"Пользователь {call.message.chat.id} отказался от вашего перевода.")
            waiting_for_transfer.pop(sender_id, None)
    elif data.startswith("transfer_question_"):
        sender_id = int(data.replace("transfer_question_", ""))
        waiting_for_transfer_question[call.message.chat.id] = sender_id
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("Cancel", callback_data="cancel"))
        bot.send_message(call.message.chat.id, "Введите ваш вопрос для отправителя:", reply_markup=markup)
    elif data == "exit_rules":
        bot.send_message(user_id, "Вы вышли из просмотра правил.")
    # Действия в настройках администратора
    elif data == "set_promote":
        waiting_for_input[user_id] = "settings_promote"
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("Cancel", callback_data="cancel"))
        bot.send_message(user_id, "Введите ID пользователя для повышения до админа:", reply_markup=markup)
    elif data == "set_demote":
        waiting_for_input[user_id] = "settings_demote"
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("Cancel", callback_data="cancel"))
        bot.send_message(user_id, "Введите ID пользователя для понижения до обычного юзера:", reply_markup=markup)
    elif data == "set_ban":
        waiting_for_input[user_id] = "settings_ban_id"
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("Cancel", callback_data="cancel"))
        bot.send_message(user_id, "Введите ID пользователя для бана:", reply_markup=markup)
    elif data == "set_unban":
        waiting_for_input[user_id] = "settings_unban"
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("Cancel", callback_data="cancel"))
        bot.send_message(user_id, "Введите ID пользователя для разбанивания:", reply_markup=markup)
    elif data == "set_reset":
        waiting_for_input[user_id] = "settings_reset"
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("Cancel", callback_data="cancel"))
        bot.send_message(user_id, "Введите ID пользователя для сброса коинов:", reply_markup=markup)
    # Новые действия для администратора
    elif data == "get_user_info":
        markup = InlineKeyboardMarkup()
        for uid in user_coins:
            markup.add(InlineKeyboardButton(f"User {uid}", callback_data=f"user_info_{uid}"))
        markup.add(InlineKeyboardButton("Cancel", callback_data="cancel"))
        bot.send_message(user_id, "Выберите пользователя:", reply_markup=markup)
    elif data.startswith("user_info_"):
        target = int(data.replace("user_info_", ""))
        info = f"ID: {target}\nКоины: {user_coins.get(target, 0)}\nСтатус: {user_roles.get(target, 'user')}"
        bot.send_message(user_id, info)
    elif data == "send_message":
        markup = InlineKeyboardMarkup()
        for uid in user_coins:
            markup.add(InlineKeyboardButton(f"User {uid}", callback_data=f"admin_msg_{uid}"))
        markup.add(InlineKeyboardButton("Cancel", callback_data="cancel"))
        bot.send_message(user_id, "Выберите пользователя для отправки сообщения:", reply_markup=markup)
    elif data.startswith("admin_msg_"):
        target = int(data.replace("admin_msg_", ""))
        waiting_for_input[user_id] = ("admin_send_message", target)
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("Cancel", callback_data="cancel"))
        bot.send_message(user_id, "Введите сообщение для отправки:", reply_markup=markup)
    elif data == "save_data":
        save_data()
        bot.send_message(user_id, "Данные сохранены.")
    elif data == "load_data":
        load_data()
        bot.send_message(user_id, "Данные загружены.")
    # Действия в настройках пользователя (User Settings)
    elif data == "set_click":
        waiting_for_input[user_id] = "set_click"
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("Cancel", callback_data="cancel"))
        bot.send_message(user_id, "Поставь значение клика (от 0.5 до 2):", reply_markup=markup)
    elif data == "block_transfer":
        transfer_block[user_id] = True
        bot.send_message(user_id, "Переводы для вас заблокированы.")
    elif data == "unblock_transfer":
        transfer_block[user_id] = False
        bot.send_message(user_id, "Переводы для вас разблокированы.")
    elif data == "cancel":
        waiting_for_input.pop(user_id, None)
        waiting_for_message.pop(user_id, None)
        waiting_for_transfer.pop(user_id, None)
        bot.send_message(user_id, "❌ Действие отменено.")

# ---------------------------------------------------------------------------------
# Обработка сообщений для чата (поддержка текстовых и файловых сообщений)
@bot.message_handler(func=lambda message: message.chat.id in waiting_for_message,
                     content_types=["text", "photo", "video", "audio", "document", "voice", "sticker"])
def handle_chat_message(message):
    user_id = message.chat.id
    current_time = time.time()
    if user_id in chat_ban_until and current_time < chat_ban_until[user_id]:
        ban_remaining = int(chat_ban_until[user_id] - current_time)
        bot.send_message(user_id, f"Вы забанены в чате на {ban_remaining // 60} минут(ы).")
        waiting_for_message.pop(user_id, None)
        return
    target_id = waiting_for_message[user_id]
    if message.content_type == "text":
        original_text = message.text
        moderated_text, severity = moderate_text(original_text)
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("Ответить", callback_data=f"reply_{user_id}"))
        bot.send_message(target_id, f"Сообщение от {user_id}: {moderated_text}", reply_markup=markup)
    else:
        try:
            bot.forward_message(target_id, message.chat.id, message.message_id)
        except Exception as e:
            bot.send_message(user_id, f"Ошибка пересылки файла: {e}")
    waiting_for_message.pop(user_id, None)

# ---------------------------------------------------------------------------------
# Обработка сообщений для ввода (промокоды, настройки и пр.)
@bot.message_handler(func=lambda message: message.chat.id in waiting_for_input, content_types=["text"])
def handle_input(message):
    user_id = message.chat.id
    action = waiting_for_input[user_id]
    user_input = message.text
    # Обработка промокодов
    if action == "coins":
        try:
            coins = int(user_input)
            if coins > user_coins[user_id]:
                bot.send_message(user_id, "Недостаточно коинов для создания промокода!")
                return
            waiting_for_input[user_id] = ("users", coins)
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("Cancel", callback_data="cancel"))
            bot.send_message(user_id, "Введите количество пользователей, которые смогут активировать промокод:", reply_markup=markup)
        except ValueError:
            bot.send_message(user_id, "Пожалуйста, введите число!")
    elif isinstance(action, tuple) and action[0] == "users":
        try:
            users_limit = int(user_input)
            waiting_for_input[user_id] = ("expiration", action[1], users_limit)
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("Cancel", callback_data="cancel"))
            bot.send_message(user_id, "Введите время действия промокода в минутах:", reply_markup=markup)
        except ValueError:
            bot.send_message(user_id, "Пожалуйста, введите число!")
    elif isinstance(action, tuple) and action[0] == "expiration":
        try:
            expiration_minutes = int(user_input)
            expiration_time = time.time() + expiration_minutes * 60
            coins_value = action[1]
            users_limit = action[2]
            promo_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
            promo_codes[promo_code] = {
                "coins": coins_value,
                "limit": users_limit,
                "creator": user_id,
                "expires": expiration_time
            }
            user_coins[user_id] -= coins_value * users_limit
            bot.send_message(user_id, f"Промокод создан!\n**Код:** {promo_code}\n**Лимит:** {users_limit} пользователей\n"
                                      f"**Коины:** {coins_value} на каждого\n**Срок действия:** {expiration_minutes} минут.")
            waiting_for_input.pop(user_id)
        except ValueError:
            bot.send_message(user_id, "Пожалуйста, введите число!")
    elif action == "promo_code":
        if user_input in promo_codes:
            promo = promo_codes[user_input]
            # Проверка: нельзя активировать свой промокод
            if promo["creator"] == user_id:
                bot.send_message(user_id, "Вы не можете активировать свой промокод!")
                waiting_for_input.pop(user_id)
                return
            current_time = time.time()
            if current_time > promo["expires"]:
                bot.send_message(user_id, "Промокод истёк.")
                promo_codes.pop(user_input)
                waiting_for_input.pop(user_id)
                return
            if promo["limit"] > 0 and user_coins[promo["creator"]] >= promo["coins"]:
                user_coins[user_id] += promo["coins"]
                user_coins[promo["creator"]] -= promo["coins"]
                promo["limit"] -= 1
                bot.send_message(user_id, f"Промокод активирован! Получено {promo['coins']} коинов.")
                bot.send_message(promo["creator"], f"Пользователь {user_id} активировал ваш промокод. Осталось активаций: {promo['limit']}.")
                if promo["limit"] == 0:
                    promo_codes.pop(user_input)
            else:
                bot.send_message(user_id, "Промокод недействителен или закончились активации.")
        else:
            bot.send_message(user_id, "Промокод не найден.")
        waiting_for_input.pop(user_id)
    # Обработка настроек администратора
    elif action == "settings_promote":
        try:
            target = int(user_input)
            if target not in user_coins:
                bot.send_message(user_id, "Пользователь не найден.")
                waiting_for_input.pop(user_id)
                return
            user_roles[target] = "admin"
            bot.send_message(user_id, f"Пользователь {target} повышен до админа.")
        except ValueError:
            bot.send_message(user_id, "Пожалуйста, введите корректный ID пользователя.")
        waiting_for_input.pop(user_id)
    elif action == "settings_demote":
        try:
            target = int(user_input)
            if target not in user_coins:
                bot.send_message(user_id, "Пользователь не найден.")
                waiting_for_input.pop(user_id)
                return
            user_roles[target] = "user"
            bot.send_message(user_id, f"Пользователь {target} понижен до обычного юзера.")
        except ValueError:
            bot.send_message(user_id, "Пожалуйста, введите корректный ID пользователя.")
        waiting_for_input.pop(user_id)
    elif action == "settings_ban_id":
        try:
            target = int(user_input)
            if target not in user_coins:
                bot.send_message(user_id, "Пользователь не найден.")
                waiting_for_input.pop(user_id)
                return
            waiting_for_input[user_id] = ("settings_ban", target)
            bot.send_message(user_id, "Введите причину бана:")
        except ValueError:
            bot.send_message(user_id, "Пожалуйста, введите корректный ID пользователя.")
    elif isinstance(action, tuple) and action[0] == "settings_ban" and len(action) == 2:
        target = action[1]
        reason = user_input
        waiting_for_input[user_id] = ("settings_ban", target, reason)
        bot.send_message(user_id, "Введите длительность бана (например, '10 минут', '2 часа', '1 день'):")
    elif isinstance(action, tuple) and action[0] == "settings_ban" and len(action) == 3:
        target = action[1]
        reason = action[2]
        parts = user_input.split()
        if len(parts) < 2:
            bot.send_message(user_id, "Пожалуйста, введите число и единицу (например, '10 минут').")
            return
        try:
            number = int(parts[0])
        except ValueError:
            bot.send_message(user_id, "Пожалуйста, введите корректное число.")
            return
        unit = parts[1].lower()
        if unit.startswith("минут"):
            duration = number * 60
        elif unit.startswith("час"):
            duration = number * 3600
        elif unit.startswith("день"):
            duration = number * 86400
        elif unit.startswith("месяц"):
            duration = number * 30 * 86400
        elif unit.startswith("год"):
            duration = number * 365 * 86400
        else:
            duration = number * 60
        user_roles[target] = "banned"
        chat_ban_until[target] = time.time() + duration
        duration_text = f"{number} {unit}"
        bot.send_message(target, f"Вы забанены за '{reason}' на {duration_text}.")
        bot.send_message(user_id, f"Пользователь {target} забанен за '{reason}' на {duration_text}.")
        waiting_for_input.pop(user_id)
    elif action == "settings_unban":
        try:
            target = int(user_input)
            if target not in user_coins:
                bot.send_message(user_id, "Пользователь не найден.")
                waiting_for_input.pop(user_id)
                return
            user_roles[target] = "user"
            bot.send_message(user_id, f"Пользователь {target} разблокирован.")
        except ValueError:
            bot.send_message(user_id, "Пожалуйста, введите корректный ID пользователя.")
        waiting_for_input.pop(user_id)
    elif action == "settings_reset":
        try:
            target = int(user_input)
            if target not in user_coins:
                bot.send_message(user_id, "Пользователь не найден.")
                waiting_for_input.pop(user_id)
                return
            user_coins[target] = 0
            bot.send_message(user_id, f"Коины пользователя {target} сброшены.")
        except ValueError:
            bot.send_message(user_id, "Пожалуйста, введите корректный ID пользователя.")
        waiting_for_input.pop(user_id)
    # Обработка настроек пользователя (User Settings)
    elif action == "set_click":
        try:
            new_value = float(user_input)
            if 0.5 <= new_value <= 2:
                global click_value
                click_value = new_value
                bot.send_message(user_id, f"Значение клика изменено на {click_value}.")
            else:
                bot.send_message(user_id, "Введенное значение должно быть от 0.5 до 2.")
        except ValueError:
            bot.send_message(user_id, "Пожалуйста, введите число!")
        waiting_for_input.pop(user_id)
    # Обработка админского сообщения
    elif isinstance(action, tuple) and action[0] == "admin_send_message":
        target = action[1]
        text_to_send = user_input
        markup = InlineKeyboardMarkup()
        markup.row(InlineKeyboardButton("Ответить", callback_data=f"admin_reply_{user_id}_{target}"))
        markup.row(InlineKeyboardButton("Поставить статус (Прочитано)", callback_data=f"admin_status_{user_id}_{target}"))
        markup.row(InlineKeyboardButton("Игнор", callback_data=f"admin_ignore_{user_id}_{target}"))
        bot.send_message(target, f"Вы получили от админа ({user_id}) сообщение:\n{text_to_send}", reply_markup=markup)
        bot.send_message(user_id, "Сообщение отправлено.")
        waiting_for_input.pop(user_id)

# ---------------------------------------------------------------------------------
# Обработка сообщений для перевода коинов
@bot.message_handler(func=lambda message: message.chat.id in waiting_for_transfer and "amount" not in waiting_for_transfer[message.chat.id])
def handle_transfer_amount(message):
    user_id = message.chat.id
    try:
        amount = int(message.text)
        if amount <= 0:
            bot.send_message(user_id, "Введите положительное число!")
            return
        if user_coins[user_id] < amount:
            bot.send_message(user_id, "У вас недостаточно коинов для перевода!")
            waiting_for_transfer.pop(user_id, None)
            return
        waiting_for_transfer[user_id]["amount"] = amount
        target = waiting_for_transfer[user_id]["target"]
        sender_name = message.from_user.first_name or str(user_id)
        markup = InlineKeyboardMarkup()
        markup.row(InlineKeyboardButton("Перевести ему коины", callback_data=f"transfer_send_{user_id}"))
        markup.row(InlineKeyboardButton("Отказаться от перевода и вернуть коины", callback_data=f"transfer_decline_{user_id}"))
        markup.row(InlineKeyboardButton("Задать вопрос ему", callback_data=f"transfer_question_{user_id}"),
                   InlineKeyboardButton("Принять перевод", callback_data=f"transfer_accept_{user_id}"))
        bot.send_message(target, f"Пользователь {sender_name} (ID: {user_id}) хочет перевести вам {amount} коинов.", reply_markup=markup)
        bot.send_message(user_id, "Запрос перевода отправлен.")
    except ValueError:
        bot.send_message(user_id, "Пожалуйста, введите число!")

# ---------------------------------------------------------------------------------
# Обработка сообщений для вопросов по переводу
@bot.message_handler(func=lambda message: message.chat.id in waiting_for_transfer_question, content_types=["text"])
def handle_transfer_question(message):
    receiver_id = message.chat.id
    sender_id = waiting_for_transfer_question[receiver_id]
    question = message.text
    bot.send_message(sender_id, f"Пользователь {receiver_id} задал вопрос относительно перевода: {question}")
    bot.send_message(receiver_id, "Ваш вопрос отправлен.")
    waiting_for_transfer_question.pop(receiver_id, None)

# ---------------------------------------------------------------------------------
bot.polling()
