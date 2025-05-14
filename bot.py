import telebot
from telebot.types import (InlineKeyboardMarkup, InlineKeyboardButton,
                           ReplyKeyboardMarkup, KeyboardButton)
import random
import string
import time
import re

TOKEN = "8152061099:AAE5k3IricRRWn-OuYnkkG8cJf1WS0utLps"
bot = telebot.TeleBot(TOKEN)

# ------------------ Механизм фильтрации нецензурных слов ------------------
bad_words = {
    "блин": 1, "Блин": 1, "бЛин": 1,
    "хрен": 1, "Хрен": 1,
    "дурак": 1, "Дурак": 1,
    "идиот": 2, "Идиот": 2,
    "кретин": 2, "Кретин": 2,
    "ублюдок": 3, "Ублюдок": 3,
    "сука": 4, "Сука": 4,
    "пиздец": 5, "Пиздец": 5,
    "хуй": 5, "Хуй": 5,
    "хуесос": 5, "Хуесос": 5
}

user_warnings = {}   # { user_id: warning_count }
chat_ban_until = {}  # { user_id: ban_end_timestamp }

def censor_text(text):
    max_severity = 0

    def replace_func(match):
        word = match.group(0)
        severity = bad_words.get(word, 0)
        nonlocal max_severity
        if severity > max_severity:
            max_severity = severity
        return word[0] + "*" * (len(word)-1)

    pattern = re.compile(r'\b(' + '|'.join(map(re.escape, bad_words.keys())) + r')\b', re.IGNORECASE)
    censored = pattern.sub(replace_func, text)
    return censored, max_severity

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

# -------------- Данные пользователей и состояний --------------
user_coins = {}           # Баланс пользователей (начальный баланс 0)
user_roles = {}           # Статусы пользователей ("user", "admin", "banned")
waiting_for_username = {} # Для ввода (например, "About user")
waiting_for_message = {}  # Для передачи сообщений (чат, ответы)
waiting_for_input = {}    # Для ввода данных (промокоды, настройки и т.д.)
waiting_for_transfer = {}             # Для перевода монет; ключ – sender_id, значение – dict с данными перевода
waiting_for_transfer_question = {}    # Для вопросов по переводу: ключ – получатель, значение – sender_id

admin_id = 2120919981     # ID администратора
promo_codes = {}          # Список активных промокодов

# -------------------- Главное меню --------------------
def get_main_menu(user_id):
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(KeyboardButton("Click"), KeyboardButton("Users online"), KeyboardButton("Balance"))
    markup.row(KeyboardButton("About your account"), KeyboardButton("About user"))
    markup.row(KeyboardButton("Chat"))
    markup.row(KeyboardButton("Create promo code"), KeyboardButton("Activate promo code"))
    markup.row(KeyboardButton("Transfer coins"))
    markup.row(KeyboardButton("Rules"))
    if user_id == admin_id:
        markup.row(KeyboardButton("Settings"))
    markup.row(KeyboardButton("Reset all"))
    return markup

# ---------------- Команда /start ----------------
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

# ---------------- Обработчик основного меню (Reply Keyboard) ----------------
@bot.message_handler(func=lambda message: message.text in [
    "Click", "Users online", "About your account", "About user", "Chat",
    "Create promo code", "Activate promo code", "Balance", "Rules", "Settings", "Reset all", "Transfer coins"
])
def main_menu_handler(message):
    user_id = message.chat.id
    text = message.text
    if user_roles.get(user_id) == "banned":
        bot.send_message(user_id, "Ты заблокирован и не можешь использовать бота.")
        return
    if text == "Click":
        user_coins[user_id]  += 1
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
        if user_id == admin_id:
            waiting_for_input[user_id] = "settings_pending"
            markup = InlineKeyboardMarkup()
            markup.row(InlineKeyboardButton("Повысить юзера до админа", callback_data="set_promote"))
            markup.row(InlineKeyboardButton("Понизить юзера до юзера", callback_data="set_demote"))
            markup.row(InlineKeyboardButton("Забанить юзера", callback_data="set_ban"))
            markup.row(InlineKeyboardButton("Разбанить юзера", callback_data="set_unban"))
            markup.row(InlineKeyboardButton("Reset coins", callback_data="set_reset"))
            markup.row(InlineKeyboardButton("Cancel", callback_data="cancel"))
            bot.send_message(user_id, "Выберите действие для администратора:", reply_markup=markup)
        else:
            bot.send_message(user_id, "У вас нет прав администратора.")
    elif text == "Transfer coins":
        markup = InlineKeyboardMarkup()
        for uid in user_roles:
            if uid != user_id and user_roles[uid] != "banned":
                markup.add(InlineKeyboardButton(f"{uid}", callback_data=f"transfer_{uid}"))
        markup.add(InlineKeyboardButton("Cancel", callback_data="cancel"))
        bot.send_message(user_id, "Выберите пользователя для перевода коинов:", reply_markup=markup)
    elif text == "Rules":
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("Exit", callback_data="exit_rules"))
        bot.send_message(user_id, "Правила:\n"
                                  "Оскорбления, плохие слова, маты – бан от 10 минут до 24 часов.\n"
                                  "Спам – бан (возможно перманентный).\n"
                                  "Нарушение правил бота-кликера – бан (на любое время).", reply_markup=markup)

# ---------------- Обработчик inline-кнопок ----------------
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.message.chat.id
    if user_roles.get(user_id) == "banned":
        bot.answer_callback_query(call.id, "Ты заблокирован и не можешь использовать бота.")
        return
    if call.data.startswith("chat_"):
        target_user = int(call.data.split("_")[1])
        waiting_for_message[user_id] = target_user
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("Cancel", callback_data="cancel"))
        bot.send_message(user_id, "Введите сообщение для пользователя:", reply_markup=markup)
    elif call.data.startswith("reply_"):
        sender_id = call.message.chat.id
        receiver_id = int(call.data.split("_")[1])
        waiting_for_message[sender_id] = receiver_id
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("Cancel", callback_data="cancel"))
        bot.send_message(sender_id, "Введите ответное сообщение:", reply_markup=markup)
    elif call.data.startswith("transfer_"):
        target_user = int(call.data.split("_")[1])
        waiting_for_transfer[user_id] = {"target": target_user}
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("Cancel", callback_data="cancel"))
        bot.send_message(user_id, "Введите количество коинов для перевода:", reply_markup=markup)
    elif call.data.startswith("transfer_send_"):
        sender_id = int(call.data.replace("transfer_send_", ""))
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
    elif call.data.startswith("transfer_accept_"):
        sender_id = int(call.data.replace("transfer_accept_", ""))
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
    elif call.data.startswith("transfer_decline_"):
        sender_id = int(call.data.replace("transfer_decline_", ""))
        if sender_id in waiting_for_transfer:
            bot.send_message(call.message.chat.id, "Вы отказались от перевода. Перевод отменён.")
            bot.send_message(sender_id, f"Пользователь {call.message.chat.id} отказался от вашего перевода.")
            waiting_for_transfer.pop(sender_id, None)
    elif call.data.startswith("transfer_question_"):
        sender_id = int(call.data.replace("transfer_question_", ""))
        waiting_for_transfer_question[call.message.chat.id] = sender_id
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("Cancel", callback_data="cancel"))
        bot.send_message(call.message.chat.id, "Введите ваш вопрос для отправителя:", reply_markup=markup)
    elif call.data == "exit_rules":
        bot.send_message(user_id, "Вы вышли из просмотра правил.")
    # Действия в настройках администратора
    elif call.data == "set_promote":
        waiting_for_input[user_id] = "settings_promote"
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("Cancel", callback_data="cancel"))
        bot.send_message(user_id, "Введите ID пользователя для повышения до админа:", reply_markup=markup)
    elif call.data == "set_demote":
        waiting_for_input[user_id] = "settings_demote"
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("Cancel", callback_data="cancel"))
        bot.send_message(user_id, "Введите ID пользователя для понижения до обычного юзера:", reply_markup=markup)
    elif call.data == "set_ban":
        # Запуск нового потока: сначала запрос ID, потом причину, потом длительность
        waiting_for_input[user_id] = "settings_ban_id"
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("Cancel", callback_data="cancel"))
        bot.send_message(user_id, "Введите ID пользователя для бана:", reply_markup=markup)
    elif call.data == "set_unban":
        waiting_for_input[user_id] = "settings_unban"
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("Cancel", callback_data="cancel"))
        bot.send_message(user_id, "Введите ID пользователя для разбанивания:", reply_markup=markup)
    elif call.data == "set_reset":
        waiting_for_input[user_id] = "settings_reset"
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("Cancel", callback_data="cancel"))
        bot.send_message(user_id, "Введите ID пользователя для сброса коинов:", reply_markup=markup)
    elif call.data == "cancel":
        waiting_for_input.pop(user_id, None)
        waiting_for_message.pop(user_id, None)
        waiting_for_transfer.pop(user_id, None)
        bot.send_message(user_id, "❌ Действие отменено.")

# ---------------- Обработка сообщений для чата с фильтрацией нецензурной лексики ----------------
@bot.message_handler(func=lambda message: message.chat.id in waiting_for_message)
def handle_chat_message(message):
    user_id = message.chat.id
    current_time = time.time()
    if user_id in chat_ban_until and current_time < chat_ban_until[user_id]:
        ban_remaining = int(chat_ban_until[user_id] - current_time)
        bot.send_message(user_id, f"Вы забанены в чате на {ban_remaining // 60} минут(ы).")
        waiting_for_message.pop(user_id, None)
        return
    original_text = message.text
    censored_text, severity = censor_text(original_text)
    if severity > 0:
        user_warnings[user_id] = user_warnings.get(user_id, 0) + 1
        warnings = user_warnings[user_id]
        bot.send_message(user_id, f"Ваше сообщение изменено из-за нецензурных выражений. Предупреждений: {warnings} из 3.")
        if warnings >= 3:
            ban_duration = get_ban_duration(severity)
            chat_ban_until[user_id] = time.time() + ban_duration
            bot.send_message(user_id, f"Вы получили бан в чате на {ban_duration // 60} минут(ы) за нецензурную лексику.")
            waiting_for_message.pop(user_id, None)
            return
    receiver_id = waiting_for_message[user_id]
    bot.send_message(receiver_id, f"Сообщение от {user_id}: {censored_text}",
                     reply_markup=InlineKeyboardMarkup().add(
                         InlineKeyboardButton("Ответить", callback_data=f"reply_{user_id}")
                     ))
    waiting_for_message.pop(user_id, None)

# ---------------- Обработка сообщений для ввода данных (промокоды, настройки и пр.) ----------------
@bot.message_handler(func=lambda message: message.chat.id in waiting_for_input)
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
            bot.send_message(user_id, "Пожалуйста, введите корректный идентификатор пользователя.")
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
            bot.send_message(user_id, "Пожалуйста, введите корректный идентификатор пользователя.")
        waiting_for_input.pop(user_id)
    # Новый многошаговый процесс для бана:
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
            bot.send_message(user_id, "Пожалуйста, введите корректный идентификатор пользователя.")
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
            bot.send_message(user_id, "Пожалуйста, введите число и единицу измерения, например, '10 минут'.")
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
            bot.send_message(user_id, "Пожалуйста, введите корректный идентификатор пользователя.")
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
            bot.send_message(user_id, "Пожалуйста, введите корректный идентификатор пользователя.")
        waiting_for_input.pop(user_id)

# ---------------- Обработка сообщений для ввода суммы при переводе коинов ----------------
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
        markup.row(InlineKeyboardButton("Отказаться от этого перевода и вернуть коины", callback_data=f"transfer_decline_{user_id}"))
        markup.row(InlineKeyboardButton("Задать вопрос ему", callback_data=f"transfer_question_{user_id}"),
                   InlineKeyboardButton("Принять перевод", callback_data=f"transfer_accept_{user_id}"))
        bot.send_message(target, f"Пользователь {sender_name} (ID: {user_id}) хочет перевести вам {amount} коинов.", reply_markup=markup)
        bot.send_message(user_id, "Запрос перевода отправлен.")
    except ValueError:
        bot.send_message(user_id, "Пожалуйста, введите число!")

# ---------------- Обработка сообщений для вопроса по переводу от получателя ----------------
@bot.message_handler(func=lambda message: message.chat.id in waiting_for_transfer_question)
def handle_transfer_question(message):
    receiver_id = message.chat.id
    sender_id = waiting_for_transfer_question[receiver_id]
    question = message.text
    bot.send_message(sender_id, f"Пользователь {receiver_id} задал вопрос относительно перевода: {question}")
    bot.send_message(receiver_id, "Ваш вопрос отправлен.")
    waiting_for_transfer_question.pop(receiver_id, None)

bot.polling()