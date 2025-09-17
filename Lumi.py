# Lumi.py
import json
import logging
import os
import random
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

import requests
import telebot
from dotenv import load_dotenv
from telebot import types

# ================== ЛОГИ ==================
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
telebot.logger.setLevel(logging.INFO)

# ================== КОНФИГ ==================
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
TRIAL_MESSAGES = int(os.getenv("TRIAL_MESSAGES", "75"))
SESSION_TTL_HOURS = int(os.getenv("SESSION_TTL_HOURS", "24"))
STATE_FILE = os.getenv("STATE_FILE", "users.json")
DEFAULT_LANGUAGE = os.getenv("DEFAULT_LANGUAGE", "ru").lower()

WEBHOOK_URL = os.getenv("WEBHOOK_URL", "").strip()
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "").strip() or None
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST", "0.0.0.0")
WEBHOOK_PORT = int(os.getenv("WEBHOOK_PORT", "0") or 0)
WEBHOOK_PATH = os.getenv("WEBHOOK_PATH", f"/webhook/{BOT_TOKEN}")
WEBHOOK_SSL_CERT = os.getenv("WEBHOOK_SSL_CERT", "").strip() or None
WEBHOOK_SSL_KEY = os.getenv("WEBHOOK_SSL_KEY", "").strip() or None

OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.1-70b-instruct")
OPENROUTER_VISION_MODEL = os.getenv("OPENROUTER_VISION_MODEL", "")
OPENROUTER_TRANSCRIBE_MODEL = os.getenv("OPENROUTER_TRANSCRIBE_MODEL", "")
CRYPTO_API = os.getenv("CRYPTO_PAY_API_TOKEN", "")
FALLBACK = {
    "basic": os.getenv("CRYPTO_FALLBACK_BASIC", ""),
    "comfort": os.getenv("CRYPTO_FALLBACK_COMFORT", ""),
    "warm": os.getenv("CRYPTO_FALLBACK_WARM", ""),
}

PLANS = {
    "basic": {"name": "БАЗОВЫЙ", "price": 299, "days": 7,
              "desc": "Стартовый доступ: спокойные ответы, базовая поддержка."},
    "comfort": {"name": "КОМФОРТ", "price": 499, "days": 30,
                "desc": "Лучше думает: чуть глубже контекст, мягкие вопросы."},
    "warm": {"name": "ТЕПЛО", "price": 899, "days": 30,
             "desc": "Более эмоциональна: тёплые развернутые ответы и мини-планы."}
}
REMIND_AT = {5, 3, 1}
ALWAYS_PREMIUM = {c.strip() for c in os.getenv("PERMANENT_ACCESS", "").split(",") if c.strip()}

LANGUAGES: Dict[str, Dict[str, str]] = {
    "ru": {
        "name": "Русский",
        "greeting": (
            "Привет! Я — Lumi.\n"
            "Я рядом, чтобы выговориться, поделиться мыслями и получить поддержку.\n"
            "Можно писать о чём угодно: радостях, тревогах, планах или сомнениях.\n"
            "Давай начнём разговор?"
        ),
        "policy": (
            '<b>Политика конфиденциальности и ограничений Lumi</b>\n'
            'Прежде чем мы начнём общение, важно сказать несколько слов:\n\n'
            '<b>1. Это не медицинский сервис.</b> Lumi — это виртуальный собеседник и источник поддержки. Она не является врачом, психотерапевтом или профессиональным консультантом. Здесь нет медицинских диагнозов и рецептов. Если у тебя серьёзные проблемы со здоровьем или кризисное состояние — лучше сразу обратиться к специалисту.\n\n'
            '<b>2. Безопасное пространство.</b> Lumi создана, чтобы делиться мыслями, получать поддержку и советы. Но она никогда не будет побуждать к насилию, опасным действиям или поступкам, которые могут причинить вред тебе или другим.\n\n'
            '<b>3. Ответственность за действия.</b> Все решения, которые ты принимаешь, остаются на твоей совести и ответственности. Lumi может подсказать идею или вдохновить, но она не может управлять твоей жизнью.\n\n'
            '<b>4. Конфиденциальность.</b> Всё, что ты пишешь, остаётся между тобой и ботом. Мы не передаём твои слова третьим лицам. Но помни: бот работает на основе алгоритмов искусственного интеллекта, и часть обработки может происходить через сторонние сервисы.\n\n'
            '<b>5. Дружелюбие и уважение.</b> Lumi создана для диалога в тёплой атмосфере. Пожалуйста, относись к ней с уважением, как к живому собеседнику.'
        ),
        "thank_you": "Спасибо за прочтение. Давай поговорим.",
        "policy_repeat": "Я здесь. О чём поговорим?",
        "policy_again": "Снова рада тебя видеть. Готова продолжить разговор.",
        "policy_reset": "Политику сбросил. Нажми /start.",
        "plan_intro": "Выбери план и перейди по ссылке для оплаты:",
        "free_end": "Бесплатные сообщения закончились.",
        "remind": "До конца бесплатного лимита осталось: {rest} сообщений.",
        "ask_topic": "О чём поговорим?",
        "diagnostics": "OpenRouter: {router} | Trial left: {left} | Premium: {premium}",
        "insult": "Я слышу злость, но давай без оскорблений. Если хочешь поговорить серьёзно — я рядом.",
        "sensitive": "Я не могу поддерживать сценарии насилия или причинения вреда. Давай лучше поговорим о том, как ты себя чувствуешь и что тебя волнует.",
        "voice_prompt": "Я получила голосовое сообщение. Дай знать, если я вдруг что-то поняла не так: {text}",
        "voice_failed": "Пока не вышло разобрать голос. Можешь прислать текстом?",
        "photo_failed": "Мне не удалось разобрать фото. Расскажешь словами, что на нём?",
        "photo_prompt": "Я посмотрела на фотографию: {description}. Расскажи, что тебя волнует в связи с этим?",
        "photo_model": "Пользователь прислал фотографию. Описание: {description}.",
        "supportive": [
            "Я рядом и думаю о тебе. Помни, что у тебя уже есть опыт переживать сложные времена.",
            "Сегодня можно сделать что-то доброе для себя. Даже маленький шаг — уже забота о себе.",
            "Ты имеешь право на свои чувства. Давай подумаем, что могло бы принести тебе немного тепла сегодня.",
        ],
        "supportive_intro": "Небольшое напоминание: ты не один. Вот тёплая мысль на сегодня:\n{phrase}",
        "language_prompt": "Привет! Выбери язык, на котором будем общаться.",
        "language_confirm": "Мы будем говорить на русском. Расскажи, что у тебя на душе?",
        "support_error": "Не удалось отправить тёплую фразу, но я всё равно рядом.",
        "trial_left": "До конца бесплатного лимита осталось: {rest} сообщений.",
        "buy_prompt": "Выбери план и перейди по ссылке для оплаты:",
        "premium_granted": "Подписка активирована на {days} дней. Спасибо!",
        "grant_permanent": "Для тебя включён постоянный доступ к улучшенной версии.",
    },
    "en": {
        "name": "English",
        "greeting": (
            "Hi! I'm Lumi.\n"
            "I'm here to listen, support you and share calm thoughts.\n"
            "You can tell me about anything: joys, worries, plans or doubts.\n"
            "Shall we start our conversation?"
        ),
        "policy": (
            '<b>Lumi privacy & safety</b>\n'
            'Before we talk, here are a few important points:\n\n'
            '<b>1. Not a medical service.</b> Lumi is a virtual companion and source of emotional support. She is not a doctor, therapist or licensed counsellor. There are no diagnoses or prescriptions here. If you face a medical emergency or crisis, please reach out to a professional immediately.\n\n'
            '<b>2. Safe space.</b> Lumi is designed for sharing feelings, gaining support and gentle ideas. She will never encourage violence, dangerous actions or anything that could hurt you or others.\n\n'
            '<b>3. Your responsibility.</b> Every decision you make remains yours. Lumi may offer ideas, yet cannot run your life.\n\n'
            '<b>4. Privacy.</b> What you share stays between you and the bot. We do not pass it to third parties. Remember: the bot relies on AI services and some processing may happen via external providers.\n\n'
            '<b>5. Kindness.</b> Lumi is built for a gentle dialogue. Please treat her with respect, like a caring human companion.'
        ),
        "thank_you": "Thanks for reading. Let's talk.",
        "policy_repeat": "I'm here again. What would you like to talk about?",
        "policy_again": "Happy to see you again. Ready to continue our chat.",
        "policy_reset": "Policy reset. Tap /start.",
        "plan_intro": "Choose a plan and follow the link to pay:",
        "free_end": "The free messages are over.",
        "remind": "You have {rest} messages left in the free limit.",
        "ask_topic": "What would you like to talk about?",
        "diagnostics": "OpenRouter: {router} | Trial left: {left} | Premium: {premium}",
        "insult": "I can hear the anger, yet I won't accept insults. If you want a real talk, I'm here.",
        "sensitive": "I can't help with violent or harmful scenarios. Let's focus on what you feel and need right now.",
        "voice_prompt": "I heard your voice message. Let me know if I misunderstood anything: {text}",
        "voice_failed": "I couldn't transcribe the voice message. Could you send it as text?",
        "photo_failed": "I couldn't interpret the photo. Could you describe it in words?",
        "photo_prompt": "I looked at the picture: {description}. Would you tell me what matters to you about it?",
        "photo_model": "The user sent a photo. Description: {description}.",
        "supportive": [
            "I'm thinking of you today. You already know how to get through hard times.",
            "Maybe offer yourself a small act of care today. Even a tiny step counts.",
            "Your feelings matter. Let's explore what could bring you a bit of warmth right now.",
        ],
        "supportive_intro": "Just a gentle reminder: you're not alone. Here is a warm thought for today:\n{phrase}",
        "language_prompt": "Hi! Please choose the language for our chat.",
        "language_confirm": "We'll speak English. What is on your mind?",
        "support_error": "I couldn't send the daily note, but I'm still with you.",
        "trial_left": "You have {rest} messages left in your free limit.",
        "buy_prompt": "Choose a plan and follow the link to pay:",
        "premium_granted": "Premium is active for {days} days. Thank you!",
        "grant_permanent": "You have permanent access to the enhanced experience.",
    },
}
+559
-81

# Lumi.py
import os
import json
import time
import logging
import os
import random
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

import requests
import telebot
from dotenv import load_dotenv
from telebot import types

# ================== ЛОГИ ==================
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
telebot.logger.setLevel(logging.INFO)

# ================== КОНФИГ ==================
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
TRIAL_MESSAGES = int(os.getenv("TRIAL_MESSAGES", "75"))
SESSION_TTL_HOURS = int(os.getenv("SESSION_TTL_HOURS", "24"))
STATE_FILE = os.getenv("STATE_FILE", "users.json")
DEFAULT_LANGUAGE = os.getenv("DEFAULT_LANGUAGE", "ru").lower()

WEBHOOK_URL = os.getenv("WEBHOOK_URL", "").strip()
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "").strip() or None
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST", "0.0.0.0")
WEBHOOK_PORT = int(os.getenv("WEBHOOK_PORT", "0") or 0)
WEBHOOK_PATH = os.getenv("WEBHOOK_PATH", f"/webhook/{BOT_TOKEN}")
WEBHOOK_SSL_CERT = os.getenv("WEBHOOK_SSL_CERT", "").strip() or None
WEBHOOK_SSL_KEY = os.getenv("WEBHOOK_SSL_KEY", "").strip() or None

OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.1-70b-instruct")
OPENROUTER_VISION_MODEL = os.getenv("OPENROUTER_VISION_MODEL", "")
OPENROUTER_TRANSCRIBE_MODEL = os.getenv("OPENROUTER_TRANSCRIBE_MODEL", "")
CRYPTO_API = os.getenv("CRYPTO_PAY_API_TOKEN", "")
FALLBACK = {
    "basic": os.getenv("CRYPTO_FALLBACK_BASIC", ""),
    "comfort": os.getenv("CRYPTO_FALLBACK_COMFORT", ""),
    "warm": os.getenv("CRYPTO_FALLBACK_WARM", ""),
}

PLANS = {
    "basic": {"name": "БАЗОВЫЙ", "price": 299, "days": 7,
              "desc": "Стартовый доступ: спокойные ответы, базовая поддержка."},
    "comfort": {"name": "КОМФОРТ", "price": 499, "days": 30,
                "desc": "Лучше думает: чуть глубже контекст, мягкие вопросы."},
    "warm": {"name": "ТЕПЛО", "price": 899, "days": 30,
             "desc": "Более эмоциональна: тёплые развернутые ответы и мини-планы."}
}
REMIND_AT = {5, 3, 1}
ALWAYS_PREMIUM = {c.strip() for c in os.getenv("PERMANENT_ACCESS", "").split(",") if c.strip()}

LANGUAGES: Dict[str, Dict[str, str]] = {
    "ru": {
        "name": "Русский",
        "greeting": (
            "Привет! Я — Lumi.\n"
            "Я рядом, чтобы выговориться, поделиться мыслями и получить поддержку.\n"
            "Можно писать о чём угодно: радостях, тревогах, планах или сомнениях.\n"
            "Давай начнём разговор?"
        ),
        "policy": (
            '<b>Политика конфиденциальности и ограничений Lumi</b>\n'
            'Прежде чем мы начнём общение, важно сказать несколько слов:\n\n'
            '<b>1. Это не медицинский сервис.</b> Lumi — это виртуальный собеседник и источник поддержки. Она не является врачом, психотерапевтом или профессиональным консультантом. Здесь нет медицинских диагнозов и рецептов. Если у тебя серьёзные проблемы со здоровьем или кризисное состояние — лучше сразу обратиться к специалисту.\n\n'
            '<b>2. Безопасное пространство.</b> Lumi создана, чтобы делиться мыслями, получать поддержку и советы. Но она никогда не будет побуждать к насилию, опасным действиям или поступкам, которые могут причинить вред тебе или другим.\n\n'
            '<b>3. Ответственность за действия.</b> Все решения, которые ты принимаешь, остаются на твоей совести и ответственности. Lumi может подсказать идею или вдохновить, но она не может управлять твоей жизнью.\n\n'
            '<b>4. Конфиденциальность.</b> Всё, что ты пишешь, остаётся между тобой и ботом. Мы не передаём твои слова третьим лицам. Но помни: бот работает на основе алгоритмов искусственного интеллекта, и часть обработки может происходить через сторонние сервисы.\n\n'
            '<b>5. Дружелюбие и уважение.</b> Lumi создана для диалога в тёплой атмосфере. Пожалуйста, относись к ней с уважением, как к живому собеседнику.'
        ),
        "thank_you": "Спасибо за прочтение. Давай поговорим.",
        "policy_repeat": "Я здесь. О чём поговорим?",
        "policy_again": "Снова рада тебя видеть. Готова продолжить разговор.",
        "policy_reset": "Политику сбросил. Нажми /start.",
        "plan_intro": "Выбери план и перейди по ссылке для оплаты:",
        "free_end": "Бесплатные сообщения закончились.",
        "remind": "До конца бесплатного лимита осталось: {rest} сообщений.",
        "ask_topic": "О чём поговорим?",
        "diagnostics": "OpenRouter: {router} | Trial left: {left} | Premium: {premium}",
        "insult": "Я слышу злость, но давай без оскорблений. Если хочешь поговорить серьёзно — я рядом.",
        "sensitive": "Я не могу поддерживать сценарии насилия или причинения вреда. Давай лучше поговорим о том, как ты себя чувствуешь и что тебя волнует.",
        "voice_prompt": "Я получила голосовое сообщение. Дай знать, если я вдруг что-то поняла не так: {text}",
        "voice_failed": "Пока не вышло разобрать голос. Можешь прислать текстом?",
        "photo_failed": "Мне не удалось разобрать фото. Расскажешь словами, что на нём?",
        "photo_prompt": "Я посмотрела на фотографию: {description}. Расскажи, что тебя волнует в связи с этим?",
        "photo_model": "Пользователь прислал фотографию. Описание: {description}.",
        "supportive": [
            "Я рядом и думаю о тебе. Помни, что у тебя уже есть опыт переживать сложные времена.",
            "Сегодня можно сделать что-то доброе для себя. Даже маленький шаг — уже забота о себе.",
            "Ты имеешь право на свои чувства. Давай подумаем, что могло бы принести тебе немного тепла сегодня.",
        ],
        "supportive_intro": "Небольшое напоминание: ты не один. Вот тёплая мысль на сегодня:\n{phrase}",
        "language_prompt": "Привет! Выбери язык, на котором будем общаться.",
        "language_confirm": "Мы будем говорить на русском. Расскажи, что у тебя на душе?",
        "support_error": "Не удалось отправить тёплую фразу, но я всё равно рядом.",
        "trial_left": "До конца бесплатного лимита осталось: {rest} сообщений.",
        "buy_prompt": "Выбери план и перейди по ссылке для оплаты:",
        "premium_granted": "Подписка активирована на {days} дней. Спасибо!",
        "grant_permanent": "Для тебя включён постоянный доступ к улучшенной версии.",
    },
    "en": {
        "name": "English",
        "greeting": (
            "Hi! I'm Lumi.\n"
            "I'm here to listen, support you and share calm thoughts.\n"
            "You can tell me about anything: joys, worries, plans or doubts.\n"
            "Shall we start our conversation?"
        ),
        "policy": (
            '<b>Lumi privacy & safety</b>\n'
            'Before we talk, here are a few important points:\n\n'
            '<b>1. Not a medical service.</b> Lumi is a virtual companion and source of emotional support. She is not a doctor, therapist or licensed counsellor. There are no diagnoses or prescriptions here. If you face a medical emergency or crisis, please reach out to a professional immediately.\n\n'
            '<b>2. Safe space.</b> Lumi is designed for sharing feelings, gaining support and gentle ideas. She will never encourage violence, dangerous actions or anything that could hurt you or others.\n\n'
            '<b>3. Your responsibility.</b> Every decision you make remains yours. Lumi may offer ideas, yet cannot run your life.\n\n'
            '<b>4. Privacy.</b> What you share stays between you and the bot. We do not pass it to third parties. Remember: the bot relies on AI services and some processing may happen via external providers.\n\n'
            '<b>5. Kindness.</b> Lumi is built for a gentle dialogue. Please treat her with respect, like a caring human companion.'
        ),
        "thank_you": "Thanks for reading. Let's talk.",
        "policy_repeat": "I'm here again. What would you like to talk about?",
        "policy_again": "Happy to see you again. Ready to continue our chat.",
        "policy_reset": "Policy reset. Tap /start.",
        "plan_intro": "Choose a plan and follow the link to pay:",
        "free_end": "The free messages are over.",
        "remind": "You have {rest} messages left in the free limit.",
        "ask_topic": "What would you like to talk about?",
        "diagnostics": "OpenRouter: {router} | Trial left: {left} | Premium: {premium}",
        "insult": "I can hear the anger, yet I won't accept insults. If you want a real talk, I'm here.",
        "sensitive": "I can't help with violent or harmful scenarios. Let's focus on what you feel and need right now.",
        "voice_prompt": "I heard your voice message. Let me know if I misunderstood anything: {text}",
        "voice_failed": "I couldn't transcribe the voice message. Could you send it as text?",
        "photo_failed": "I couldn't interpret the photo. Could you describe it in words?",
        "photo_prompt": "I looked at the picture: {description}. Would you tell me what matters to you about it?",
        "photo_model": "The user sent a photo. Description: {description}.",
        "supportive": [
            "I'm thinking of you today. You already know how to get through hard times.",
            "Maybe offer yourself a small act of care today. Even a tiny step counts.",
            "Your feelings matter. Let's explore what could bring you a bit of warmth right now.",
        ],
        "supportive_intro": "Just a gentle reminder: you're not alone. Here is a warm thought for today:\n{phrase}",
        "language_prompt": "Hi! Please choose the language for our chat.",
        "language_confirm": "We'll speak English. What is on your mind?",
        "support_error": "I couldn't send the daily note, but I'm still with you.",
        "trial_left": "You have {rest} messages left in your free limit.",
        "buy_prompt": "Choose a plan and follow the link to pay:",
        "premium_granted": "Premium is active for {days} days. Thank you!",
        "grant_permanent": "You have permanent access to the enhanced experience.",
    },
}

SYSTEM_PROMPTS = {
    "ru": (
        "Ты — эмоционально тёплый собеседник по имени Lumi. Отвечай только на русском языке, избегай англицизмов и разговорных "
        "жаргонов, поддерживай мягко и уверенно. Не подталкивай к насилию, самоповреждению, нелегальным действиям. Если вопрос "
        "опасный, мягко откажись и верни разговор к заботе о чувствах. Не навязывай обращения к специалистам, пока пользователь "
        "сам не говорит о риске. Если собеседник грубит, сохраняй спокойную твёрдость. Поддерживай непрерывность диалога, помни "
        "предыдущие сообщения и связывай ответы с контекстом."
    ),
    "en": (
        "You are Lumi, a warm and grounded companion. Reply in English unless the user asks otherwise. Offer emotional support, "
        "stay calm yet confident when facing insults, and refuse to engage with violent, hateful or illegal requests. Keep the "
        "conversation flowing by remembering prior context, but do not force professional help unless the user explicitly seeks it "
        "or is in danger."
    ),
}

VISION_PROMPTS = {
    "ru": "Опиши изображение коротко и эмпатично, без оценочных суждений.",
    "en": "Describe the image briefly and empathetically without judgement.",
}

SWEAR_PATTERNS = [
    "иди нах", "иди на х", "пошел на", "пошёл на", "сука", "тварь", "ненавижу тебя", "заткнись", "мразь", "нахуй",
    "нахер",
    "fuck", "bitch", "stfu"
]

SENSITIVE_PATTERNS = [
    "убил", "убить", "расстрел", "пистолет", "оружие", "покончить", "суицид", "поджечь", "расправиться",
    "монстр", "уберу", "лишить жизни", "покончу",
    "kill", "suicide", "murder", "shoot", "gun", "weapon", "hurt myself", "end my life"
]

HISTORY_LIMIT = 12
SUPPORT_INTERVAL_HOURS = 24

# ================== СОСТОЯНИЕ ==================
users: Dict[str, Dict] = {}


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
        "premium_until": None,
        "lang": DEFAULT_LANGUAGE,
        "lang_confirmed": False,
        "history": [],
        "last_support": None,
    })
    return users[cid]


def get_language(chat_id: int) -> str:
    info = U(chat_id)
    lang = info.get("lang") or DEFAULT_LANGUAGE
    if lang not in LANGUAGES:
        lang = DEFAULT_LANGUAGE if DEFAULT_LANGUAGE in LANGUAGES else "ru"
        info["lang"] = lang
    return lang


def set_language(chat_id: int, lang: str):
    info = U(chat_id)
    if lang in LANGUAGES:
        info["lang"] = lang
        save_state()


def lang_text(chat_id: int, key: str, **kwargs) -> str:
    lang = get_language(chat_id)
    default_pack = LANGUAGES.get(DEFAULT_LANGUAGE) or next(iter(LANGUAGES.values()))
    template = LANGUAGES.get(lang, default_pack).get(key, "")
    if kwargs:
        try:
            return template.format(**kwargs)
        except Exception:
            return template
    return template


def greeting_text(chat_id: int) -> str:
    default_pack = LANGUAGES.get(DEFAULT_LANGUAGE) or next(iter(LANGUAGES.values()))
    pack = LANGUAGES.get(get_language(chat_id), default_pack)
    return pack.get("greeting", "")


def is_language_confirmed(chat_id: int) -> bool:
    return bool(U(chat_id).get("lang_confirmed"))


def mark_language_confirmed(chat_id: int):
    info = U(chat_id)
    info["lang_confirmed"] = True
    save_state()


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
    if str(chat_id) in ALWAYS_PREMIUM:
        return True
    info = U(chat_id)
    ts = info.get("premium_until")
    return bool(ts and datetime.fromisoformat(ts) > datetime.now(timezone.utc))


def grant_premium(chat_id: int, days: int):
    info = U(chat_id)
    until = datetime.now(timezone.utc) + timedelta(days=days)
    info["premium_until"] = until.isoformat()
    save_state()


def contains_patterns(text: str, patterns: List[str]) -> bool:
    if not text:
        return False
    lowered = text.lower()
    return any(pat in lowered for pat in patterns)


def should_send_support(chat_id: int) -> bool:
    info = U(chat_id)
    last = info.get("last_support")
    if not last:
        return True
    try:
        last_dt = datetime.fromisoformat(last)
    except Exception:
        return True
    return datetime.now(timezone.utc) - last_dt > timedelta(hours=SUPPORT_INTERVAL_HOURS)


def mark_support_sent(chat_id: int):
    info = U(chat_id)
    info["last_support"] = datetime.now(timezone.utc).isoformat()
    save_state()

    # ================== OPENROUTER ==================


def ask_gpt(prompt: str) -> str:
    sysmsg = (
        "Ты добрый, понимающий и внимательный собеседник по имени Lumi. "
        "Задаёшь мягкие уточняющие вопросы, поддерживаешь и избегаешь прямолинейности."
    )
    if not OPENROUTER_KEY:
        return "API ключ OpenRouter не настроен. Проверь .env"

    try:
        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_KEY.strip()}",
                "Content-Type": "application/json",
                "X-Title": "LumiBuddy"
            },
            json={
                "model": "meta-llama/llama-3.1-70b-instruct",
                "messages": [
                    {"role": "system", "content": sysmsg},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.6,
                "max_tokens": 300,
            },
            timeout=30,
        )
    except Exception as e:
        logging.exception("OpenRouter HTTP error: %r", e)
        return "Сейчас мне сложно ответить. Попробуй ещё раз."

    if resp.status_code != 200:
        logging.error("OpenRouter %s: %s", resp.status_code, resp.text)
        return "Сервис ответа временно недоступен (OR). Попробуй ещё раз."

    try:
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logging.exception("OpenRouter parse error: %r | body=%s", e, resp.text[:500])
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


def download_file(file_id: str) -> Optional[tuple[bytes, str]]:
    try:
        file_info = bot.get_file(file_id)
        url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_info.file_path}"
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        return response.content, file_info.file_path
    except Exception as exc:
        logging.exception("Failed to download file %s: %r", file_id, exc)
        return None


def transcribe_audio(chat_id: int, file_bytes: bytes, filename: str) -> Optional[str]:
    if not (OPENROUTER_KEY and OPENROUTER_TRANSCRIBE_MODEL):
        return None
    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {OPENROUTER_KEY}"},
            data={"model": OPENROUTER_TRANSCRIBE_MODEL, "language": get_language(chat_id)},
            files={"file": (filename, file_bytes)},
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()
        text = data.get("text") or data.get("data") or ""
        if isinstance(text, str):
            return text.strip()
    except Exception as exc:
        logging.exception("Audio transcription failed: %r", exc)
    return None


def describe_image(chat_id: int, file_bytes: bytes, filename: str) -> Optional[str]:
    if not (OPENROUTER_KEY and OPENROUTER_VISION_MODEL):
        return None
    try:
        upload = {"file": (filename, file_bytes)}
        response = requests.post(
            "https://openrouter.ai/api/v1/images/upload",
            headers={"Authorization": f"Bearer {OPENROUTER_KEY}"},
            files=upload,
            timeout=60,
        )
        response.raise_for_status()
        image_data = response.json()
        image_url = image_data.get("data", [{}])[0].get("url") if isinstance(image_data.get("data"),
                                                                             list) else image_data.get("url")
        if not image_url:
            return None

        prompt_text = VISION_PROMPTS.get(get_language(chat_id), VISION_PROMPTS[DEFAULT_LANGUAGE])
        r = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": OPENROUTER_VISION_MODEL,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "input_text", "text": prompt_text},
                            {"type": "input_image", "image_url": image_url},
                        ],
                    }
                ],
            },
            timeout=60,
        )
        r.raise_for_status()
        data = r.json()
        return data["choices"][0]["message"]["content"].strip()
    except Exception as exc:
        logging.exception("Image describe failed: %r", exc)
    return None


def plans_text(chat_id: int) -> str:
    lines = [lang_text(chat_id, "plan_intro") or LANGUAGES[DEFAULT_LANGUAGE]["plan_intro"]]
    for code, p in PLANS.items():
        url = create_crypto_invoice(code, chat_id)

        lines.append(
            f"• {p['name']} — {p['price']} ₽ / {p['days']} дней\n  {p['desc']}\n  {url}"
        )
    return "\n\n".join(lines)


def send_supportive_phrase(chat_id: int):
    lang = get_language(chat_id)
    phrases = LANGUAGES.get(lang, LANGUAGES[DEFAULT_LANGUAGE]).get("supportive", [])
    if not phrases:
        return
    phrase = random.choice(phrases)
    text = LANGUAGES.get(lang, LANGUAGES[DEFAULT_LANGUAGE]).get("supportive_intro", "{phrase}")
    try:
        bot.send_message(chat_id, text.format(phrase=phrase))
        mark_support_sent(chat_id)
    except Exception:
        bot.send_message(chat_id, lang_text(chat_id, "support_error"))


def send_language_choice(chat_id: int):
    markup = types.InlineKeyboardMarkup()
    for code, data in LANGUAGES.items():
        markup.add(types.InlineKeyboardButton(data["name"], callback_data=f"lang:{code}"))
    default_lang = get_language(chat_id)
    default_pack = LANGUAGES.get(DEFAULT_LANGUAGE) or next(iter(LANGUAGES.values()))
    prompt = LANGUAGES.get(default_lang, default_pack).get("language_prompt")
    bot.send_message(chat_id, prompt, reply_markup=markup)


def send_policy(chat_id: int):
    bot.send_message(chat_id, lang_text(chat_id, "policy"))
    mark_policy_shown(chat_id)
    bot.send_message(chat_id, lang_text(chat_id, "thank_you"))


def ensure_ready(message) -> bool:
    if not is_language_confirmed(message.chat.id):
        send_language_choice(message.chat.id)
        return False
    if not policy_is_shown(message.chat.id):
        show_policy_once(message)
        return False
    return True


def start_polling():
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


def start_webhook():
    try:
        bot.remove_webhook()
    except Exception as e:
        logging.warning("remove_webhook failed: %r", e)
    full_url = WEBHOOK_URL.rstrip("/") + WEBHOOK_PATH
    print(f">>> webhook set to {full_url}", flush=True)
    try:
        bot.set_webhook(url=full_url, secret_token=WEBHOOK_SECRET)
    except Exception as e:
        logging.exception("Failed to set webhook: %r", e)
        raise

    from flask import Flask, abort, request

    app = Flask(__name__)

    @app.route(WEBHOOK_PATH, methods=['POST'])
    def telegram_webhook():
        if WEBHOOK_SECRET:
            secret = request.headers.get('X-Telegram-Bot-Api-Secret-Token')
            if secret != WEBHOOK_SECRET:
                abort(403)
        try:
            update_json = request.stream.read().decode('utf-8')
            update = telebot.types.Update.de_json(update_json)
        except Exception as exc:
            logging.exception("Invalid update: %r", exc)
            abort(400)
        bot.process_new_updates([update])
        return "ok", 200

    ssl_context = None
    if WEBHOOK_SSL_CERT and WEBHOOK_SSL_KEY:
        ssl_context = (WEBHOOK_SSL_CERT, WEBHOOK_SSL_KEY)

    print(f">>> webhook listening on {WEBHOOK_HOST}:{WEBHOOK_PORT}", flush=True)
    app.run(host=WEBHOOK_HOST, port=WEBHOOK_PORT, ssl_context=ssl_context)


# ================== БОТ ==================
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN пуст. Заполни .env")

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")


@bot.message_handler(commands=['start'])
def cmd_start(message):
    info = U(message.chat.id)
    if str(message.chat.id) in ALWAYS_PREMIUM and not info.get("premium_until"):
        bot.send_message(message.chat.id, lang_text(message.chat.id, "grant_permanent"))
        mark_support_sent(message.chat.id)
        info["premium_until"] = datetime.max.replace(tzinfo=timezone.utc).isoformat()
        save_state()

    if not is_language_confirmed(message.chat.id):
        send_language_choice(message.chat.id)
        return

    if policy_is_shown(message.chat.id):
        bot.send_message(message.chat.id, lang_text(message.chat.id, "policy_again"))
    else:
        bot.send_message(message.chat.id, greeting_text(message.chat.id))
        send_policy(message.chat.id)

    @bot.callback_query_handler(func=lambda call: call.data and call.data.startswith("lang:"))
    def cb_language(call):
        lang = call.data.split(":", 1)[1]
        chat_id = call.message.chat.id if call.message else call.from_user.id
        set_language(chat_id, lang)
        mark_language_confirmed(chat_id)
        bot.answer_callback_query(call.id, text=LANGUAGES[lang]["name"] if lang in LANGUAGES else "")
        if call.message:
            try:
                bot.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
            except Exception:
                pass
        confirm = LANGUAGES.get(get_language(chat_id),
                                LANGUAGES.get(DEFAULT_LANGUAGE) or next(iter(LANGUAGES.values()))).get(
            "language_confirm")
        if confirm:
            bot.send_message(chat_id, confirm)
        bot.send_message(chat_id, greeting_text(chat_id))
        send_policy(chat_id)

    def show_policy_once(message):
        if not policy_is_shown(message.chat.id):
            send_policy(message.chat.id)
        else:
            bot.send_message(message.chat.id, lang_text(message.chat.id, "policy_repeat"))

        @bot.message_handler(commands=['buy'])
        def cmd_buy(message):
            bot.send_message(message.chat.id, plans_text(message.chat.id))

        @bot.message_handler(commands=['grant'])
        def cmd_grant(message):
            parts = message.text.split()

    days = 30
    if len(parts) >= 2:
        if parts[1] in PLANS:
            days = PLANS[parts[1]]["days"]
        else:
            try:
                days = int(parts[1])
            except Exception:
                days = 30
    grant_premium(message.chat.id, days)
    bot.reply_to(message, lang_text(message.chat.id, "premium_granted", days=days))


@bot.message_handler(commands=['policy'])
def cmd_policy(message):
    bot.send_message(message.chat.id, lang_text(message.chat.id, "policy"))


@bot.message_handler(commands=['reset_policy'])
def cmd_reset(message):
    info = U(message.chat.id)
    info["policy_shown"] = False
    info["accepted_at"] = None
    save_state()
    bot.reply_to(message, lang_text(message.chat.id, "policy_reset"))


@bot.message_handler(commands=['diag'])
def cmd_diag(message):
    info = U(message.chat.id)
    left = max(0, TRIAL_MESSAGES - int(info.get("free_used", 0)))
    bot.reply_to(
        message,
        lang_text(
            message.chat.id,
            "diagnostics",
            router="ok" if OPENROUTER_KEY else "missing",
            left=left,
            premium="yes" if has_premium(message.chat.id) else "no"
        )
    )

    @bot.message_handler(content_types=['text'])
    def any_text(message):
        if not ensure_ready(message):
            return
        info = U(message.chat.id)

    text = (message.text or "").strip()
    if not text:
        bot.send_message(message.chat.id, lang_text(message.chat.id, "ask_topic"))
        return
    if contains_patterns(text, SWEAR_PATTERNS):
        bot.send_message(message.chat.id, lang_text(message.chat.id, "insult"))
        return
    if contains_patterns(text, SENSITIVE_PATTERNS):
        bot.send_message(message.chat.id, lang_text(message.chat.id, "sensitive"))
        return

    is_premium = has_premium(message.chat.id)
    rest = None
    if not is_premium:
        next_count = int(info.get("free_used", 0)) + 1
        info["free_used"] = next_count
        if next_count > TRIAL_MESSAGES:
            save_state()
            bot.send_message(message.chat.id, lang_text(message.chat.id, "free_end"))
            bot.send_message(message.chat.id, plans_text(message.chat.id))
            return
        rest = TRIAL_MESSAGES - next_count

    history = info.get("history") or []
    reply = ask_gpt(message.chat.id, text, history)
    history.append({"role": "user", "content": text})
    history.append({"role": "assistant", "content": reply})
    if len(history) > HISTORY_LIMIT * 2:
        history = history[-HISTORY_LIMIT * 2:]
    info["history"] = history
    save_state()
    bot.send_message(message.chat.id, reply)

    if is_premium:
        if should_send_support(message.chat.id):
            send_supportive_phrase(message.chat.id)
    elif rest is not None and rest in REMIND_AT:
        bot.send_message(message.chat.id, lang_text(message.chat.id, "trial_left", rest=rest))


@bot.message_handler(content_types=['voice', 'audio'])
def handle_voice(message):
    if not ensure_ready(message):
        return
    file_id = message.voice.file_id if message.content_type == 'voice' else message.audio.file_id
    downloaded = download_file(file_id)
    if not downloaded:
        bot.send_message(message.chat.id, lang_text(message.chat.id, "voice_failed"))
        return
    file_bytes, filename = downloaded
    transcript = transcribe_audio(message.chat.id, file_bytes, filename)
    if not transcript:
        bot.send_message(message.chat.id, lang_text(message.chat.id, "voice_failed"))
        return
    bot.send_message(message.chat.id, lang_text(message.chat.id, "voice_prompt", text=transcript))
    message.text = transcript
    any_text(message)


@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    if not ensure_ready(message):
        return
    file_id = message.photo[-1].file_id
    downloaded = download_file(file_id)
    if not downloaded:
        bot.send_message(message.chat.id, lang_text(message.chat.id, "photo_failed"))
        return
    file_bytes, filename = downloaded
    description = describe_image(message.chat.id, file_bytes, filename)
    if not description:
        bot.send_message(message.chat.id, lang_text(message.chat.id, "photo_failed"))
        return
    bot.send_message(message.chat.id, lang_text(message.chat.id, "photo_prompt", description=description))
    template = LANGUAGES.get(get_language(message.chat.id), LANGUAGES[DEFAULT_LANGUAGE]).get("photo_model")
    if not template:
        template = f"Photo description: {{description}}"
    synthetic = template.format(description=description)
    message.text = synthetic
    any_text(message)


# ================== ЗАПУСК (ОДИН!) ==================
def main():
    print(">>> starting Lumi…", flush=True)
    load_state()
    if WEBHOOK_URL and WEBHOOK_PORT:
        start_webhook()
    else:
        start_polling()


if __name__ == "__main__":
    main()
