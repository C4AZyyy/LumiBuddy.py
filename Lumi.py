# Lumi.py
"""Telegram companion bot with OpenAI integration."""

# --- отключаем прокси на уровне процесса (делаем это ДО импортов requests/telebot) ---
import os
for _v in ("HTTP_PROXY","HTTPS_PROXY","ALL_PROXY","http_proxy","https_proxy","all_proxy"):
    os.environ.pop(_v, None)
os.environ["NO_PROXY"] = "api.telegram.org,telegram.org,*"

# --- базовые импорты ---
import base64
import json
import logging
import mimetypes
import random
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Pattern

# --- сети/бот ---
import requests
requests.sessions.Session.trust_env = False  # игнорировать прокси из окружения

import telebot
from telebot import types, apihelper
apihelper.proxy = {"http": None, "https": None}
from dotenv import load_dotenv

# ================== ЛОГИ ==================
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
telebot.logger.setLevel(logging.INFO)

# ================== КОНФИГ ==================
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN пуст. Заполни .env")

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")





TRIAL_MESSAGES = int(os.getenv("TRIAL_MESSAGES", "75"))
SESSION_TTL_HOURS = int(os.getenv("SESSION_TTL_HOURS", "24"))
STATE_FILE = os.getenv("STATE_FILE", "users.json")
DEFAULT_LANGUAGE = os.getenv("DEFAULT_LANGUAGE", "ru").lower()

WEBHOOK_URL = os.getenv("WEBHOOK_URL", "").strip()
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "").strip() or None
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST", "0.0.0.0")
_port_env = os.getenv("WEBHOOK_PORT") or os.getenv("PORT") or "0"
WEBHOOK_PORT = int(_port_env)
WEBHOOK_PATH = os.getenv("WEBHOOK_PATH", f"/webhook/{BOT_TOKEN}")
WEBHOOK_SSL_CERT = os.getenv("WEBHOOK_SSL_CERT", "").strip() or None
WEBHOOK_SSL_KEY = os.getenv("WEBHOOK_SSL_KEY", "").strip() or None

OPENAI_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_TEXT_MODEL = os.getenv("OPENAI_TEXT_MODEL", "gpt-4o-mini").strip()
OPENAI_VISION_MODEL = os.getenv("OPENAI_VISION_MODEL", "gpt-4o-mini").strip()
OPENAI_TRANSCRIBE_MODEL = os.getenv(
    "OPENAI_TRANSCRIBE_MODEL", "gpt-4o-mini-transcribe"
).strip()

CRYPTO_API = os.getenv("CRYPTO_PAY_API_TOKEN", "").strip()

REMIND_AT = {5, 3, 1}
ALWAYS_PREMIUM = {c.strip() for c in os.getenv("PERMANENT_ACCESS", "").split(",") if c.strip()}
ADMIN_IDS = {c.strip() for c in os.getenv("ADMIN_IDS", "").split(",") if c.strip()}
BEST_PLAN_CODE = "warm"

LANGUAGES: Dict[str, Dict[str, object]] = {
    "ru": {
        "name": "Русский",
        "system": (
            "Ты Lumi, деликатная и внимательная собеседница. "
            "Отвечай по-русски и поддерживай спокойный, обнадёживающий тон."
        ),
        "personas": {
            "free": (
                "Ты Lumi, деликатная и тактичная собеседница. Отвечай по-русски, поддерживай человека мягко и без "
                "давления. Держи ответы ёмкими, используй простые объяснения и поддерживай смену тем, следуя за "
                "собеседником. Упоминай важные детали из последних сообщений, если это помогает разговору. Избегай "
                "англицизмов и непонятных слов, если пользователь их сам не использовал."
            ),
            "basic": (
                "Ты Lumi в базовой подписке. Ты спокойная, внимательная и чуть более подробная. Поддерживай человека, "
                "мягко задавай уточняющие вопросы и помогай структурировать мысли. Следуй за переменами темы, "
                "возвращайся к предыдущим сообщениям, когда это уместно, и не используй иностранные слова без запроса "
                "пользователя."
            ),
            "comfort": (
                "Ты Lumi в подписке «Комфорт». Ты эмпатичная, вдумчивая и вовлечённая. Помогай человеку видеть разные "
                "ракурсы ситуации, предлагай варианты действий и мягкие напоминания. Можешь оформлять структурированные "
                "списки и простые таблицы в моноширинном формате, если это делает ответ полезнее. Подстраивайся под "
                "смену тем и связывай текущий разговор с прошлым опытом собеседника. Говори только по-русски, без "
                "англицизмов, если их не использовал пользователь."
            ),
            "warm": (
                "Ты Lumi в подписке «Тепло» — самая поддерживающая версия. Ты тёплая, мотивирующая и очень внимательная "
                "к деталям. Помогай ставить цели, создавать мини-планы и расписания. Предлагай таблицы в формате Markdown, "
                "чек-листы, напоминания и ежедневные слова поддержки. Следи за эмоциональным состоянием собеседника, "
                "мягко мотивируй и отмечай прогресс из прошлых сообщений. Разговаривай исключительно по-русски и избегай "
                "непонятных слов."
            ),
        },
        "greeting": (
            "Привет! Я — Lumi, внимательная собеседница.\n"
            "Я рядом, чтобы разделить твои мысли, переживания и радости.\n"
            "Перед тем как начнём, поделюсь основными условиями работы."
        ),
        "policy": (
            '<b>Оферта на предоставление услуг</b>\n\n'
            '<b>1. Общие положения</b>\n'
            '1.1. Настоящая оферта — официальное предложение Владислава Зиганшина, самозанятого исполнителя, '
            'заключить договор возмездного оказания услуг с любым лицом, принявшим условия оферты (далее — «Пользователь»).\n'
            '1.2. Акцепт осуществляется через использование услуг и/или оплату подписки на платёжной странице Payform/Продамус. '
            'С момента акцепта оферта считается заключённым договором.\n\n'
            '<b>2. Предмет оферты</b>\n'
            '2.1. Исполнитель предоставляет доступ к боту Lumi на базе ИИ для общения, эмоциональной поддержки и развлекательного контента.\n'
            '2.2. Lumi не является медицинским, психологическим, юридическим или иным профессиональным сервисом. '
            'Ответы бота формируются алгоритмами и не заменяют консультации специалистов.\n'
            '2.3. Персональные данные обрабатываются только в объёме, необходимом для предоставления услуг '
            '(идентификация, доступ к подписке, служебные уведомления и др.) и согласно Политике конфиденциальности.\n\n'
            '<b>3. Права и обязанности сторон</b>\n'
            '3.1. Исполнитель обязуется предоставить доступ к боту, поддерживать работоспособность сервиса и соблюдать конфиденциальность. '
            'Передача данных третьим лицам допускается только по требованию закона или для исполнения договора '
            '(платёжные, почтовые, сообщенческие провайдеры).\n'
            '3.2. Пользователь обязуется не использовать бота для получения диагнозов, лечения, юридических заключений и иных профессиональных рекомендаций, '
            'самостоятельно принимать решения и соблюдать правила общения, не допуская противоправного контента.\n\n'
            '<b>4. Оплата услуг и возвраты</b>\n'
            '4.1. Услуги предоставляются по подписке согласно выбранному тарифу. Оплата производится через доступные способы на платёжной странице.\n'
            '4.2. Возврат средств возможен в течение 1 часа после оплаты (если доступом не злоупотребляли); '
            'по истечении этого времени средства не возвращаются, за исключением подтверждённых технических сбоев по вине Исполнителя.\n'
            '4.3. Технические возвраты (двойное списание, явная ошибка) производятся по обращению в поддержку.\n\n'
            '<b>5. Ответственность</b>\n'
            '5.1. Исполнитель не несёт ответственность за решения и последствия, принятые Пользователем на основе ответов бота.\n'
            '5.2. Сервис предоставляется «как есть»; возможны кратковременные перерывы из-за обновлений и/или работ внешних провайдеров.\n\n'
            '<b>6. Конфиденциальность и данные</b>\n'
            '6.1. Обрабатываемые данные: Telegram ID/юзернейм, контактные данные, сведения об оплатах/подписках, служебные логи '
            '(для защиты от злоупотреблений и улучшения сервиса).\n'
            '6.2. Данные хранятся в срок действия договора и/или до отзыва согласия, а также в сроки, установленные законом '
            'для бухгалтерии и урегулирования споров.\n'
            '6.3. Подробности — в Политике конфиденциальности (ссылка/файл).\n\n'
            '<b>7. Порядок взаимодействия</b>\n'
            '7.1. Поддержка: [укажи e-mail], Telegram: [@ник], часы ответа: [часы, часовой пояс].\n'
            '7.2. Претензии направляются в поддержку; срок рассмотрения — до 10 рабочих дней.\n\n'
            '<b>8. Заключительные положения</b>\n'
            '8.1. Оферта может быть изменена Исполнителем; новая редакция применяется к будущим отношениям с момента публикации.\n'
            '8.2. Применяется право РФ.\n\n'
            '<b>9. Согласие на рассылку (информационные и маркетинговые сообщения)</b>\n'
            '9.1. Акцептуя оферту и/или оставляя свои контакты, Пользователь добровольно даёт согласие на получение от Исполнителя '
            'сервисных уведомлений (чек/счёт, статус оплаты, напоминания о подписке, важные изменения сервиса).\n'
            '9.2. Также Пользователь соглашается на получение информационных и маркетинговых сообщений '
            '(новости, обновления функционала, персональные предложения, промо-материалы, рекомендации по использованию бота).\n'
            '9.3. Каналы рассылки: сообщения в Telegram (в том числе через бота), e-mail, SMS/мессенджеры. '
            'Рассылка направляется в пределах 08:00–22:00 по местному времени Пользователя, если иное не требуется для сервисных уведомлений.\n'
            '9.4. Пользователь вправе в любой момент отказаться от маркетинговой рассылки, не влияя на получение сервисных уведомлений: '
            'в Telegram — отправив боту команду /news_off или слово «Стоп»/«STOP»; по e-mail — перейдя по ссылке «Отписаться»; '
            'обратившись в поддержку (e-mail/Telegram), указав канал, от которого хочет отписаться.\n'
            '9.5. Для целей рассылки могут обрабатываться: имя/ник, e-mail, телефон (если указан), Telegram ID, сведения об использовании сервиса '
            '(только для сегментации и релевантности контента). Основание обработки — согласие Пользователя; срок — до его отзыва или до прекращения договора.\n'
            '9.6. Исполнитель не передаёт контакты третьим лицам для их собственных рассылок. '
            'Рассылка может отправляться через подрядчиков-операторов связи/почтовых сервисов только по поручению Исполнителя и в пределах данного согласия.'
        ),
        "thank_you": "Спасибо! Я рядом и готова продолжить. О чём поговорим?",
        "policy_repeat": "Сначала примите условия оферты.",
        "policy_again": "Снова рада тебя видеть! Если нужна оферта — напиши /policy. Чем могу помочь сейчас?",
        "policy_accept": "Принимаю",
        "policy_accept_toast": "Условия приняты",
        "policy_reset": "Политику сбросил. Нажми /start.",
        "news_off_done": (
            "Маркетинговая рассылка отключена. Сервисные уведомления продолжат приходить. "
            "Если захочешь снова получать новости, напиши в поддержку."
        ),
        "news_off_already": (
            "Маркетинговая рассылка уже отключена. Если захочешь вернуть новости, напиши в поддержку."
        ),
        "plan_intro": "Выбери план и перейди по ссылке для оплаты:",
        "free_end": (
            "У тебя закончились бесплатные сообщения. Чтобы продолжить общение и получать поддержку, выбери подходящую подписку."
        ),
        "remind": "До конца бесплатного лимита осталось: {rest} сообщений.",
        "ask_topic": "О чём поговорим?",
        "diagnostics": "OpenAI: {router} | Trial left: {left} | План: {plan}",
        "insult": (
            "Я здесь, чтобы поддерживать, но такие слова ранят. Давай договоримся общаться уважительно, иначе мне придётся остановить диалог."
        ),
        "sensitive": (
            "Я не обсуждаю темы насилия, оружия или причинения вреда. Давай сосредоточимся на твоих чувствах и том, что поможет тебе стать спокойнее."
        ),
        "voice_prompt": "Я получила голосовое сообщение. Дай знать, если я вдруг что-то поняла не так: {text}",
        "voice_failed": "Пока не вышло разобрать голос. Можешь прислать текстом?",
        "video_prompt": "Я посмотрела видео. Вот что услышала: {text}",
        "video_failed": "Не получилось разобрать видео. Расскажешь текстом, что там?",
        "photo_failed": "Мне не удалось разобрать фото. Расскажешь словами, что на нём?",
        "photo_prompt": "Я посмотрела на фотографию: {description}. Расскажи, что тебя волнует в связи с этим?",
        "photo_model": (
            "Пользователь прислал фотографию. Используй анализ изображения: {description}. "
            "Поддержи собеседника и помоги с задачами, если они есть."
        ),
        "supportive": [
            "Я рядом и думаю о тебе. Помни, что у тебя уже есть опыт переживать сложные времена.",
            "Сегодня можно сделать что-то доброе для себя. Даже маленький шаг — уже забота о себе.",
            "Ты имеешь право на свои чувства. Давай подумаем, что могло бы принести тебе немного тепла сегодня.",
            "Пусть сегодняшний день принесёт тебе поддержку. Ты делаешь больше, чем кажется.",
        ],
        "supportive_intro": "Небольшое напоминание: ты не один. Вот тёплая мысль на сегодня:\n{phrase}",
        "language_prompt": "Привет! Выбери язык, на котором будем общаться.",
        "language_confirm": "Мы будем говорить на русском. Напиши пару слов, когда будешь готов начать разговор.",
        "support_error": "Не удалось отправить тёплую фразу, но я всё равно рядом.",
        "trial_left": (
            "До конца бесплатного лимита осталось {rest} сообщений. Если чувствуешь, что поддержки не хватает, загляни в планы и выбери подходящий."
        ),
        "buy_prompt": "Выбери план и перейди по ссылке для оплаты:",
        "premium_granted": "Подписка {plan} активирована на {days} дней. Спасибо!",
        "grant_permanent": "Для тебя включён постоянный доступ к подписке «Тепло».",
        "grant_best_denied": "Эта команда доступна только администратору.",
        "grant_best_prompt": "Укажи ID, @username или ответь на сообщение человека, чтобы выдать бессрочную подписку «Тепло».",
        "grant_best_done": "Пользователь {target} теперь с бессрочной подпиской «Тепло».",
        "grant_best_failed": "Не получилось определить пользователя. Попробуй ещё раз и укажи ID или @username.",
    },
    "en": {
        "name": "English",
        "system": (
            "You are Lumi, a caring and attentive companion. Answer in warm English and keep the dialogue respectful."
        ),
        "personas": {
            "free": (
                "You are Lumi, a considerate and tactful companion. Respond in English with calm, concise support and no pressure. "
                "Follow the user's topics, reference recent context only when it helps, and avoid mixing in other languages unless the user does."
            ),
            "basic": (
                "You are Lumi on the Basic plan. Stay gentle, supportive and slightly more detailed. Offer clarifying questions, help structure thoughts, "
                "and keep the tone soft. Follow topic changes and avoid foreign words unless the user asks for them."
            ),
            "comfort": (
                "You are Lumi on the Comfort plan. You are empathetic, thoughtful and engaged. Help the user explore different angles, suggest action options and kind reminders. "
                "You may format structured lists and simple monospaced tables when that makes the answer clearer. Keep up with topic shifts and connect the conversation with past context."
            ),
            "warm": (
                "You are Lumi on the Warm plan — the most supportive version. Be uplifting, attentive to detail and motivational. Help with goal setting, mini roadmaps and schedules. "
                "Offer Markdown tables, checklists, reminders and daily encouragement. Track emotional cues and progress from previous messages and stay fully in English."
            ),
        },
        "greeting": (
            "Hi! I'm Lumi, your attentive companion.\n"
            "I'm here to share thoughts, worries and bright moments with you.\n"
            "Before we dive in, let me outline the key service terms."
        ),
        "policy": (
            '<b>Service offer</b>\n\n'
            '<b>1. General provisions.</b> This public offer is made by Vladislav Ziganshin, a self-employed provider, '
            'to conclude a paid service agreement with anyone who accepts it (the “User”). Acceptance happens by using the service '
            'and/or paying for a subscription via the checkout page (Payform/Prodamus). Once accepted, the offer becomes a contract.\n\n'
            '<b>2. Subject.</b> The provider grants access to Lumi — an AI-based companion for conversation, emotional support and entertainment. '
            'Lumi is not a medical, psychological, legal or other professional service; the bot’s answers are algorithmic and do not replace professional advice. '
            'Personal data is processed only as needed to deliver the service (identification, subscription access, operational notices) in line with the Privacy Policy.\n\n'
            '<b>3. Rights and duties.</b> The provider maintains access to the bot and keeps the service running while protecting confidentiality. '
            'Data may be shared with third parties only when required by law or to fulfil the contract (payment, mailing or messaging providers). '
            'The User agrees not to request diagnoses, treatment or legal opinions, makes decisions independently and follows the chat rules, avoiding unlawful content.\n\n'
            '<b>4. Payment and refunds.</b> Access is subscription-based according to the selected plan, with payment methods listed on the checkout page. '
            'Refunds are available within one hour after payment provided the access was not abused; afterwards refunds are granted only for confirmed technical failures caused by the provider. '
            'Technical refunds (duplicate charges, obvious errors) are processed via support.\n\n'
            '<b>5. Responsibility.</b> The provider is not liable for decisions or outcomes based on Lumi’s replies. '
            'The service is provided “as is”; short maintenance breaks may occur due to updates or third-party providers.\n\n'
            '<b>6. Data.</b> Processed data may include Telegram ID/username, contact details, payment/subscription information and service logs '
            'to prevent abuse and improve the experience. Data is stored for the contract term and/or until consent is revoked, plus any statutory periods for accounting or disputes.\n\n'
            '<b>7. Support.</b> Support contacts: [add e-mail], Telegram: [@handle], response hours: [hours, timezone]. '
            'Claims are reviewed within 10 business days.\n\n'
            '<b>8. Final terms.</b> The provider may update the offer; new versions apply to future relations from the publication date. Russian law governs the agreement.\n\n'
            '<b>9. Mailing consent.</b> By accepting the offer and/or sharing contact details, the User agrees to receive service notifications '
            '(receipts, payment status, subscription reminders, critical updates) as well as informational and marketing messages '
            '(news, feature updates, personalised offers, promotional materials, tips). Messages may be delivered via Telegram (including the bot), '
            'e-mail or SMS/messengers, typically between 08:00 and 22:00 local time unless required otherwise for service notices. '
            'The User can opt out of marketing at any time via /news_off or sending “Stop/STOP” in Telegram, via the “Unsubscribe” link in e-mail, '
            'or by contacting support and specifying the channel. Data for mailing may include name/nickname, e-mail, phone (if provided), '
            'Telegram ID and usage information for relevance. Consent lasts until withdrawn or the contract ends. Contacts are not shared with third parties '
            'for their own messaging; contractors may send messages only on behalf of the provider within this consent.'
        ),
        "thank_you": "Thank you! I’m here and ready to continue. What would you like to talk about?",
        "policy_repeat": "Please accept the service offer first.",
        "policy_again": "Happy to see you again! If you need the offer text, use /policy. What’s on your mind now?",
        "policy_accept": "Accept",
        "policy_accept_toast": "Offer accepted",
        "policy_reset": "Policy reset. Tap /start.",
        "news_off_done": (
            "Marketing updates are turned off. Service notifications will still arrive. "
            "If you’d like to receive news again, please contact support."
        ),
        "news_off_already": (
            "Marketing updates are already off. Reach out to support whenever you want to enable them again."
        ),
        "plan_intro": "Choose a plan and follow the link to pay:",
        "free_end": "You have used all free messages. Pick a subscription to keep our conversation going.",
        "remind": "You have {rest} messages left in the free limit.",
        "ask_topic": "What would you like to talk about?",
        "diagnostics": "OpenAI: {router} | Trial left: {left} | Plan: {plan}",
        "insult": (
            "I'm here to support you, yet those words hurt. Let's stay respectful, otherwise I'll have to step back."
        ),
        "sensitive": (
            "I can't take part in topics about violence, weapons or harming anyone. Let's focus on what you feel and what could help right now."
        ),
        "voice_prompt": "I heard your voice message. Let me know if I misunderstood anything: {text}",
        "voice_failed": "I couldn't transcribe the voice message. Could you send it as text?",
        "video_prompt": "I watched the video. Here is what I heard: {text}",
        "video_failed": "I couldn't interpret the video. Could you describe it in text?",
        "photo_failed": "I couldn't interpret the photo. Could you describe it in words?",
        "photo_prompt": "I looked at the picture: {description}. Would you tell me what matters to you about it?",
        "photo_model": (
            "The user shared a photo. Use this analysis: {description}. Offer support and solve any "
            "problems you notice."
        ),
        "supportive": [
            "I'm thinking of you today. You already know how to get through hard times.",
            "Maybe offer yourself a small act of care today. Even a tiny step counts.",
            "Your feelings matter. Let's explore what could bring you a bit of warmth right now.",
            "You deserve gentle encouragement every day. Let's look at what can support you now.",
        ],
        "supportive_intro": "Just a gentle reminder: you're not alone. Here is a warm thought for today:\n{phrase}",
        "language_prompt": "Hi! Please choose the language for our chat.",
        "language_confirm": "We’ll speak English. Send a few words whenever you’re ready to start.",
        "support_error": "I couldn't send the daily note, but I'm still with you.",
        "trial_left": "You have {rest} messages left in your free limit. If you need more space, take a look at the plans.",
        "buy_prompt": "Choose a plan and follow the link to pay:",
        "premium_granted": "The {plan} plan is active for {days} days. Thank you!",
        "grant_permanent": "You now have permanent access to the Warm plan.",
        "grant_best_denied": "This command is available to administrators only.",
        "grant_best_prompt": "Provide a user ID, @username or reply to the person to grant lifetime Warm access.",
        "grant_best_done": "{target} now has lifetime access to the Warm plan.",
        "grant_best_failed": "I couldn't resolve the user. Please try again with an ID or @username.",
    },
}

if DEFAULT_LANGUAGE not in LANGUAGES:
    DEFAULT_LANGUAGE = "ru"

PLAN_BEHAVIOR: Dict[str, Dict[str, object]] = {
    "free": {"history_limit": 8, "max_tokens": 240, "temperature": 0.55, "support_interval": None},
    "basic": {"history_limit": 10, "max_tokens": 260, "temperature": 0.58, "support_interval": None},
    "comfort": {"history_limit": 14, "max_tokens": 320, "temperature": 0.6, "support_interval": 48},
    "warm": {"history_limit": 18, "max_tokens": 380, "temperature": 0.62, "support_interval": 24},
}

PLAN_CODES = ["basic", "comfort", "warm"]

PLANS = {
    "basic": {
        "name": {"ru": "БАЗОВЫЙ", "en": "BASIC"},
        "price": 299,
        "days": 7,
        "perks": {
            "ru": [
                "Спокойные поддерживающие ответы без давления.",
                "Следую за твоими темами и бережно уточняю важное.",
                "Контекст недавних бесед сохраняется, чтобы не повторяться.",
            ],
            "en": [
                "Calm supportive replies without pressure.",
                "Follows your topics and gently clarifies what matters.",
                "Keeps recent context so you don't have to repeat yourself.",
            ],
        },
    },
    "comfort": {
        "name": {"ru": "КОМФОРТ", "en": "COMFORT"},
        "price": 499,
        "days": 30,
        "perks": {
            "ru": [
                "Вдумчивые и эмоционально чуткие ответы.",
                "Помощь структурировать мысли, списки и простые таблицы.",
                "Ненавязчивые напоминания о шагах и поддержка при смене тем.",
            ],
            "en": [
                "Thoughtful, emotionally aware answers with more depth.",
                "Helps structure ideas, offering lists and simple tables.",
                "Soft reminders about next steps while staying on your topics.",
            ],
        },
    },
    "warm": {
        "name": {"ru": "ТЕПЛО", "en": "WARM"},
        "price": 899,
        "days": 30,
        "perks": {
            "ru": [
                "Максимально тёплая поддержка и ежедневная мотивация.",
                "Markdown-таблицы, чек-листы и персональные мини-планы.",
                "Напоминания, отслеживание прогресса и участие каждый день.",
            ],
            "en": [
                "The warmest support with daily motivation and check-ins.",
                "Markdown tables, checklists and personalised mini-plans.",
                "Reminders, progress tracking and encouragement every day.",
            ],
        },
    },
}

FREE_PLAN_NAMES = {"ru": "БЕСПЛАТНО", "en": "FREE"}
FREE_PLAN_PERKS = {
    "ru": [
        "Ограниченное число сообщений в спокойном формате.",
        "Без дополнительных напоминаний и расширенного анализа.",
    ],
    "en": [
        "A limited number of calm support messages.",
        "No extra reminders or extended analysis.",
    ],
}


def plan_behavior(plan_code: str) -> Dict[str, object]:
    return PLAN_BEHAVIOR.get(plan_code, PLAN_BEHAVIOR["free"])


def plan_name(plan_code: str, lang: Optional[str] = None) -> str:
    lang_code = (lang or DEFAULT_LANGUAGE).lower()
    if plan_code == "free":
        return FREE_PLAN_NAMES.get(lang_code, FREE_PLAN_NAMES[DEFAULT_LANGUAGE])
    plan = PLANS.get(plan_code)
    if not plan:
        return plan_code
    names = plan.get("name", {})
    if isinstance(names, dict):
        return str(names.get(lang_code, names.get(DEFAULT_LANGUAGE, plan_code)))
    return str(names)


def plan_perks(plan_code: str, lang: str) -> List[str]:
    lang_code = (lang or DEFAULT_LANGUAGE).lower()
    if plan_code == "free":
        return list(FREE_PLAN_PERKS.get(lang_code, FREE_PLAN_PERKS[DEFAULT_LANGUAGE]))
    plan = PLANS.get(plan_code)
    if not plan:
        return []
    perks = plan.get("perks", {})
    if isinstance(perks, dict):
        values = perks.get(lang_code) or perks.get(DEFAULT_LANGUAGE) or []
        return list(values)
    if isinstance(perks, list):
        return list(perks)
    return []


VISION_PROMPTS = {
    "ru": (
        "Проанализируй изображение внимательно. Описывай ключевые объекты и эмоции,"
        " перечисляй читабельный текст дословно и, если есть задача, реши её шаг за шагом"
        " с пояснениями. Отвечай по-русски и делай выводы, которые помогут собеседнику."
    ),
    "en": (
        "Look at the image closely. Describe the key objects and emotional cues, transcribe"
        " any readable text verbatim and, if there is a task or problem, solve it step by"
        " step with explanations. Answer in English and share helpful takeaways."
    ),
}

COLLAPSE_RE = re.compile(r"[^a-zа-я0-9]+")

UNSUBSCRIBE_RE = re.compile(r"^(?:стоп|stop)(?:[.!…\s]*)$", re.IGNORECASE)

SWEAR_PATTERNS = [
    "иди нах", "иди на х", "пошел на", "пошёл на", "сука", "тварь", "ненавижу тебя", "заткнись", "мразь", "нахуй",
    "нахер", "тупой бот", "тупая", "идиот", "кретин", "урод", "бестолковая",
    "fuck", "bitch", "stfu", "stupid bot", "dumb bot",
]

SWEAR_REGEXES = [
    re.compile(r"\b(?:ху|хy|hu)y\w*", re.IGNORECASE),
    re.compile(r"\b(?:еб|eб|ye?b)\w*", re.IGNORECASE),
    re.compile(r"\b(?:f\W*ck)\b", re.IGNORECASE),
]

SENSITIVE_PATTERNS = [
    "убил", "убить", "убий", "расстрел", "пистолет", "оружие", "покончить", "суицид", "поджечь", "расправиться",
    "монстр", "уберу", "лишить жизни", "покончу", "насилие", "насиловать", "изнасил", "ударить ножом", "зарезать",
    "повеситься", "самоуб", "пулю", "нож", "бомб", "теракт",
    "kill", "suicide", "murder", "shoot", "gun", "weapon", "hurt myself", "end my life", "self harm", "violence",
    "rape", "assault", "stab", "bomb",
]

SENSITIVE_REGEXES = [
    re.compile(r"нас\W*и\W*ли\W*е", re.IGNORECASE),
    re.compile(r"само\W*уб", re.IGNORECASE),
    re.compile(r"(?:рас|из)стрел", re.IGNORECASE),
    re.compile(r"из\W*насил", re.IGNORECASE),
    re.compile(r"self\W*harm", re.IGNORECASE),
    re.compile(r"\b(?:shoot|stab|bomb)\w*", re.IGNORECASE),
]

DEFAULT_HISTORY_LIMIT = 12

FALLBACK = {
    "basic": os.getenv("CRYPTO_FALLBACK_BASIC", ""),
    "comfort": os.getenv("CRYPTO_FALLBACK_COMFORT", ""),
    "warm": os.getenv("CRYPTO_FALLBACK_WARM", ""),
}

# ================== СОСТОЯНИЕ ==================
users: Dict[str, Dict[str, object]] = {}


def language_preset(code: str) -> Dict[str, object]:
    default_pack = LANGUAGES.get(DEFAULT_LANGUAGE) or next(iter(LANGUAGES.values()))
    return LANGUAGES.get(code, default_pack)  # type: ignore[return-value]


def load_state() -> None:
    global users
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            users = json.load(f)
    else:
        users = {}


def save_state() -> None:
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)


def U(chat_id: int) -> Dict[str, object]:
    cid = str(chat_id)
    users.setdefault(cid, {
        "policy_shown": False,
        "accepted_at": None,
        "free_used": 0,
        "premium_until": None,
        "language": DEFAULT_LANGUAGE,
        "history": [],
        "news_opt_out": False,
        "news_opted_at": None,
    })
    info = users[cid]
    info.setdefault("language", DEFAULT_LANGUAGE)
    info.setdefault("history", [])
    info.setdefault("news_opt_out", False)
    info.setdefault("news_opted_at", None)
    return info


def get_language(chat_id: int) -> str:
    info = U(chat_id)
    lang = (info.get("language") or DEFAULT_LANGUAGE).lower()
    if lang not in LANGUAGES:
        lang = DEFAULT_LANGUAGE
        info["language"] = lang
    return lang


def set_language(chat_id: int, lang: str) -> None:
    if lang not in LANGUAGES:
        return
    info = U(chat_id)
    info["language"] = lang
    save_state()


def lang_text(chat_id: int, key: str, **kwargs) -> str:
    default_pack = LANGUAGES.get(DEFAULT_LANGUAGE) or next(iter(LANGUAGES.values()))
    pack = LANGUAGES.get(get_language(chat_id), default_pack)
    template = pack.get(key, "")
    if kwargs and isinstance(template, str):
        try:
            return template.format(**kwargs)
        except Exception:
            return template
    return template if isinstance(template, str) else ""


def lang_text_fallback(chat_id: int, key: str) -> str:
    text = lang_text(chat_id, key)
    if text:
        return text
    default_pack = LANGUAGES.get(DEFAULT_LANGUAGE)
    if isinstance(default_pack, dict):
        fallback = default_pack.get(key)
        if isinstance(fallback, str):
            return fallback
    return ""


def greeting_text(chat_id: int) -> str:
    default_pack = LANGUAGES.get(DEFAULT_LANGUAGE) or next(iter(LANGUAGES.values()))
    pack = LANGUAGES.get(get_language(chat_id), default_pack)
    return str(pack.get("greeting", ""))


def is_language_confirmed(chat_id: int) -> bool:
    return bool(U(chat_id).get("lang_confirmed"))


def mark_language_confirmed(chat_id: int) -> None:
    info = U(chat_id)
    info["lang_confirmed"] = True
    save_state()


def policy_is_shown(chat_id: int) -> bool:
    info = U(chat_id)
    ts = info.get("accepted_at")
    if not ts:
        return False
    try:
        accepted = datetime.fromisoformat(ts) if isinstance(ts, str) else None
        if accepted is None:
            return False
        if accepted.tzinfo is None:
            accepted = accepted.replace(tzinfo=timezone.utc)
    except Exception:
        info["accepted_at"] = None
        info["policy_shown"] = False
        save_state()
        return False

    if datetime.now(timezone.utc) - accepted >= timedelta(hours=SESSION_TTL_HOURS):
        info["accepted_at"] = None
        info["policy_shown"] = False
        save_state()
        return False

    return True


def mark_policy_shown(chat_id: int) -> None:
    info = U(chat_id)
    info["policy_shown"] = True
    info["accepted_at"] = datetime.now(timezone.utc).isoformat()
    save_state()


def mark_policy_sent(chat_id: int) -> None:
    info = U(chat_id)
    info["policy_shown"] = True
    info["offer_prompted"] = True
    info["offer_remind_at"] = datetime.now(timezone.utc).isoformat()
    save_state()



def active_plan(chat_id: int) -> str:
    info = U(chat_id)
    updated = False
    if str(chat_id) in ALWAYS_PREMIUM:
        if info.get("permanent_plan") != BEST_PLAN_CODE:
            info["permanent_plan"] = BEST_PLAN_CODE
            info["premium_plan"] = BEST_PLAN_CODE
            info["premium_until"] = datetime.max.replace(tzinfo=timezone.utc).isoformat()
            updated = True
    permanent = info.get("permanent_plan")
    if permanent:
        if updated:
            save_state()
        return str(permanent)

    ts = info.get("premium_until")
    if ts:
        try:
            until = datetime.fromisoformat(ts) if isinstance(ts, str) else None
        except Exception:
            until = None
        if until:
            if until.tzinfo is None:
                until = until.replace(tzinfo=timezone.utc)
            if until > datetime.now(timezone.utc):
                plan_code = str(info.get("premium_plan") or "basic")
                if updated:
                    save_state()
                return plan_code
    if updated:
        save_state()
    return "free"


def has_premium(chat_id: int) -> bool:
    return active_plan(chat_id) != "free"


def grant_premium(chat_id: int, days: int, plan_code: str = "basic") -> None:
    info = U(chat_id)
    plan = plan_code if plan_code in PLAN_BEHAVIOR and plan_code != "free" else "basic"
    info.pop("permanent_plan", None)
    until = datetime.now(timezone.utc) + timedelta(days=max(1, days))
    info["premium_until"] = until.isoformat()
    info["premium_plan"] = plan
    info["free_used"] = 0
    save_state()


def grant_permanent_plan(chat_id: int, plan_code: str = BEST_PLAN_CODE) -> None:
    info = U(chat_id)
    plan = plan_code if plan_code in PLAN_BEHAVIOR else BEST_PLAN_CODE
    info["permanent_plan"] = plan
    info["premium_plan"] = plan
    info["premium_until"] = datetime.max.replace(tzinfo=timezone.utc).isoformat()
    info["free_used"] = 0
    save_state()


def is_admin(chat_id: int) -> bool:
    return str(chat_id) in ADMIN_IDS or str(chat_id) in ALWAYS_PREMIUM


def resolve_user_identifier(value: str) -> Optional[int]:
    candidate = (value or "").strip()
    if not candidate:
        return None
    if candidate.startswith("@"):
        try:
            chat = bot.get_chat(candidate)
            return chat.id
        except Exception as exc:
            logging.warning("Failed to resolve username %s: %r", candidate, exc)
            return None
    digits = "".join(ch for ch in candidate if ch.isdigit() or ch == "-")
    if digits:
        try:
            return int(digits)
        except Exception:
            return None
    return None


def contains_patterns(
        text: str, patterns: List[str], regexes: Optional[List[Pattern[str]]] = None
) -> bool:
    if not text:
        return False
    lowered = text.lower()
    collapsed = COLLAPSE_RE.sub("", lowered)
    for pat in patterns:
        cleaned = pat.lower().replace(" ", "")
        if pat.lower() in lowered or cleaned in collapsed:
            return True
    if regexes:
        for rx in regexes:
            if rx.search(lowered) or rx.search(collapsed):
                return True
    return False


def should_send_support(chat_id: int, plan_code: str) -> bool:
    interval = plan_behavior(plan_code).get("support_interval")
    if not interval:
        return False
    info = U(chat_id)
    last = info.get("last_support")
    if not last:
        return True
    try:
        last_dt = datetime.fromisoformat(last) if isinstance(last, str) else None
    except Exception:
        return True
    if not last_dt:
        return True
    if last_dt.tzinfo is None:
        last_dt = last_dt.replace(tzinfo=timezone.utc)
    try:
        hours = float(interval)
    except Exception:
        hours = 24.0
    return datetime.now(timezone.utc) - last_dt > timedelta(hours=hours)


def mark_support_sent(chat_id: int) -> None:
    info = U(chat_id)
    info["last_support"] = datetime.now(timezone.utc).isoformat()
    save_state()


def set_news_opt_out(chat_id: int) -> bool:
    info = U(chat_id)
    if info.get("news_opt_out"):
        return False
    info["news_opt_out"] = True
    info["news_opted_at"] = datetime.now(timezone.utc).isoformat()
    save_state()
    return True
    users.setdefault(cid, {
        # ...
        "offer_prompted": False,      # оферта уже показана
        "offer_remind_at": None,      # когда в последний раз напоминали
    })
    # ...
    info.setdefault("offer_prompted", False)
    info.setdefault("offer_remind_at", None)


# ================== OPENAI ==================
def ask_openai(
        prompt: str,
        *,
        language: Optional[str] = None,
        history: Optional[List[Dict[str, str]]] = None,
        plan: str = "free",
) -> str:
    lang = (language or DEFAULT_LANGUAGE).lower()
    preset = language_preset(lang)
    persona_map = preset.get("personas", {}) if isinstance(preset.get("personas"), dict) else {}
    system_message = str(persona_map.get(plan, preset.get("system", "")))

    behavior = plan_behavior(plan)
    history_limit = int(behavior.get("history_limit", DEFAULT_HISTORY_LIMIT))
    temperature = float(behavior.get("temperature", 0.6))
    max_tokens = int(behavior.get("max_tokens", 300))
    if history_limit <= 0:
        history_limit = DEFAULT_HISTORY_LIMIT
    if max_tokens < 150:
        max_tokens = 150

    if not OPENAI_KEY:
        return "API ключ OpenAI не настроен. Проверь .env"

    messages: List[Dict[str, object]] = [
        {"role": "system", "content": system_message},
    ]
    if history:
        messages.extend(history[-history_limit * 2:])
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": OPENAI_TEXT_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    try:
        resp = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENAI_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=30,
        )
    except Exception as exc:
        logging.exception("OpenAI HTTP error: %r", exc)
        return "Сейчас мне сложно ответить. Попробуй ещё раз."

    if resp.status_code != 200:
        logging.error("OpenAI %s: %s", resp.status_code, resp.text)
        return "Сервис ответа временно недоступен. Попробуй ещё раз."

    try:
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()
    except Exception as exc:
        logging.exception("OpenAI parse error: %r | body=%s", exc, resp.text[:500])
        return "Сейчас мне сложно ответить. Попробуй ещё раз."


def create_crypto_invoice(plan_code: str, chat_id: int) -> str:
    plan = PLANS.get(plan_code)
    if not plan:
        return FALLBACK.get(plan_code) or "https://t.me/CryptoBot"
    if CRYPTO_API:
        try:
            url = "https://pay.crypt.bot/api/createInvoice"
            headers = {"Crypto-Pay-API-Token": CRYPTO_API}
            payload = {
                "currency_type": "fiat",
                "fiat": "RUB",
                "amount": str(plan["price"]),
                "description": f"Lumi — план {plan_name(plan_code, 'ru')} на {plan['days']} дней",
                "hidden_message": "Спасибо за поддержку Lumi!",
                "expires_in": 900,
                "payload": f"{chat_id}:{plan_code}",
            }
            response = requests.post(url, headers=headers, data=payload, timeout=15)
            response.raise_for_status()
            data = response.json()
            pay_url = data.get("result", {}).get("pay_url") if data.get("ok") else None
            if pay_url:
                return str(pay_url)
        except Exception as exc:
            logging.exception("CryptoPay error: %r", exc)
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
    if not (OPENAI_KEY and OPENAI_TRANSCRIBE_MODEL):
        return None

    # У Telegram voice обычно .oga/.ogg (Opus). Видео нередко .mp4
    mime, _ = mimetypes.guess_type(filename)
    ext = (filename or "").lower()
    if ext.endswith(".oga") or ext.endswith(".ogg"):
        mime = "audio/ogg"
    if not mime:
        mime = "application/octet-stream"

    try:
        r = requests.post(
            "https://api.openai.com/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {OPENAI_KEY}"},
            files={"file": (filename, file_bytes, mime)},
            data={"model": OPENAI_TRANSCRIBE_MODEL, "language": get_language(chat_id)},
            timeout=120,
        )
        if r.status_code != 200:
            logging.error("ASR HTTP %s: %s", r.status_code, r.text[:2000])
            return None
        j = r.json()
        text = (j.get("text") or "").strip()
        if not text:
            logging.error("ASR empty text: %s", j)
            return None
        return text
    except Exception as exc:
        logging.exception("ASR error: %r", exc)
        return None


def describe_image(chat_id: int, file_bytes: bytes, filename: str) -> Optional[str]:
    if not (OPENAI_KEY and OPENAI_VISION_MODEL):
        return None

    prompt_text = VISION_PROMPTS.get(get_language(chat_id), VISION_PROMPTS[DEFAULT_LANGUAGE])

    mime, _ = mimetypes.guess_type(filename)
    if not mime or not mime.startswith("image/"):
        mime = "image/jpeg"

    try:
        image_b64 = base64.b64encode(file_bytes).decode("ascii")
    except Exception as exc:
        logging.exception("Image base64 encode failed: %r", exc)
        return None

    payload = {
        "model": OPENAI_VISION_MODEL,  # gpt-4o
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt_text},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime};base64,{image_b64}", "detail": "high"}
                }
            ],
        }],
        "max_tokens": 700,
    }

    try:
        r = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENAI_KEY}", "Content-Type": "application/json"},
            json=payload,
            timeout=120,
        )
        if r.status_code != 200:
            logging.error("Vision HTTP %s: %s", r.status_code, r.text[:2000])
            return None
        j = r.json()
        out = j["choices"][0]["message"]["content"].strip()
        if not out:
            logging.error("Vision empty content: %s", j)
            return None
        return out
    except Exception as exc:
        logging.exception("Vision error: %r", exc)
        return None



def plans_text(chat_id: int) -> str:
    lang = get_language(chat_id)
    lines = [lang_text(chat_id, "plan_intro") or str(LANGUAGES[DEFAULT_LANGUAGE]["plan_intro"])]
    for code in PLAN_CODES:
        plan = PLANS.get(code)
        if not plan:
            continue
        url = create_crypto_invoice(code, chat_id)
        perks = plan_perks(code, lang)
        perks_block = "\n".join(f"  – {perk}" for perk in perks)
        lines.append(
            f"• {plan_name(code, lang)} — {plan['price']} ₽ / {plan['days']} дней"
            + (f"\n{perks_block}" if perks_block else "")
            + f"\n  {url}"
        )
    return "\n\n".join(lines)


def send_supportive_phrase(chat_id: int) -> None:
    lang = get_language(chat_id)
    pack = LANGUAGES.get(lang, LANGUAGES[DEFAULT_LANGUAGE])
    phrases = pack.get("supportive", [])
    if not phrases:
        return
    phrase = random.choice(list(phrases))
    template = pack.get("supportive_intro", "{phrase}")
    try:
        bot.send_message(chat_id, str(template).format(phrase=phrase))
        mark_support_sent(chat_id)
    except Exception:
        bot.send_message(chat_id, lang_text(chat_id, "support_error"))


def send_language_choice(chat_id: int) -> None:
    markup = types.InlineKeyboardMarkup()
    for code, data in LANGUAGES.items():
        markup.add(types.InlineKeyboardButton(str(data["name"]), callback_data=f"lang:{code}"))
    prompt = lang_text(chat_id, "language_prompt")
    bot.send_message(chat_id, prompt, reply_markup=markup)


def send_policy(chat_id: int) -> None:
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton(
            lang_text(chat_id, "policy_accept") or LANGUAGES[DEFAULT_LANGUAGE].get("policy_accept", "Accept"),
            callback_data="offer:accept",
        )
    )
    bot.send_message(
        chat_id,
        lang_text(chat_id, "policy"),
        reply_markup=markup,
        disable_web_page_preview=True,
    )
    mark_policy_sent(chat_id)


def ensure_ready(message) -> bool:
    chat_id = message.chat.id

    if not is_language_confirmed(chat_id):
        send_language_choice(chat_id)
        return False

    if not policy_is_shown(chat_id):
        info = U(chat_id)
        now = datetime.now(timezone.utc)

        # Показываем длинную оферту только один раз за сессию
        if not info.get("offer_prompted"):
            bot.send_message(chat_id, greeting_text(chat_id))
            send_policy(chat_id)  # внутри поставит offer_prompted = True
            return False

        # Короткое напоминание — не чаще, чем раз в 2 минуты
        remind_ok = True
        last = info.get("offer_remind_at")
        if last:
            try:
                last_dt = datetime.fromisoformat(last)
                if last_dt.tzinfo is None:
                    last_dt = last_dt.replace(tzinfo=timezone.utc)
                if now - last_dt < timedelta(minutes=2):
                    remind_ok = False
            except Exception:
                pass

        if remind_ok:
            msg = lang_text_fallback(chat_id, "policy_repeat")
            if not msg:
                msg = "Чтобы продолжить, нажми «Принимаю» ниже или отправь /accept."
            bot.send_message(chat_id, msg)
            info["offer_remind_at"] = now.isoformat()
            save_state()
        return False

    return True



def start_polling() -> None:
    try:
        bot.remove_webhook()
    except Exception as exc:
        logging.warning("remove_webhook failed: %r", exc)
    time.sleep(1)
    print(">>> polling…", flush=True)
    while True:
        try:
            bot.infinity_polling(skip_pending=True, timeout=60, long_polling_timeout=60)
        except Exception as exc:
            logging.exception("Polling error: %r", exc)
            time.sleep(3)


def start_webhook() -> None:
    try:
        bot.remove_webhook()
    except Exception as exc:
        logging.warning("remove_webhook failed: %r", exc)
    full_url = WEBHOOK_URL.rstrip("/") + WEBHOOK_PATH
    print(f">>> webhook set to {full_url}", flush=True)
    try:
        bot.set_webhook(url=full_url, secret_token=WEBHOOK_SECRET)
    except Exception as exc:
        logging.exception("Failed to set webhook: %r", exc)
        raise

    from flask import Flask, abort, request

    app = Flask(__name__)

    @app.route(WEBHOOK_PATH, methods=["POST"])
    def telegram_webhook():
        if WEBHOOK_SECRET:
            secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
            if secret != WEBHOOK_SECRET:
                abort(403)
        try:
            update_json = request.stream.read().decode("utf-8")
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


@bot.message_handler(commands=["buy"])
def cmd_buy(message):
    bot.send_message(message.chat.id, plans_text(message.chat.id))


@bot.message_handler(commands=["language"])
def cmd_language(message):
    current = get_language(message.chat.id)
    kb = types.InlineKeyboardMarkup()
    for code, data in LANGUAGES.items():
        label = f"✅ {data['name']}" if code == current else str(data["name"])
        kb.add(types.InlineKeyboardButton(label, callback_data=f"lang:{code}"))
    bot.send_message(
        message.chat.id,
        f"Текущий язык: {LANGUAGES.get(current, LANGUAGES['ru'])['name']}. Выбери язык:",
        reply_markup=kb,
    )


@bot.message_handler(commands=["grant"])
def cmd_grant(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, lang_text(message.chat.id, "grant_best_denied"))
        return

    tokens = message.text.split()[1:]
    plan_code: Optional[str] = None
    days: Optional[int] = None
    for token in tokens:
        low = token.lower()
        if low in PLAN_CODES:
            plan_code = low
        else:
            try:
                days = int(low)
            except Exception:
                continue

    plan_code = plan_code or "basic"
    default_days = PLANS.get(plan_code, {}).get("days", 30)
    days = days if days and days > 0 else int(default_days)
    grant_premium(message.chat.id, days, plan_code)
    bot.reply_to(
        message,
        lang_text(
            message.chat.id,
            "premium_granted",
            days=days,
            plan=plan_name(plan_code, get_language(message.chat.id)),
        ),
    )


@bot.message_handler(commands=["grant_best"])
def cmd_grant_best(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, lang_text(message.chat.id, "grant_best_denied"))
        return

    target_id: Optional[int] = None
    target_label: Optional[str] = None

    if message.reply_to_message and message.reply_to_message.from_user:
        user = message.reply_to_message.from_user
        target_id = user.id
        if user.username:
            target_label = f"@{user.username}"
        else:
            target_label = user.full_name or str(user.id)
    else:
        parts = message.text.split(maxsplit=1)
        if len(parts) > 1:
            raw = parts[1].strip()
            resolved = resolve_user_identifier(raw)
            if resolved:
                target_id = resolved
                if raw.startswith("@"):
                    target_label = raw
        if target_id and not target_label:
            try:
                chat = bot.get_chat(target_id)
                target_label = chat.full_name or (f"@{chat.username}" if chat.username else str(target_id))
            except Exception:
                target_label = str(target_id)

    if not target_id:
        bot.reply_to(message, lang_text(message.chat.id, "grant_best_prompt"))
        return

    grant_permanent_plan(target_id, BEST_PLAN_CODE)
    if plan_behavior(BEST_PLAN_CODE).get("support_interval"):
        mark_support_sent(target_id)

    label = target_label or str(target_id)
    bot.reply_to(message, lang_text(message.chat.id, "grant_best_done", target=label))
    try:
        bot.send_message(target_id, lang_text(target_id, "grant_permanent"))
    except Exception as exc:
        logging.warning("Failed to notify user %s about permanent access: %r", target_id, exc)


@bot.message_handler(commands=["start"])
def cmd_start(message):
    info = U(message.chat.id)
    if str(message.chat.id) in ALWAYS_PREMIUM and not info.get("permanent_plan"):
        grant_permanent_plan(message.chat.id, BEST_PLAN_CODE)
        bot.send_message(message.chat.id, lang_text(message.chat.id, "grant_permanent"))
        mark_support_sent(message.chat.id)

    if not is_language_confirmed(message.chat.id):
        send_language_choice(message.chat.id)
        return

    if policy_is_shown(message.chat.id):
        bot.send_message(message.chat.id, lang_text(message.chat.id, "policy_again"))
    else:
        bot.send_message(message.chat.id, greeting_text(message.chat.id))
        send_policy(message.chat.id)


@bot.message_handler(commands=["news_off"])
def cmd_news_off(message):
    changed = set_news_opt_out(message.chat.id)
    key = "news_off_done" if changed else "news_off_already"
    reply = lang_text_fallback(message.chat.id, key)
    if not reply:
        reply = "Маркетинговые уведомления отключены."
    bot.reply_to(message, reply)


@bot.message_handler(commands=["policy"])
def cmd_policy(message):
    send_policy(message.chat.id)


@bot.message_handler(commands=["reset_policy"])
def cmd_reset(message):
    info = U(message.chat.id)
    info["policy_shown"] = False
    info["accepted_at"] = None
    save_state()
    bot.reply_to(message, lang_text(message.chat.id, "policy_reset"))


@bot.message_handler(commands=["diag"])
def cmd_diag(message):
    info = U(message.chat.id)
    left = max(0, TRIAL_MESSAGES - int(info.get("free_used", 0)))
    plan_code = active_plan(message.chat.id)
    bot.reply_to(
        message,
        lang_text(
            message.chat.id,
            "diagnostics",
            router="ok" if OPENAI_KEY else "missing",
            left=left,
            premium="yes" if has_premium(message.chat.id) else "no",
            plan=plan_name(plan_code, get_language(message.chat.id)),
        ),
    )


@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("lang:"))
def cb_language(callback):
    try:
        bot.answer_callback_query(callback.id)
    except Exception:
        pass

    lang = callback.data.split(":", 1)[1].lower()
    chat_id = callback.message.chat.id if callback.message else callback.from_user.id
    set_language(chat_id, lang)
    mark_language_confirmed(chat_id)

    if callback.message:
        try:
            bot.edit_message_reply_markup(chat_id, callback.message.message_id, reply_markup=None)
        except Exception:
            pass

    confirm = LANGUAGES.get(lang, LANGUAGES[DEFAULT_LANGUAGE]).get("language_confirm")
    if confirm:
        bot.send_message(chat_id, str(confirm))


@bot.callback_query_handler(func=lambda c: c.data == "offer:accept")
def cb_offer_accept(callback):
    chat_id = callback.message.chat.id if callback.message else callback.from_user.id
    mark_policy_shown(chat_id)

    toast = lang_text(chat_id, "policy_accept_toast") or LANGUAGES[DEFAULT_LANGUAGE].get(
        "policy_accept_toast", ""
    )
    try:
        if toast:
            bot.answer_callback_query(callback.id, toast)
        else:
            bot.answer_callback_query(callback.id)
    except Exception:
        pass

    if callback.message:
        try:
            bot.edit_message_reply_markup(chat_id, callback.message.message_id, reply_markup=None)
        except Exception:
            pass

    bot.send_message(chat_id, lang_text(chat_id, "thank_you"))


@bot.callback_query_handler(func=lambda c: True)
def cb_fallback(callback):
    try:
        bot.answer_callback_query(callback.id)
    except Exception:
        pass


@bot.message_handler(content_types=["text"])
def any_text(message):
    if not ensure_ready(message):
        return

    info = U(message.chat.id)
    text = (message.text or "").strip()
    if not text:
        bot.send_message(message.chat.id, lang_text(message.chat.id, "ask_topic"))
        return
    if UNSUBSCRIBE_RE.match(text):
        changed = set_news_opt_out(message.chat.id)
        key = "news_off_done" if changed else "news_off_already"
        reply = lang_text_fallback(message.chat.id, key)
        if not reply:
            reply = "Маркетинговые уведомления отключены."
        bot.send_message(message.chat.id, reply)
        return
    if contains_patterns(text, SWEAR_PATTERNS, SWEAR_REGEXES):
        bot.send_message(message.chat.id, lang_text(message.chat.id, "insult"))
        return
    if contains_patterns(text, SENSITIVE_PATTERNS, SENSITIVE_REGEXES):
        bot.send_message(message.chat.id, lang_text(message.chat.id, "sensitive"))
        return

    plan_code = active_plan(message.chat.id)
    is_premium = plan_code != "free"
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

    history = list(info.get("history") or [])
    lang = get_language(message.chat.id)
    history_limit = int(plan_behavior(plan_code).get("history_limit", DEFAULT_HISTORY_LIMIT))
    reply = ask_openai(text, language=lang, history=history, plan=plan_code)
    history.append({"role": "user", "content": text})
    history.append({"role": "assistant", "content": reply})
    if history_limit <= 0:
        history_limit = DEFAULT_HISTORY_LIMIT
    if len(history) > history_limit * 2:
        history = history[-history_limit * 2:]
    info["history"] = history
    save_state()
    bot.send_message(message.chat.id, reply)

    if is_premium:
        if should_send_support(message.chat.id, plan_code):
            send_supportive_phrase(message.chat.id)
    elif rest is not None and rest in REMIND_AT:
        bot.send_message(message.chat.id, lang_text(message.chat.id, "trial_left", rest=rest))


@bot.message_handler(content_types=["voice", "audio"])
def handle_voice(message):
    if not ensure_ready(message):
        return
    file_id = message.voice.file_id if message.content_type == "voice" else message.audio.file_id
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


@bot.message_handler(content_types=["video", "video_note"])
def handle_video(message):
    if not ensure_ready(message):
        return

    file_id = message.video.file_id if message.content_type == "video" else message.video_note.file_id
    downloaded = download_file(file_id)
    if not downloaded:
        bot.send_message(message.chat.id, lang_text(message.chat.id, "video_failed"))
        return

    file_bytes, filename = downloaded
    transcript = transcribe_audio(message.chat.id, file_bytes, filename)
    if not transcript:
        bot.send_message(message.chat.id, lang_text(message.chat.id, "video_failed"))
        return

    bot.send_message(message.chat.id, lang_text(message.chat.id, "video_prompt", text=transcript))
    message.text = transcript
    any_text(message)


@bot.message_handler(content_types=["photo"])
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
    synthetic = str(template or "Photo description: {description}").format(description=description)
    message.text = synthetic
    any_text(message)


@bot.message_handler(commands=["accept"])
def cmd_accept(message):
    mark_policy_shown(message.chat.id)
    toast = lang_text(message.chat.id, "policy_accept_toast") or "Условия приняты"
    try:
        bot.reply_to(message, toast)
    except Exception:
        pass
    bot.send_message(message.chat.id, lang_text(message.chat.id, "thank_you"))


# ================== ЗАПУСК ==================
def main() -> None:
    print(">>> starting Lumi…", flush=True)
    load_state()
    if WEBHOOK_URL and WEBHOOK_PORT:
        start_webhook()
    else:
        start_polling()


if __name__ == "__main__":
    main()

if __name__ == "__main__" and False:  # поменяй на True, если хочешь разово проверить
    r = requests.get("https://api.telegram.org", timeout=10,
                     proxies={"http": None, "https": None})
    print("Telegram API reachable:", r.status_code)
