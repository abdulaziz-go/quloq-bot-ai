# 🎙️ VoiceScribe AI — Telegram Voice-to-Text Bot

A world-class Telegram bot that transcribes voice messages using OpenAI Whisper, with premium AI features powered by GPT-4o.

---

## ✨ Features

| Feature | Plan | Description |
|---------|------|-------------|
| 🎙️ **Voice Transcription** | Free | Transcribe any voice message or audio file |
| 📨 **Forwarded Message Support** | Free | Forward voice messages from any chat or group |
| 🌍 **50+ Languages** | Free | Auto-detects language with Whisper |
| 💡 **AI Summarizer** | Premium | Concise ≤5-sentence summary via inline button |
| ✅ **Smart Action Detection** | Premium | Extracts tasks, deadlines & questions as a checklist |

---

## 🚀 Quick Start

### 1. Clone & install

```bash
cd "voice ai"
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure

```bash
cp .env.example .env
```

Edit `.env` and fill in:
- `TELEGRAM_BOT_TOKEN` — Get from [@BotFather](https://t.me/BotFather) on Telegram
- `OPENAI_API_KEY` — Get from [platform.openai.com](https://platform.openai.com)
- `ADMIN_IDS` — Your Telegram user ID (get it from [@userinfobot](https://t.me/userinfobot))

### 3. Run

```bash
python bot.py
```

---

## 📋 Commands

| Command | Who | Description |
|---------|-----|-------------|
| `/start` | Everyone | Welcome screen & feature overview |
| `/help` | Everyone | Full help guide |
| `/status` | Everyone | Check your plan (Free / Premium) |
| `/grant <user_id>` | Admin only | Grant premium to a user |
| `/revoke <user_id>` | Admin only | Revoke premium from a user |

---

## 🔒 Premium System

Premium is granted manually by admins:

1. Find a user's Telegram ID (they can use `/start` — you'll see it in logs, or they can use [@userinfobot](https://t.me/userinfobot))
2. Run `/grant 123456789` in your bot chat
3. User now has access to Summarize & Smart Action Detection buttons

---

## 📁 Project Structure

```
voice ai/
├── bot.py                   # Entry point
├── config.py                # Settings & env var loading
├── requirements.txt         # Dependencies
├── .env.example             # Environment template
│
├── handlers/
│   ├── commands.py          # /start /help /status /grant /revoke
│   ├── voice.py             # Voice/audio transcription handler
│   └── callbacks.py         # Inline button callbacks
│
├── services/
│   ├── transcriber.py       # OpenAI Whisper API
│   ├── summarizer.py        # GPT-4o summarization
│   └── action_detector.py   # GPT-4o action extraction
│
├── database/
│   ├── db.py                # SQLite schema & init
│   └── users.py             # User & transcript CRUD
│
└── utils/
    ├── formatting.py        # Telegram message formatters
    └── decorators.py        # @admin_only, @premium_required
```

---

## 🔧 Supported Audio Formats

Voice messages, audio files (MP3, M4A, WAV, FLAC), video notes (circle messages), and any forwarded versions of these.

---

## 📊 Architecture

```
User sends voice → handle_voice()
                      ↓
              Download via Telegram API
                      ↓
              transcribe_telegram_file()  ←→  OpenAI Whisper
                      ↓
              save_transcript() → SQLite
                      ↓
              format_transcript() → Send with inline keyboard
                      ↓
         [💡 Summarize]          [✅ Extract Actions]
              ↓                           ↓
        summarize()              extract_actions()
        GPT-4o                   GPT-4o (JSON mode)
              ↓                           ↓
        format_summary()         format_actions()
              ↓                           ↓
         Send reply               Send checklist + Copy button
```
