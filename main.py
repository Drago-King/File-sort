from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters, ContextTypes
from tinydb import TinyDB, Query
import re, os

TOKEN = os.getenv("BOT_TOKEN")

db = TinyDB('storage.json')
FileTable = db.table("files")


def extract_season_episode(name):

    name = name.lower()

    # sXXeYY detection
    m = re.search(r"s(\d+)[\. _-]*e(\d+)", name)
    if m:
        return int(m.group(1)), int(m.group(2))

    # [E191] or E191
    m = re.search(r"\[?e(\d+)\]?", name)
    if m:
        return 1, int(m.group(1))

    # number only
    m = re.search(r"(\d+)", name)
    if m:
        return 1, int(m.group(1))

    return 999, 999999999


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📁 File sorting bot active!\n\n"
        "• Upload files in any format\n"
        "• Supports SxxEyy, [E##], number only\n"
        "• Sorts by season → episode\n"
        "• Detects missing episodes\n\n"
        "When ready: /sort"
    )


async def store_files(update: Update, context: ContextTypes.DEFAULT_TYPE):

    document = (update.message.document or
                update.message.video or
                update.message.audio)

    if document is None:
        return

    FileTable.insert({
        "user": update.effective_user.id,
        "file_id": document.file_id,
        "name": document.file_name if document.file_name else document.file_unique_id
    })

    await update.message.reply_text("Stored ✔")


async def sort_files(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user.id

    files = FileTable.search(Query().user == user)

    if not files:
        await update.message.reply_text("❌ No files stored.")
        return

    for f in files:
        season, ep = extract_season_episode(f["name"])
        f["season"] = season
        f["episode"] = ep

    files = sorted(files, key=lambda x: (x["season"], x["episode"], x["name"]))

    # Missing episode detection
    missing_per_season = {}
    seasons = sorted(set(f["season"] for f in files if f["season"] != 999))

    for s in seasons:
        eps = sorted(f["episode"] for f in files if f["season"] == s)
        full = set(range(min(eps), max(eps) + 1))
        miss = sorted(full - set(eps))
        if miss:
            missing_per_season[s] = miss

    sorted_text = "\n".join(
        f"S{f['season']:02d}E{f['episode']:02d} - {f['name']}"
        for f in files
    )

    if not missing_per_season:
        missing_text = "None 🎉"
    else:
        missing_text = ""
        for s in sorted(missing_per_season):
            miss = ", ".join(f"E{e}" for e in missing_per_season[s])
            missing_text += f"S{s:02d}: {miss}\n"

    await update.message.reply_text(
        "📦 SORTED ↓\n"
        f"```\n{sorted_text}\n```",
        parse_mode="Markdown",
    )

    await update.message.reply_text(
        "❗ MISSING ↓\n"
        f"```\n{missing_text}\n```",
        parse_mode="Markdown",
    )

    for f in files:
        try:
            await update.message.reply_document(f["file_id"])
        except:
            pass

    FileTable.remove(Query().user == user)


app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("sort", sort_files))
app.add_handler(MessageHandler(filters.ALL & (~filters.COMMAND), store_files))

app.run_polling()
