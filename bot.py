# ====== IMPORTS ====== #
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ConversationHandler,  # Added here
    ContextTypes
)
import logging
import random
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials
import logging
import random
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
import gspread
from google.oauth2.service_account import Credentials
from pathlib import Path
from googleapiclient.http import MediaFileUpload
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from pathlib import Path

# ====== BOT STATES ====== #
NEW_SHIPMENT, GET_NAME, GET_ADDRESS, UPLOAD_PHOTO = range(4)

# ====== CONFIG ====== #
TOKEN = "7753709164:AAG9G373Et77PYiL7vDrihMfFEKrYSSIAdg"  # From @BotFather
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
DRIVE_FOLDER_ID = "1E84DGoS772HZBqhwxGpUkeDi5jjYk2LU"  # Replace with your folder ID
PHOTO_DIR = Path("shipment_photos")
PHOTO_DIR.mkdir(exist_ok=True)

# ====== GOOGLE SETUP ====== #
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
CREDS = Credentials.from_service_account_file("credentials.json", scopes=SCOPES)
gc = gspread.authorize(CREDS)
sheet = gc.open("ShipmentTracker").sheet1

# ====== BOT MENUS ====== #
MAIN_MENU = [
    [InlineKeyboardButton("New Shipment", callback_data="new_shipment")],
    [InlineKeyboardButton("View Shipments", callback_data="view_shipments")],
    [InlineKeyboardButton("Help", callback_data="help")]
]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send main menu"""
    await update.message.reply_text(
        "📦 Shipment Tracker",
        reply_markup=InlineKeyboardMarkup(MAIN_MENU)
    )

def generate_id():
    return f"{datetime.now().strftime('%m%d%y')}-{random.randint(100, 999)}"

# ====== DRIVE UPLOAD ====== #
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from pathlib import Path

# Initialize Drive service
drive_service = build("drive", "v3", credentials=CREDS)

def upload_to_drive(file_path: Path):
    """Upload a file to Google Drive and return its URL"""
    file_metadata = {
        "name": file_path.name,
        "parents": ["1E84DGoS772HZBqhwxGpUkeDi5jjYk2LU"]  # Replace with your folder ID
    }
    media = MediaFileUpload(file_path, mimetype="image/jpeg")
    uploaded = drive_service.files().create(
        body=file_metadata,
        media_body=media,
        fields="id"
    ).execute()
    return f"https://drive.google.com/uc?id={uploaded['id']}"

async def new_shipment_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Initiate new shipment"""
    query = update.callback_query
    await query.answer()
    context.user_data.clear()
    context.user_data["shipment_id"] = generate_id()
    await query.edit_message_text(f"🆕 Shipment ID: {context.user_data['shipment_id']}\nEnter customer name:")
    return GET_NAME  # Next state

async def handle_customer_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Store name and ask for address"""
    context.user_data["customer_name"] = update.message.text
    await update.message.reply_text("🏠 Enter customer address:")
    return 2  # Next state

async def handle_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Store address and finish"""
    context.user_data["address"] = update.message.text
    sheet.append_row([
        context.user_data["shipment_id"],
        context.user_data["customer_name"],
        context.user_data["address"],
        "Pending Review",
        datetime.now().isoformat()
    ])
    await update.message.reply_text("✅ Shipment saved!", reply_markup=InlineKeyboardMarkup(MAIN_MENU))
    return -1  # End conversation

async def handle_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Store address and ask for photos"""
    context.user_data["address"] = update.message.text
    await update.message.reply_text("📸 Upload photos (max 2) or type /done to finish")
    return UPLOAD_PHOTO  # Next state

# ====== PHOTO HANDLING ====== #
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle photo uploads"""
    if "photos" not in context.user_data:
        context.user_data["photos"] = []
    
    # Download photo
    photo = await update.message.photo[-1].get_file()
    photo_path = Path(f"shipment_photos/{context.user_data['shipment_id']}_{len(context.user_data['photos'])}.jpg")
    await photo.download_to_drive(photo_path)
    
    # Upload to Drive
    try:
        drive_url = upload_to_drive(photo_path)
        context.user_data["photos"].append(drive_url)
    except Exception as e:
        await update.message.reply_text(f"❌ Upload failed: {str(e)}")
        return UPLOAD_PHOTO
    
    # Check if max photos reached
    if len(context.user_data["photos"]) >= 2:
        await finish_shipment(update, context)
        return -1  # End conversation
    
    await update.message.reply_text("📸 Photo received! Send another or type /done to finish")
    return UPLOAD_PHOTO

async def finish_shipment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Save shipment data and return to main menu"""
    sheet.append_row([
        context.user_data["shipment_id"],
        context.user_data["customer_name"],
        context.user_data["address"],
        ", ".join(context.user_data["photos"]),
        "Pending Review",
        datetime.now().isoformat()
    ])
    await update.message.reply_text(
        f"✅ Shipment {context.user_data['shipment_id']} saved!\n"
        f"{len(context.user_data['photos'])} photos uploaded",
        reply_markup=InlineKeyboardMarkup(MAIN_MENU)
    )
    return -1  # End conversation

if __name__ == "__main__":
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(new_shipment_start, pattern="^new_shipment$")],
        states={
            1: [MessageHandler(filters.TEXT, handle_customer_name)],
            2: [MessageHandler(filters.TEXT, handle_address)]
        },
        fallbacks=[]
    ))
    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(new_shipment_start, pattern="^new_shipment$")],
        states={
            GET_NAME: [MessageHandler(filters.TEXT, handle_customer_name)],
            GET_ADDRESS: [MessageHandler(filters.TEXT, handle_address)],
            UPLOAD_PHOTO: [
                MessageHandler(filters.PHOTO, handle_photo),
                MessageHandler(filters.TEXT & filters.Regex(r"^/done$"), finish_shipment)
            ]
        },
        fallbacks=[CommandHandler("cancel", lambda u,c: ConversationHandler.END)]
    ))
    app.run_polling()