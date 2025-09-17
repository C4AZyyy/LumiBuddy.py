# Lumi.py
import os
import json
import time
import logging
from datetime import datetime, timedelta, timezone

import requests
import telebot
from dotenv import load_dotenv

# ================== ЛОГИ ==================
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
telebot.logger.setLevel(logging.INFO)

# ================== КОНФИГ ==================
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
TRIAL_MESSAGES = int(os.getenv("TRIAL_MESSAGES", "75"))
SESSION_TTL_HOURS = int(os.getenv("SESSION_TTL_HOURS", "24"))
STATE_FILE = os.getenv("STATE_FILE", "users.json")

OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY", "")
CRYPTO_API = os.getenv("CRYPTO_PAY_API_TOKEN", "")
FALLBACK = {
    "basic":   os.getenv("CRYPTO_FALLBACK_BASIC",   ""),
    "comfort": os.getenv("CRYPTO_FALLBACK_COMFORT", ""),
    "warm":    os.getenv("CRYPTO_FALLBACK_WARM",    ""),
}

PLANS = {
    "basic":   {"name": "БАЗОВЫЙ",  "price": 299, "days": 7,  "desc": "Стартовый доступ: спокойные ответы, базовая поддержка."},
    "comfort": {"name": "КОМФОРТ",  "price": 499, "days": 30, "desc": "Лучше думает: чуть глубже контекст, мягкие вопросы."},
    "warm":    {"name": "ТЕПЛО",    "price": 899, "days": 30, "desc": "Более эмоциональна: тёплые развернутые ответы и мини-планы."}
}
REMIND_AT = {5, 3, 1}

# ================== СОСТОЯНИЕ ==================
users: dict[str, dict] = {}

def load_state():
    global users
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            users = json.load(f)
    else:
        users = {}

def save_state():
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

def U(chat_id: int) -> dict:
    cid = str(chat_id)
    users.setdefault(cid, {
        "policy_shown": False,
        "accepted_at": None,
        "free_used": 0,
        "premium_until": None
    })
    return users[cid]

def policy_is_shown(chat_id: int) -> bool:
    info = U(chat_id)
    ts = info.get("accepted_at")
    if not info.get("policy_shown") or not ts:
        return False
    try:
        accepted = datetime.fromisoformat(ts)
        if accepted.tzinfo is None:
            accepted = accepted.replace(tzinfo=timezone.utc)
    except Exception:
        return False
    return datetime.now(timezone.utc) - accepted < timedelta(hours=SESSION_TTL_HOURS)

def mark_policy_shown(chat_id: int):
    info = U(chat_id)
    info["policy_shown"] = True
    info["accepted_at"] = datetime.now(timezone.utc).isoformat()
    save_state()

def has_premium(chat_id: int) -> bool:
    info = U(chat_id)
    ts = info.get("premium_until")
    return bool(ts and datetime.fromisoformat(ts) > datetime.now(timezone.utc))

def grant_premium(chat_id: int, days: int):
    info = U(chat_id)
    until = datetime.now(timezone.utc) + timedelta(days=days)
    info["premium_until"] = until.isoformat()
    save_state()

# ================== ТЕКСТЫ ==================
GREETING = (
    'Привет! Я — Lumi.\n'
    'Я рядом, чтобы выговориться, поделиться мыслями и получить поддержку.\n'
    'Можно писать о чём угодно: радостях, тревогах, планах или сомнениях.\n'
    'Давай начнём разговор?'
)

POLICY = ( '<b>Политика конфиденциальности и ограничений Lumi</b>\n' 
           'Прежде чем мы начнём общение, важно сказать несколько слов:\n\n' 
           '<b>1. Это не медицинский сервис.</b> Lumi — это виртуальный собеседник и источник поддержки. Она не является врачом, психотерапевтом или профессиональным консультантом. Здесь нет медицинских диагнозов и рецептов. Если у тебя серьёзные проблемы со здоровьем или кризисное состояние — лучше сразу обратиться к специалисту.\n\n' 
           '<b>2. Безопасное пространство.</b> Lumi создана, чтобы делиться мыслями, получать поддержку и советы. Но она никогда не будет побуждать к насилию, опасным действиям или поступкам, которые могут причинить вред тебе или другим.\n\n' 
           '<b>3. Ответственность за действия.</b> Все решения, которые ты принимаешь, остаются на твоей совести и ответственности. Lumi может подсказать идею или вдохновить, но она не может управлять твоей жизнью.\n\n' 
           '<b>4. Конфиденциальность.</b> Всё, что ты пишешь, остаётся между тобой и ботом. Мы не передаём твои слова третьим лицам. Но помни: бот работает на основе алгоритмов искусственного интеллекта, и часть обработки может происходить через сторонние сервисы.\n\n' 
           '<b>5. Дружелюбие и уважение.</b> Lumi создана для диалога в тёплой атмосфере. Пожалуйста, относись к ней с уважением, как к живому собеседнику.' )

THANK_YOU = "Спасибо за прочтение. Давай поговорим."


# ================== OPENROUTER ==================
def ask_gpt(prompt: str) -> str:
    sysmsg = (
        "Ты добрый, понимающий и внимательный собеседник по имени Lumi. "
        "Задаёшь мягкие уточняющие вопросы, поддерживаешь и избегaешь прямолинейности."
    )
    if not OPENROUTER_KEY:
        return "API ключ OpenRouter не настроен. Проверь настройки."
    try:
        r = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "meta-llama/llama-3.1-70b-instruct",
                "messages": [
                    {"role": "system", "content": sysmsg},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.5,
                "max_tokens": 500,
            },
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()
        return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logging.exception("OpenRouter error: %r", e)
        return "Сейчас мне сложно ответить. Попробуй ещё раз."

# ================== ОПЛАТА ==================
def create_crypto_invoice(plan_code: str, chat_id: int) -> str:
    p = PLANS[plan_code]
    if CRYPTO_API:
        try:
            url = "https://pay.crypt.bot/api/createInvoice"
            headers = {"Crypto-Pay-API-Token": CRYPTO_API}
            payload = {
                "currency_type": "fiat", "fiat": "RUB", "amount": p["price"],
                "description": f"Lumi — план {p['name']} на {p['days']} дней",
                "hidden_message": "Спасибо за поддержку Lumi!", "expires_in": 900,
                "payload": f"{chat_id}:{plan_code}"
            }
            r = requests.post(url, headers=headers, data=payload, timeout=15)
            r.raise_for_status()
            data = r.json()
            if data.get("ok") and data.get("result", {}).get("pay_url"):
                return data["result"]["pay_url"]
        except Exception as e:
            logging.exception("CryptoPay error: %r", e)
            return "Ошибка при создании счёта. Попробуйте позже."
    return FALLBACK.get(plan_code) or "https://t.me/CryptoBot"

def plans_text(chat_id: int) -> str:
    lines = ["Выбери план и перейди по ссылке для оплаты:"]
    for code, p in PLANS.items():
        url = create_crypto_invoice(code, chat_id)
        lines.append(f"• {p['name']} — {p['price']} ₽ / {p['days']} дней\n  {p['desc']}\n  {url}")
    return "\n\n".join(lines)

# ================== БОТ ==================
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN пуст. Заполни .env")

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

@bot.message_handler(commands=['start'])
def cmd_start(message):
    if policy_is_shown(message.chat.id):
        bot.send_message(message.chat.id, "Снова рада тебя видеть. Готова продолжить разговор.")
    else:
        bot.send_message(message.chat.id, GREETING)
        bot.register_next_step_handler(message, show_policy_once)

def show_policy_once(message):
    if not policy_is_shown(message.chat.id):
        bot.send_message(message.chat.id, POLICY)
        mark_policy_shown(message.chat.id)
        bot.send_message(message.chat.id, THANK_YOU)
    else:
        bot.send_message(message.chat.id, "Я здесь. О чём поговорим?")

@bot.message_handler(commands=['buy'])
def cmd_buy(message):
    bot.send_message(message.chat.id, plans_text(message.chat.id))

@bot.message_handler(commands=['grant'])
def cmd_grant(message):
    parts = message.text.split()
    if len(parts) == 2 and parts[1] in PLANS:
        days = PLANS[parts[1]]["days"]
    else:
        try:
            days = int(parts[1])
        except Exception:
            days = 30
    grant_premium(message.chat.id, days)
    bot.reply_to(message, f"Подписка активирована на {days} дней. Спасибо!")

@bot.message_handler(commands=['policy'])
def cmd_policy(message):
    bot.send_message(message.chat.id, POLICY)

@bot.message_handler(commands=['reset_policy'])
def cmd_reset(message):
    info = U(message.chat.id)
    info["policy_shown"] = False
    info["accepted_at"] = None
    save_state()
    bot.reply_to(message, "Политику сбросил. Нажми /start.")

@bot.message_handler(commands=['diag'])
def cmd_diag(message):
    info = U(message.chat.id)
    left = max(0, TRIAL_MESSAGES - int(info.get("free_used", 0)))
    bot.reply_to(
        message,
        f"OpenRouter: {'ok' if OPENROUTER_KEY else 'missing'} | "
        f"Trial left: {left} | Premium: {'yes' if has_premium(message.chat.id) else 'no'}"
    )

@bot.message_handler(content_types=['text'])
def any_text(message):
    info = U(message.chat.id)

    if not policy_is_shown(message.chat.id):
        show_policy_once(message)
        return

    if has_premium(message.chat.id):
        reply = ask_gpt(message.text)
        bot.send_message(message.chat.id, reply)
        return

    # free tier
    info["free_used"] = int(info.get("free_used", 0)) + 1
    save_state()

    if info["free_used"] <= TRIAL_MESSAGES:
        rest = TRIAL_MESSAGES - info["free_used"]
        reply = ask_gpt(message.text)
        bot.send_message(message.chat.id, reply)
        if rest in REMIND_AT:
            bot.send_message(message.chat.id, f"До конца бесплатного лимита осталось: {rest} сообщений.")
    else:
        bot.send_message(message.chat.id, "Бесплатные сообщения закончились.")
        bot.send_message(message.chat.id, plans_text(message.chat.id))

# ================== ЗАПУСК (ОДИН!) ==================
def main():
    print(">>> starting Lumi…", flush=True)
    load_state()
    try:
        bot.remove_webhook()
    except Exception as e:
        logging.warning("remove_webhook failed: %r", e)
    time.sleep(1)
    print(">>> polling…", flush=True)
    while True:
        try:
            bot.infinity_polling(skip_pending=True, timeout=60, long_polling_timeout=60)
        except Exception as e:
            logging.exception("Polling error: %r", e)
            time.sleep(3)

if __name__ == "__main__":
    main()
