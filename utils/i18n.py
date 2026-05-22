"""
utils/i18n.py — Internationalisation and translation helper for the bot UI.
"""

from __future__ import annotations

# Text strings for the bot in different languages
# Note: In MarkdownV2, special characters like !, ., (, ) MUST be escaped with \\
STRINGS = {
    "en": {
        "welcome": "👋 *Welcome to VoiceScribe AI\\!*\n\nI am the world's most advanced voice assistant\\. Here is what I can do for you:\n\n1️⃣ Convert voice messages to text\n2️⃣ Summarize long texts\n3️⃣ Extract actionable tasks\n4️⃣ Convert text to speech \\(Voice Generation\\)\n\n👇 *Choose your language to start:*",
        "lang_selected": "✅ *Language set to English\\!*",
        "buy_status": "💳 *Account & Billing*\n\n👤 User ID: `{user_id}`\n🌐 Language: {lang_name}\n📅 Joined: {joined}",
        "balance_info": "\n\n💰 *Current Balances*\n▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n🎙 Transcribe: `{transcribe_bal}`\n📝 Summarize: `{summarize_bal}`\n🌐 Translate: `{translate_bal}`\n📌 Actions: `{extract_bal}`\n🔊 TTS: `{tts_bal}`\n▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬",
        "transcribing": "⏳ Transcribing...",
        "summarizing": "⏳ Summarizing...",
        "extracting": "⏳ Extracting actions...",
        "translating": "⏳ Translating...",
        "btn_summarize": "📝 Summarize",
        "btn_actions": "📌 Action Items",
        "btn_translate": "🌐 Translate",
        "btn_back": "⬅️ Back",
        "btn_top_up": "💳 Buy Credits / Top Up",
        "choose_target_lang": "🌐 *Choose target language for translation:*",
        "error_generic": "❌ *An error occurred\\. Please try again later\\.*",
        "instructions": "🚀 *How to use the bot:*\n\n1️⃣ Send any voice message or audio file to transcribe\\.\n2️⃣ Use the buttons below the text to summarize, extract tasks, or translate\\.\n3️⃣ Send /tts command to generate professional voiceovers\\!",
        "limit_reached": "⚠️ *Limit Reached\\!*\n\nYou have run out of credits for *{feature}*\\.\n\n👇 *Choose a plan below to top up your balance:*",
        "btn_buy_more": "💳 Buy Credits",
        "buy_request_sent": "📨 *Request Sent\\!*\n\nYour request for *{plan}* has been sent to our team\\. We will contact you shortly to complete the payment and activate your credits\\.",
        "err_too_long_audio": "❌ *Audio too long\\!*\n\nMaximum duration per message is *20 minutes*\\. Please send shorter voice notes\\.",
        "err_too_long_text": "❌ *Text too long\\!*\n\nThis transcript is too large to process in one go\\. Maximum allowed is *30,000 characters*\\.",
        "buy_menu_main": "💳 *Buy Credits*\n\nSelect which feature you want to top up:",
        "buy_menu_transcribe": "🎙 *Transcription Plans*\n\n• 60 daqiqa — 9 100 so'm\n• 3 soat — 24 500 so'm\n• 10 soat — 82 000 so'm",
        "buy_menu_summarize": "📝 *Summarization Plans*\n\n• 20 ta — 7 000 so'm\n• 100 ta — 28 000 so'm\n• 300 ta — 70 000 so'm",
        "buy_menu_translate": "🌐 *Translation Plans*\n\n• 20 ta — 7 000 so'm\n• 100 ta — 28 000 so'm\n• 300 ta — 70 000 so'm",
        "buy_menu_actions": "📌 *Action Extraction Plans*\n\n• 20 ta — 7 000 so'm\n• 100 ta — 28 000 so'm\n• 300 ta — 70 000 so'm",
        "btn_transcription": "🎙 Transcription",
        "btn_summarization": "📝 Summarization",
        "btn_translation": "🌐 Translation",
        "btn_actions_extr": "📌 Action Extraction",
        "admin_buy_request": "🚨 *NEW BUY REQUEST*\n\n👤 *User:* {name}\n🆔 *ID:* `{user_id}`\n🏷 *Username:* @{username}\n📦 *Plan:* {plan}\n\nTo grant credits, use:\n`/set_balance {user_id} {feature} {amount}`",
        "sub_required": "🚫 *Subscription Required\\!*\\n\nTo use this bot, you must be a member of our channel: {channel}\\.\n\nPlease join and click the button below to continue\\.",
        "btn_join_channel": "📢 Join Channel",
        "btn_check_sub": "✅ I have joined",
        "btn_tts": "🔊 Speak",
        "btn_tts_feature": "🎙 Text-to-Speech",
        "generating_voice": "⏳ Generating speech...",
        "err_too_long_tts": "❌ *Text too long\\!*\\n\\nMaximum allowed length for TTS is *10,000 characters*\\.",
        "buy_menu_tts": "🎙 *Text\\-to\\-Speech Plans*\\n\\n• 20 ta — 7 000 so'm\\n• 100 ta — 28 000 so'm\\n• 300 ta — 70 000 so'm",

        # Interactive Voice Generation Strings
        "prompt_tts_text": "✍️ *Please enter the text you want to convert to speech:*\\n\\(\\*Maximum 10,000 characters\\*\\)",
        "select_voice_model": "🔊 *Select a voice model below:*\\n\\nYou can listen to a preview or select the voice to synthesize your text\\.",
        "err_no_tts_text": "❌ *No text found for voice generation\\.* Please start again with /tts command\\.",
        "tts_success": "🗣 *Professional voiceover generated successfully\\!*\n\n@QuloqAiBot",
        "preview_text_en_Guy": "Hello\\! I am Guy's voice\\. I can professionally synthesize any text you write\\.",
        "preview_text_en_Jenny": "Hi there\\! My name is Jenny\\. I will gladly read your text with a pleasant and clear voice\\.",
    },
    "uz": {
        "welcome": "👋 *VoiceScribe AI\\-ga xush kelibsiz\\!*\n\nMen dunyodagi eng ilg'or ovozli yordamchiman\\. Men quyidagi ishlarni bajara olaman:\n\n1️⃣ Ovozli xabarni matnga aylantirish\n2️⃣ Matnni xulosa qilish\n3️⃣ Muhim vazifalarni ajratib olish\n4️⃣ Matnni ovozga aylantirish \\(Ovoz yaratish\\)\n\n👇 *Boshlash uchun tilni tanlang:*",
        "lang_selected": "✅ *Til O'zbekchaga o'rnatildi\\!*",
        "buy_status": "💳 *Hisob va To'lovlar*\n\n👤 ID: `{user_id}`\n🌐 Til: {lang_name}\n📅 Qo'shilgan: {joined}",
        "balance_info": "\n\n💰 *Joriy limitlar*\n▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n🎙 Matn: `{transcribe_bal}`\n📝 Xulosa: `{summarize_bal}`\n🌐 Tarjima: `{translate_bal}`\n📌 Vazifalar: `{extract_bal}`\n🔊 TTS: `{tts_bal}`\n▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬",
        "transcribing": "⏳ Matnga aylantirilmoqda...",
        "summarizing": "⏳ Xulosa qilinmoqda...",
        "extracting": "⏳ Vazifalar ajratilmoqda...",
        "translating": "⏳ Tarjima qilinmoqda...",
        "btn_summarize": "📝 Xulosa",
        "btn_actions": "📌 Vazifalar",
        "btn_translate": "🌐 Tarjima qilish",
        "btn_back": "⬅️ Orqaga",
        "btn_top_up": "💳 Limit sotib olish / To'ldirish",
        "choose_target_lang": "🌐 *Tarjima qilish uchun tilni tanlang:*",
        "error_generic": "❌ *Xatolik yuz berdi\\. Iltimos, keyinroq urinib ko'ring\\.*",
        "instructions": "🚀 *Botdan foydalanish:*\n\n1️⃣ Istalgan ovozli xabar yoki audio faylni yuboring\\.\n2️⃣ Matn tagidagi tugmalar orqali xulosa qiling, vazifalarni ajrating yoki tarjima qiling\\.\n3️⃣ Professional ovozlar yaratish uchun /tts buyrug'ini yuboring\\!",
        "limit_reached": "⚠️ *Limitga yetdingiz\\!*\n\nSizda *{feature}* uchun limit tugadi\\.\n\n👇 *Balansni to'ldirish uchun tarifni tanlang:*",
        "btn_buy_more": "💳 Limit sotib olish",
        "buy_request_sent": "📨 *So'rov yuborildi\\!*",
        "admin_buy_request": "🚨 *YANGI SOTIB OLISH SO'ROVI*\n\n👤 *Foydalanuvchi:* {name}\n🆔 *ID:* `{user_id}`\n🏷 *Username:* @{username}\n📦 *Plan:* {plan}\n\nLimit qo'shish uchun:\n`/set_balance {user_id} {feature} {amount}`",
        "err_too_long_audio": "❌ *Audio juda uzun\\!*\n\nBitta xabar uchun maksimal davomiylik *20 daqiqa*\\. Iltimos, qisqaroq ovozli xabar yuboring\\.",
        "err_too_long_text": "❌ *Matn juda uzun\\!*\n\nUshbu matn bir martada qayta ishlash uchun juda katta\\. Maksimal ruxsat etilgan miqdor *30,000 belgi*\\.",
        "buy_menu_main": "💳 *Limit sotib olish*\n\nBalansni to'ldirmoqchi bo'lgan funksiyani tanlang:",
        "buy_menu_transcribe": "🎙 *Transkripsiya tariflari*\n\n• 60 daqiqa — 9 100 so'm\n• 3 soat — 24 500 so'm\n• 10 soat — 82 000 so'm",
        "buy_menu_summarize": "📝 *Xulosa tariflari*\n\n• 20 ta — 7 000 so'm\n• 100 ta — 28 000 so'm\n• 300 ta — 70 000 so'm",
        "buy_menu_translate": "🌐 *Tarjima tariflari*\n\n• 20 ta — 7 000 so'm\n• 100 ta — 28 000 so'm\n• 300 ta — 70 000 so'm",
        "buy_menu_actions": "📌 *Vazifalar tariflari*\n\n• 20 ta — 7 000 so'm\n• 100 ta — 28 000 so'm\n• 300 ta — 70 000 so'm",
        "btn_transcription": "🎙 Transkripsiya",
        "btn_summarization": "📝 Xulosa qilish",
        "btn_translation": "🌐 Tarjima qilish",
        "btn_actions_extr": "📌 Vazifalar ajratish",
        "sub_required": "🚫 *Obuna talab qilinadi\\!*\n\nBotdan foydalanish uchun bizning kanalimizga a'zo bo'lishingiz kerak: {channel}\\.\n\nIltimos, a'zo bo'ling va davom etish uchun quyidagi tugmani bosing\\.",
        "btn_join_channel": "📢 Kanalga a'zo bo'lish",
        "btn_check_sub": "✅ A'zo bo'ldim",
        "btn_tts": "🔊 Eshitish",
        "btn_tts_feature": "🎙 Matnni ovozga o'tkazish",
        "generating_voice": "⏳ Ovoz yaratilmoqda...",
        "err_too_long_tts": "❌ *Matn juda uzun\\!*\\n\\nTTS uchun maksimal ruxsat etilgan uzunlik *10,000 belgi*\\.",
        "buy_menu_tts": "🎙 *Matnni ovozga o'tkazish tariflari*\\n\\n• 20 ta — 7 000 so'm\\n• 100 ta — 28 000 so'm\\n• 300 ta — 70 000 so'm",

        # Interactive Voice Generation Strings
        "prompt_tts_text": "✍️ *Ovozli xabar yaratish uchun matn kiriting:*\\n\\(\\*Maksimal 10,000 belgi\\*\\)",
        "select_voice_model": "🔊 *Ovoz modelini tanlang:*\\n\\nOvozni eshitib ko'rish yoki matningizni shu ovozda yaratish uchun quyidagi tugmalarni bosing\\.",
        "err_no_tts_text": "❌ *Ovoz yaratish uchun matn topilmadi\\.* Iltimos, /tts buyrug'ini boshidan ishlating\\.",
        "tts_success": "🗣 *Professional ovoz muvaffaqiyatli yaratildi\\!*\n\n@QuloqAiBot",
        "preview_text_uz_Sardor": "Salom\\! Men Sardorning professional ovoziman\\. Yozgan matningizni xuddi shu ovozda eshittirib bera olaman\\.",
        "preview_text_uz_Madina": "Assalomu alaykum\\! Mening ismim Madina\\. Men siz yozgan matnni yoqimli ayol ovozida o'qib beraman\\.",
    },
    "ru": {
        "welcome": "👋 *Добро пожаловать в VoiceScribe AI\\!*\n\nЯ самый продвинутый голосовой помощник\\. Вот что я умею делать:\n\n1️⃣ Преобразовывать голосовые сообщения в текст\n2️⃣ Делать краткое изложение текстов\n3️⃣ Выделять важные задачи из текста\n4️⃣ Преобразовывать текст в речь \\(Озвучка\\)\n\n👇 *Выберите язык для начала:*",
        "lang_selected": "✅ *Язык установлен на Русский\\!*",
        "buy_status": "💳 *Аккаунт и Биллинг*\n\n👤 ID пользователя: `{user_id}`\n🌐 Язык: {lang_name}\n📅 Дата регистрации: {joined}",
        "balance_info": "\n\n💰 *Текущие лимиты*\n▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n🎙 Текст: `{transcribe_bal}`\n📝 Пересказ: `{summarize_bal}`\n🌐 Перевод: `{translate_bal}`\n📌 Задачи: `{extract_bal}`\n🔊 Озвучка: `{tts_bal}`\n▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬",
        "transcribing": "⏳ Расшифровка...",
        "summarizing": "⏳ Краткое изложение...",
        "extracting": "⏳ Выделение задач...",
        "translating": "⏳ Перевод...",
        "btn_summarize": "📝 Пересказать",
        "btn_actions": "📌 Список задач",
        "btn_translate": "🌐 Перевести",
        "btn_back": "⬅️ Назад",
        "btn_top_up": "💳 Купить лимиты / Пополнить",
        "choose_target_lang": "🌐 *Выберите язык для перевода:*",
        "error_generic": "❌ *Произошла ошибка\\. Пожалуйста, попробуйте позже\\.*",
        "instructions": "🚀 *Как пользоваться ботом:*\n\n1️⃣ Отправьте любое голосовое или аудиосообщение\\.\n2️⃣ Дождитесь расшифровки\\.\n3️⃣ Используйте кнопки под текстом для пересказа, задач или перевода\\.\n4️⃣ Отправьте команду /tts для профессиональной озвучки текста\\!",
        "limit_reached": "⚠️ *Лимит исчерпан\\!*",
        "btn_buy_more": "💳 Купить лимиты",
        "buy_request_sent": "📨 *Запрос отправлен\\!*",
        "admin_buy_request": "🚨 *НОВЫЙ ЗАПРОС НА ПОКУПКУ*\n\n👤 *Пользователь:* {name}\n🆔 *ID:* `{user_id}`\n🏷 *Username:* @{username}\n📦 *План:* {plan}\n\nЧтобы выдать лимиты, используйте:\n`/set_balance {user_id} {feature} {amount}`",
        "err_too_long_audio": "❌ *Аудио слишком длинное\\!*\n\nМаксимальная длительность одного сообщения — *20 минут*\\. Пожалуйста, отправляйте более короткие записи\\.",
        "err_too_long_text": "❌ *Текст слишком длинный\\!*\n\nЭтот текст слишком велик для обработки за один раз\\. Максимально допустимо *30,000 символов*\\.",
        "buy_menu_main": "💳 *Покупка лимитов*\n\nВыберите функцию, баланс которой хотите пополнить:",
        "buy_menu_transcribe": "🎙 *Тарифы на расшифровку*\n\n• 60 минут — 9 100 сум\n• 3 часа — 24 500 сум\n• 10 часов — 82 000 сум",
        "buy_menu_summarize": "📝 *Тарифы на пересказ*\n\n• 20 шт — 7 000 сум\n• 100 шт — 28 000 сум\n• 300 шт — 70 000 сум",
        "buy_menu_translate": "🌐 *Тарифы на перевод*\n\n• 20 шт — 7 000 сум\n• 100 шт — 28 000 сум\n• 300 шт — 70 000 сум",
        "buy_menu_actions": "📌 *Тарифы на задачи*\n\n• 20 шт — 7 000 сум\n• 100 шт — 28 000 сум\n• 300 шт — 70 000 сум",
        "btn_transcription": "🎙 Расшифровка",
        "btn_summarization": "📝 Пересказ",
        "btn_translation": "🌐 Перевод",
        "btn_actions_extr": "📌 Выделение задач",
        "sub_required": "🚫 *Требуется подписка\\!*\n\nЧтобы использовать этого бота, вы должны быть участником нашего канала: {channel}\\.\n\nПожалуйста, подпишитесь и нажмите кнопку ниже, чтобы продолжить\\.",
        "btn_join_channel": "📢 Подписаться на канал",
        "btn_check_sub": "✅ Я подписался",
        "btn_tts": "🔊 Озвучить",
        "btn_tts_feature": "🎙 Преобразование текста в речь",
        "generating_voice": "⏳ Генерирую озвучку...",
        "err_too_long_tts": "❌ *Текст слишком длинный\\!*\\n\\nМаксимальная длина текста для TTS — *10,000 символов*\\.",
        "buy_menu_tts": "🎙 *Тарифы на озвучку*\\n\\n• 20 шт — 7 000 сум\\n• 100 шт — 28 000 сум\\n• 300 шт — 70 000 сум",

        # Interactive Voice Generation Strings
        "prompt_tts_text": "✍️ *Введите текст для создания озвучки:*\\n\\(\\*Максимум 10,000 символов\\*\\)",
        "select_voice_model": "🔊 *Выберите модель голоса:*\\n\\nВы можете прослушать превью или выбрать голос для озвучивания вашего текста\\.",
        "err_no_tts_text": "❌ *Текст для озвучки не найден\\.* Пожалуйста, начните заново с команды /tts\\.",
        "tts_success": "🗣 *Профессиональная озвучка успешно создана\\!*\n\n@QuloqAiBot",
        "preview_text_ru_Dmitry": "Здравствуйте\\! Я мужской голос Дмитрий\\. Я могу профессионально озвучить любой ваш текст\\.",
        "preview_text_ru_Svetlana": "Приветствую\\! Меня зовут Светлана\\. Я с удовольствием озвучу ваш текст красивым женским голосом\\.",
    },
}

def get_text(key: str, lang: str = "en", **kwargs) -> str:
    """Get localized string by key and language, falling back safely."""
    lang_dict = STRINGS.get(lang, STRINGS["en"])
    text = lang_dict.get(key)
    if text is None:
        text = STRINGS["en"].get(key)
    if text is None:
        # Fallback to scanning all other language dictionaries
        for d in STRINGS.values():
            if key in d:
                text = d[key]
                break
    if text is None:
        # Graceful fallback to key itself
        text = key
        
    if kwargs:
        return text.format(**kwargs)
    return text

def get_lang_name(lang: str) -> str:
    """Get human readable language name."""
    names = {"uz": "O'zbek", "ru": "Русский", "en": "English"}
    return names.get(lang, "English")
