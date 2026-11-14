"""Telegram onboarding + chat surface for Viktor.

Flow: /start → name → workspace → you're in. Then chat, attach photos/files,
dictate (voice notes), toggle browser/notifications, manage skills & plugins.
"""

from __future__ import annotations

import asyncio
import logging
import queue
import re
from pathlib import Path

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from config import Config
from vik808.brain import Brain
from vik808.chat_engine import ChatEngine
from vik808.browser_engine import BrowserEngine

log = logging.getLogger("vik808.telegram")

WELCOME = (
    "<b>Your AI coworker on your phone.</b>\n"
    "Chat with Viktor and keep work moving.\n\n"
    "Viktor is an AI coworker for your team — connected to this repository "
    "(the OpenAPK catalog) as knowledge, your skills, and your connected apps.\n\n"
    "First, what should I call you?"
)

HELP = """\
<b>Vik808 commands</b>
/start — onboard (name + workspace)
/new — reset the conversation thread
/status — profile, engine & backend status
/skills — list installed skills
/skill &lt;name&gt; — read a skill
/knowledge &lt;query&gt; — search the repo knowledge base
/genplugin &lt;description&gt; — GPT-generate a plugin + SKILL.md
/clawhub — sync skills from ClawHub sources
/browser on|off — toggle the optional browser engine
/notify on|off — proactive notifications from Viktor
/help — this message

You can also send photos, files, or voice notes — Viktor works with them."""


def _chunk(text: str, size: int = 3900) -> list[str]:
    if len(text) <= size:
        return [text]
    parts, buf = [], ""
    for para in re.split(r"(?<=\n\n)", text):
        if len(buf) + len(para) > size:
            if buf:
                parts.append(buf)
            while len(para) > size:
                parts.append(para[:size])
                para = para[size:]
            buf = para
        else:
            buf += para
    if buf:
        parts.append(buf)
    return parts


class Notifier:
    """Fans proactive Viktor messages out to subscribed chats via a thread-safe queue."""

    def __init__(self) -> None:
        self.subscribed: set[str] = set()
        self.q: "queue.Queue[tuple[str, str]]" = queue.Queue()

    def subscribe(self, chat_id: int | str) -> None:
        self.subscribed.add(str(chat_id))

    def unsubscribe(self, chat_id: int | str) -> None:
        self.subscribed.discard(str(chat_id))

    def push(self, message: str) -> None:
        for chat_id in self.subscribed:
            self.q.put((chat_id, message))

    async def drain_forever(self, app: Application) -> None:
        while True:
            chat_id, message = await asyncio.to_thread(self.q.get)
            try:
                for part in _chunk(message):
                    await app.bot.send_message(chat_id, part)
            except Exception as exc:  # blocked bot, dead chat, etc.
                log.warning("notify to %s failed: %s", chat_id, exc)


def build_application(
    cfg: Config,
    engine: ChatEngine,
    brain: Brain,
    browser: BrowserEngine,
    notifier: Notifier,
) -> Application:
    if not cfg.telegram_token:
        raise SystemExit("VIK808_TELEGRAM_TOKEN is not set — create a bot with @BotFather and put it in Vik808/.env")

    async def post_init(application: Application) -> None:
        asyncio.create_task(notifier.drain_forever(application))

    app = Application.builder().token(cfg.telegram_token).post_init(post_init).build()
    app.bot_data.update(engine=engine, brain=brain, browser=browser, notifier=notifier, cfg=cfg)

    # ------------------------------------------------------------------ onboarding
    async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        sess = engine.session(update.effective_chat.id)
        notifier.subscribe(sess.chat_id)
        sess.state = "awaiting_name"
        engine.save()
        await update.message.reply_text(WELCOME, parse_mode=ParseMode.HTML)

    async def cmd_onboard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await cmd_start(update, context)

    # ------------------------------------------------------------------ commands
    async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text(HELP, parse_mode=ParseMode.HTML)

    async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        sess = engine.session(update.effective_chat.id)
        brain_state = "ready" if cfg.has_llm else "NOT CONFIGURED (VIK808_LLM_API_KEY)"
        text = (
            f"<b>Vik808 status</b>\n"
            f"• {sess.public_summary()}\n"
            f"• brain: {cfg.llm_model} @ {cfg.llm_base_url} — {brain_state}\n"
            f"• {engine.backend.status()}\n"
            f"• {browser.status()}\n"
            f"• skills: {len(engine.skills.skills)} · knowledge chunks: {len(engine.knowledge.chunks)}"
        )
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)

    async def cmd_new(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        engine.reset(update.effective_chat.id)
        await update.message.reply_text("Fresh thread started. What are we working on?")

    async def cmd_skills(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        names = engine.skills.names()
        if not names:
            await update.message.reply_text("No skills installed yet. Try /clawhub or /genplugin.")
            return
        lines = [f"• <b>{n}</b> — {engine.skills.get(n).description or '…'}" for n in names[:60]]
        extra = len(names) - 60
        if extra > 0:
            lines.append(f"… and {extra} more")
        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)

    async def cmd_skill(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        name = " ".join(context.args).strip()
        if not name:
            await update.message.reply_text("Usage: /skill <name>")
            return
        await update.message.reply_text(engine.skills.read_for_prompt(name)[:3900])

    async def cmd_knowledge(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = " ".join(context.args).strip()
        if not query:
            await update.message.reply_text("Usage: /knowledge <query>")
            return
        hits = engine.knowledge.format_hits(query, k=cfg.knowledge_hits)
        await update.message.reply_text(hits or "No matching passages found.")

    async def cmd_genplugin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        description = " ".join(context.args).strip()
        if not description:
            await update.message.reply_text("Usage: /genplugin <description>")
            return
        await update.message.reply_text("✍️ Writing your plugin…")
        try:
            from vik808.plugins_gen import generate_plugin

            result = await asyncio.to_thread(
                generate_plugin, brain, engine.skills, description, cfg.plugins_dir
            )
            files = "\n".join(f"• {f}" for f in result["files"]) or "(no files)"
            await update.message.reply_text(
                f"✅ <b>{result['name']}</b> — {result['summary']}\n\n{files}",
                parse_mode=ParseMode.HTML,
            )
        except Exception as exc:
            await update.message.reply_text(f"Plugin generation failed: {exc}")

    async def cmd_clawhub(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text("🦞 Syncing ClawHub skills…")
        result = await asyncio.to_thread(engine.skills.sync_clawhub, cfg.clawhub_source_list)
        errors = "\n".join(result["errors"][:3])
        await update.message.reply_text(
            f"ClawHub sync done: {result['added']} added, {result['skipped']} already present, "
            f"{len(result['errors'])} source errors.\n{errors}".strip()
        )

    async def cmd_browser(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        arg = (context.args[0].lower() if context.args else "").strip()
        if arg not in {"on", "off"}:
            await update.message.reply_text("Usage: /browser on|off")
            return
        browser.enabled = arg == "on"
        sess = engine.session(update.effective_chat.id)
        sess.browser_enabled = browser.enabled
        engine.save()
        await update.message.reply_text(browser.status())

    async def cmd_notify(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        arg = (context.args[0].lower() if context.args else "").strip()
        sess = engine.session(update.effective_chat.id)
        if arg == "off":
            sess.notify_enabled = False
            notifier.unsubscribe(sess.chat_id)
            msg = "Proactive notifications off. You'll still get chat replies."
        else:
            sess.notify_enabled = True
            notifier.subscribe(sess.chat_id)
            msg = "Proactive notifications on — Viktor will ping this chat when work finishes."
        engine.save()
        await update.message.reply_text(msg)

    # ---------------------------------------------------------------- messages
    async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        sess = engine.session(update.effective_chat.id)
        text = update.message.text or ""

        if sess.state == "awaiting_name":
            sess.name = text.strip()[:80] or sess.name
            sess.state = "awaiting_workspace"
            engine.save()
            await update.message.reply_text(
                f"Nice to meet you, {sess.name}. What workspace / team should Viktor know about?"
            )
            return
        if sess.state == "awaiting_workspace":
            sess.workspace = text.strip()[:120] or "default"
            sess.state = ""
            notifier.subscribe(sess.chat_id)
            engine.save()
            await update.message.reply_text(
                f"✅ You're in, {sess.name} — workspace <b>{sess.workspace}</b>.\n"
                "Ask me anything, attach a file, or dictate a voice note. "
                "Try /skills, /knowledge &lt;query&gt;, or /help.",
                parse_mode=ParseMode.HTML,
            )
            return

        reply = await asyncio.to_thread(engine.handle, sess.chat_id, text, None)
        for part in _chunk(reply):
            await update.message.reply_text(part)

    async def on_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        sess = engine.session(update.effective_chat.id)
        photo = update.message.photo[-1] if update.message.photo else None
        caption = update.message.caption or ""
        name = f"photo_{photo.file_unique_id}.jpg" if photo else "photo.jpg"
        if photo:
            dest = Path(context.bot_data["cfg"].data_dir) / "attachments" / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            tg_file = await context.bot.get_file(photo.file_id)
            await tg_file.download_to_drive(dest)
        attachments = [{"kind": "photo", "name": name, "caption": caption}]
        reply = await asyncio.to_thread(
            engine.handle, sess.chat_id, caption or "Please look at this photo.", attachments
        )
        for part in _chunk(reply):
            await update.message.reply_text(part)

    async def on_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        sess = engine.session(update.effective_chat.id)
        doc = update.message.document
        caption = update.message.caption or ""
        name = doc.file_name or f"file_{doc.file_unique_id}"
        dest = Path(context.bot_data["cfg"].data_dir) / "attachments" / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        tg_file = await context.bot.get_file(doc.file_id)
        await tg_file.download_to_drive(dest)
        size_kb = round((doc.file_size or 0) / 1024, 1)
        attachments = [{"kind": "file", "name": name, "caption": caption or f"{size_kb} KB"}]
        reply = await asyncio.to_thread(
            engine.handle,
            sess.chat_id,
            caption or f"I've received the file {name}. What should I do with it?",
            attachments,
        )
        for part in _chunk(reply):
            await update.message.reply_text(part)

    async def on_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        sess = engine.session(update.effective_chat.id)
        voice = update.message.voice
        if not voice:
            await update.message.reply_text("Couldn't read that voice note.")
            return
        dest = Path(context.bot_data["cfg"].data_dir) / "attachments" / f"voice_{voice.file_unique_id}.oga"
        dest.parent.mkdir(parents=True, exist_ok=True)
        tg_file = await context.bot.get_file(voice.file_id)
        await tg_file.download_to_drive(dest)
        transcript = await asyncio.to_thread(brain.transcribe, str(dest))
        if not transcript:
            await update.message.reply_text(
                "I heard your voice note but speech-to-text isn't configured "
                "(needs an LLM provider with audio transcription)."
            )
            return
        attachments = [{"kind": "voice", "name": dest.name, "transcript": transcript}]
        reply = await asyncio.to_thread(engine.handle, sess.chat_id, transcript, attachments)
        for part in _chunk(reply):
            await update.message.reply_text(part)

    # ---------------------------------------------------------------- wiring
    app.add_handler(CommandHandler(["start", "onboard"], cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("new", cmd_new))
    app.add_handler(CommandHandler("skills", cmd_skills))
    app.add_handler(CommandHandler("skill", cmd_skill))
    app.add_handler(CommandHandler("knowledge", cmd_knowledge))
    app.add_handler(CommandHandler("genplugin", cmd_genplugin))
    app.add_handler(CommandHandler("clawhub", cmd_clawhub))
    app.add_handler(CommandHandler("browser", cmd_browser))
    app.add_handler(CommandHandler("notify", cmd_notify))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    app.add_handler(MessageHandler(filters.PHOTO, on_photo))
    app.add_handler(MessageHandler(filters.Document.ALL, on_document))
    app.add_handler(MessageHandler(filters.VOICE, on_voice))
    return app
