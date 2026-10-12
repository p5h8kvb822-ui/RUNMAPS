import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ConversationHandler, ContextTypes, filters
)
from poster import create_poster

# États de la conversation
(LANG, NAME, BIB, RACE, TIME, DATE, GPX, CONFIRM) = range(8)

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

# Textes bilingues
TEXTS = {
    "fr": {
        "welcome": "Salut ! Je vais créer ta carte de course 🏃‍♂️\n\nChoisis ta langue :",
        "ask_name": "Quel est ton prénom et nom ?",
        "ask_bib": "Quel est ton numéro de dossard ?",
        "ask_race": "Quel est le nom de la course ? (ex: Semi Marathon de Metz)",
        "ask_time": "Quel est ton temps officiel ? (ex: 2H15'56\")",
        "ask_date": "Quelle est la date de la course ? (ex: 11/10/2026)",
        "ask_gpx": "Envoie maintenant ton fichier GPX",
        "recap": "Voici le récapitulatif :\n\n👤 Nom : {name}\n🔢 Dossard : {bib}\n🏁 Course : {race}\n⏱️ Temps : {time}\n📅 Date : {date}\n\nTout est correct ?",
        "generating": "Génération de ta carte en cours... ⏳",
        "done": "Voici ta carte ! 🎉",
        "modified": "Ok, quelle information veux-tu modifier ?",
        "cancel": "Opération annulée."
    },
    "en": {
        "welcome": "Hi! I'll create your race map 🏃‍♂️\n\nChoose your language:",
        "ask_name": "What is your full name?",
        "ask_bib": "What is your bib number?",
        "ask_race": "What is the race name? (e.g. Metz Half Marathon)",
        "ask_time": "What is your official time? (e.g. 2H15'56\")",
        "ask_date": "What is the race date? (e.g. 11/10/2026)",
        "ask_gpx": "Now send your GPX file",
        "recap": "Here's the summary:\n\n👤 Name: {name}\n🔢 Bib: {bib}\n🏁 Race: {race}\n⏱️ Time: {time}\n📅 Date: {date}\n\nIs everything correct?",
        "generating": "Generating your map... ⏳",
        "done": "Here's your map! 🎉",
        "modified": "Ok, which information do you want to change?",
        "cancel": "Operation cancelled."
    }
}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🇫🇷 Français", callback_data="lang_fr")],
        [InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")]
    ]
    await update.message.reply_text(
        "👋 Welcome / Bienvenue !\n\nChoose your language / Choisis ta langue :",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return LANG

async def set_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    lang = query.data.split("_")[1]
    context.user_data["lang"] = lang
    context.user_data["data"] = {}
    
    await query.edit_message_text(TEXTS[lang]["ask_name"])
    return NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["data"]["name"] = update.message.text
    lang = context.user_data["lang"]
    await update.message.reply_text(TEXTS[lang]["ask_bib"])
    return BIB

async def get_bib(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["data"]["bib"] = update.message.text
    lang = context.user_data["lang"]
    await update.message.reply_text(TEXTS[lang]["ask_race"])
    return RACE

async def get_race(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["data"]["race"] = update.message.text
    lang = context.user_data["lang"]
    await update.message.reply_text(TEXTS[lang]["ask_time"])
    return TIME

async def get_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["data"]["time"] = update.message.text
    lang = context.user_data["lang"]
    await update.message.reply_text(TEXTS[lang]["ask_date"])
    return DATE

async def get_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["data"]["date"] = update.message.text
    lang = context.user_data["lang"]
    await update.message.reply_text(TEXTS[lang]["ask_gpx"])
    return GPX

async def get_gpx(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.document:
        await update.message.reply_text("Merci d'envoyer un fichier GPX.")
        return GPX

    file = await update.message.document.get_file()
    gpx_path = f"temp_{update.effective_user.id}.gpx"
    await file.download_to_drive(gpx_path)
    context.user_data["gpx_path"] = gpx_path

    return await show_recap(update, context)

async def show_recap(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data["lang"]
    data = context.user_data["data"]
    
    text = TEXTS[lang]["recap"].format(**data)
    
    keyboard = [
        [InlineKeyboardButton("✅ Oui, générer", callback_data="confirm_yes")],
        [InlineKeyboardButton("✏️ Modifier", callback_data="confirm_edit")],
        [InlineKeyboardButton("❌ Annuler", callback_data="confirm_cancel")]
    ]
    
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    return CONFIRM

async def confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = context.user_data["lang"]

    if query.data == "confirm_yes":
        await query.edit_message_text(TEXTS[lang]["generating"])
        
        try:
            poster_bytes = create_poster(
                context.user_data["gpx_path"],
                context.user_data["data"],
                lang
            )
            await context.bot.send_photo(
                chat_id=query.message.chat_id,
                photo=poster_bytes,
                caption=TEXTS[lang]["done"]
            )
        except Exception as e:
            await context.bot.send_message(chat_id=query.message.chat_id, text=f"Erreur : {e}")
        
        # Nettoyage
        if os.path.exists(context.user_data.get("gpx_path", "")):
            os.remove(context.user_data["gpx_path"])
        
        return ConversationHandler.END

    elif query.data == "confirm_edit":
        keyboard = [
            [InlineKeyboardButton("Nom", callback_data="edit_name")],
            [InlineKeyboardButton("Dossard", callback_data="edit_bib")],
            [InlineKeyboardButton("Course", callback_data="edit_race")],
            [InlineKeyboardButton("Temps", callback_data="edit_time")],
            [InlineKeyboardButton("Date", callback_data="edit_date")],
        ]
        await query.edit_message_text(TEXTS[lang]["modified"], reply_markup=InlineKeyboardMarkup(keyboard))
        return CONFIRM

    else:
        await query.edit_message_text(TEXTS[lang]["cancel"])
        return ConversationHandler.END

async def edit_field(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    field = query.data.split("_")[1]
    context.user_data["editing"] = field
    lang = context.user_data["lang"]

    questions = {
        "name": TEXTS[lang]["ask_name"],
        "bib": TEXTS[lang]["ask_bib"],
        "race": TEXTS[lang]["ask_race"],
        "time": TEXTS[lang]["ask_time"],
        "date": TEXTS[lang]["ask_date"],
    }
    await query.edit_message_text(questions[field])
    return NAME if field == "name" else BIB if field == "bib" else RACE if field == "race" else TIME if field == "time" else DATE

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "fr")
    await update.message.reply_text(TEXTS[lang]["cancel"])
    return ConversationHandler.END

def main():
    TOKEN = "TON_TOKEN_ICI"  # ← Remplace par ton token BotFather

    app = Application.builder().token(TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            LANG: [CallbackQueryHandler(set_language)],
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            BIB: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_bib)],
            RACE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_race)],
            TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_time)],
            DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_date)],
            GPX: [MessageHandler(filters.Document.ALL, get_gpx)],
            CONFIRM: [
                CallbackQueryHandler(confirm, pattern="^confirm_"),
                CallbackQueryHandler(edit_field, pattern="^edit_"),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(conv)
    print("Bot démarré...")
    app.run_polling()

if __name__ == "__main__":
    main()
