import logging
import qrcode
import time
from io import BytesIO
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from telegram import Update, BotCommand
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, ConversationHandler
import asyncio

# ==================== CONFIGURATION ====================
BOT_OWNER_NAME = "Alex"
BOT_OWNER_ID = 123456789  # Replace with actual owner ID
BOT_VERSION = "1.0.0"
BOT_NAME = "WhatsApp Pairing Bot"
TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"  # Replace with your token
# ======================================================

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Conversation states
WAITING_FOR_PAIRING, WAITING_FOR_CODE = range(2)

# Store user sessions
user_sessions = {}

class WhatsAppPairer:
    """Handles WhatsApp Web pairing via Selenium"""
    
    def __init__(self, user_id):
        self.user_id = user_id
        self.driver = None
        self.qr_code_image = None
        
    def initialize_driver(self):
        """Initialize Selenium WebDriver"""
        options = webdriver.ChromeOptions()
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        
        self.driver = webdriver.Chrome(options=options)
        self.driver.get('https://web.whatsapp.com')
        logger.info(f"[User {self.user_id}] WebDriver initialized")
        
    def capture_qr_code(self):
        """Capture QR code from WhatsApp Web"""
        try:
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'canvas[aria-label="Scan this QR code to link a device!"]'))
            )
            
            qr_element = self.driver.find_element(By.CSS_SELECTOR, 'canvas[aria-label="Scan this QR code to link a device!"]')
            qr_location = qr_element.location
            qr_size = qr_element.size
            
            screenshot = self.driver.get_screenshot_as_png()
            
            # Crop QR code from screenshot
            from PIL import Image
            img = Image.open(BytesIO(screenshot))
            left = qr_location['x']
            top = qr_location['y']
            right = left + qr_size['width']
            bottom = top + qr_size['height']
            
            self.qr_code_image = img.crop((left, top, right, bottom))
            logger.info(f"[User {self.user_id}] QR code captured")
            return True
            
        except Exception as e:
            logger.error(f"[User {self.user_id}] Error capturing QR code: {e}")
            return False
    
    def wait_for_authentication(self, timeout=60):
        """Wait for user to scan QR code and authenticate"""
        try:
            WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'div[data-testid="chatlist-container"]'))
            )
            logger.info(f"[User {self.user_id}] Authentication successful")
            return True
        except Exception as e:
            logger.error(f"[User {self.user_id}] Authentication timeout: {e}")
            return False
    
    def get_pairing_code(self):
        """Extract 6-digit pairing code after successful authentication"""
        try:
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'div[data-testid="chatlist-container"]'))
            )
            
            self.driver.find_element(By.CSS_SELECTOR, 'button[aria-label="Menu"]').click()
            time.sleep(1)
            
            self.driver.find_element(By.XPATH, "//div[contains(text(), 'Settings')]").click()
            time.sleep(1)
            
            self.driver.find_element(By.XPATH, "//div[contains(text(), 'Linked Devices')]").click()
            time.sleep(2)
            
            pairing_code_element = self.driver.find_element(By.CSS_SELECTOR, 'span[data-testid="pairing-code"]')
            pairing_code = pairing_code_element.text
            
            logger.info(f"[User {self.user_id}] Pairing code extracted: {pairing_code}")
            return pairing_code
            
        except Exception as e:
            logger.error(f"[User {self.user_id}] Error getting pairing code: {e}")
            return None
    
    def cleanup(self):
        """Clean up resources"""
        if self.driver:
            self.driver.quit()
            logger.info(f"[User {self.user_id}] Driver cleaned up")

# ==================== COMMAND HANDLERS ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command"""
    user_name = update.effective_user.first_name
    await update.message.reply_text(
        f"👋 Welcome, {user_name}!\n\n"
        f"🤖 <b>{BOT_NAME}</b>\n"
        f"📌 Owner: {BOT_OWNER_NAME}\n"
        f"📊 Version: {BOT_VERSION}\n\n"
        f"I'll help you pair WhatsApp Web and get your 6-digit pairing code.\n\n"
        f"Use /pair to start the pairing process.\n"
        f"Use /help to see all available commands.",
        parse_mode="HTML"
    )

async def pair_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Initiate WhatsApp pairing"""
    user_id = update.effective_user.id
    
    if user_id in user_sessions:
        await update.message.reply_text("❌ You already have an active pairing session. Use /cancel to stop it.")
        return WAITING_FOR_PAIRING
    
    await update.message.reply_text(
        "⏳ Initializing WhatsApp Web connection...\n"
        "This may take a few moments."
    )
    
    try:
        pairer = WhatsAppPairer(user_id)
        pairer.initialize_driver()
        
        if not pairer.capture_qr_code():
            await update.message.reply_text("❌ Failed to capture QR code. Please try again.")
            pairer.cleanup()
            return ConversationHandler.END
        
        qr_bio = BytesIO()
        pairer.qr_code_image.save(qr_bio, format='PNG')
        qr_bio.seek(0)
        
        await update.message.reply_photo(
            photo=qr_bio,
            caption="📱 Scan this QR code with your phone to pair WhatsApp.\n"
                    "Waiting for authentication...",
            parse_mode="HTML"
        )
        
        user_sessions[user_id] = pairer
        
        context.user_data['pairing_task'] = asyncio.create_task(
            wait_for_auth_async(update, context, user_id, pairer)
        )
        
        return WAITING_FOR_PAIRING
        
    except Exception as e:
        logger.error(f"Error during pairing initialization: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}")
        return ConversationHandler.END

async def wait_for_auth_async(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id, pairer):
    """Wait for authentication in background"""
    try:
        if pairer.wait_for_authentication(timeout=60):
            await update.message.reply_text("✅ Authentication successful! Extracting pairing code...")
            
            code = pairer.get_pairing_code()
            if code:
                await update.message.reply_text(
                    f"🔐 <b>Your 6-Digit Pairing Code:</b>\n\n"
                    f"<code>{code}</code>\n\n"
                    f"Keep this code safe and private!",
                    parse_mode="HTML"
                )
            else:
                await update.message.reply_text("⚠️ Authentication successful, but couldn't extract pairing code automatically.")
        else:
            await update.message.reply_text("❌ QR code scan timeout. Session expired.")
    
    except Exception as e:
        logger.error(f"Error in authentication wait: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}")
    
    finally:
        pairer.cleanup()
        if user_id in user_sessions:
            del user_sessions[user_id]

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel pairing session"""
    user_id = update.effective_user.id
    
    if user_id in user_sessions:
        pairer = user_sessions[user_id]
        pairer.cleanup()
        del user_sessions[user_id]
        await update.message.reply_text("❌ Pairing session cancelled.")
    else:
        await update.message.reply_text("No active pairing session.")
    
    return ConversationHandler.END

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Help command"""
    await update.message.reply_text(
        "<b>📖 How to use this bot:</b>\n\n"
        "1️⃣ /pair - Start WhatsApp pairing\n"
        "2️⃣ Scan the QR code with your phone\n"
        "3️⃣ Get your 6-digit pairing code\n"
        "4️⃣ /cancel - Cancel current session\n\n"
        "<b>⚠️ Important:</b>\n"
        "• You need Chrome/Chromium browser installed\n"
        "• Keep your pairing code private\n"
        "• Session expires after 60 seconds if QR not scanned",
        parse_mode="HTML"
    )

async def info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bot information command"""
    await update.message.reply_text(
        f"<b>ℹ️ Bot Information</b>\n\n"
        f"<b>Bot Name:</b> {BOT_NAME}\n"
        f"<b>Owner:</b> {BOT_OWNER_NAME}\n"
        f"<b>Version:</b> {BOT_VERSION}\n"
        f"<b>Purpose:</b> WhatsApp Web pairing assistant\n\n"
        f"<b>Features:</b>\n"
        f"✅ QR code generation\n"
        f"✅ Real-time authentication\n"
        f"✅ 6-digit pairing code extraction\n"
        f"✅ Secure session management\n",
        parse_mode="HTML"
    )

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check bot status"""
    user_id = update.effective_user.id
    has_session = "🟢 Active" if user_id in user_sessions else "🔴 No active session"
    
    await update.message.reply_text(
        f"<b>🤖 Bot Status</b>\n\n"
        f"<b>Bot:</b> ✅ Online\n"
        f"<b>Your Session:</b> {has_session}\n"
        f"<b>Total Active Sessions:</b> {len(user_sessions)}\n\n"
        f"<b>Quick Commands:</b>\n"
        f"/pair - Start pairing\n"
        f"/cancel - Cancel session\n"
        f"/help - Show help",
        parse_mode="HTML"
    )

async def contact_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Contact owner"""
    await update.message.reply_text(
        f"<b>📞 Contact Owner</b>\n\n"
        f"<b>Owner Name:</b> {BOT_OWNER_NAME}\n"
        f"<b>Owner ID:</b> <code>{BOT_OWNER_ID}</code>\n\n"
        f"For support or issues, please reach out to the bot owner.",
        parse_mode="HTML"
    )

async def commands_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all available commands"""
    await update.message.reply_text(
        "<b>📋 All Available Commands</b>\n\n"
        "<b>/start</b> - Start the bot and see welcome message\n"
        "<b>/pair</b> - Initiate WhatsApp pairing process\n"
        "<b>/cancel</b> - Cancel current pairing session\n"
        "<b>/help</b> - Show detailed help information\n"
        "<b>/info</b> - Display bot information and features\n"
        "<b>/status</b> - Check bot and session status\n"
        "<b>/contact</b> - Get owner contact information\n"
        "<b>/commands</b> - List all available commands\n"
        "<b>/about</b> - About this bot\n"
        "<b>/settings</b> - User settings\n",
        parse_mode="HTML"
    )

async def about_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """About bot"""
    await update.message.reply_text(
        f"<b>ℹ️ About {BOT_NAME}</b>\n\n"
        f"This is a specialized Telegram bot designed to simplify WhatsApp Web pairing.\n\n"
        f"<b>What it does:</b>\n"
        f"• Generates QR codes for WhatsApp Web authentication\n"
        f"• Monitors the pairing process in real-time\n"
        f"• Extracts 6-digit security codes automatically\n"
        f"• Manages secure user sessions\n\n"
        f"<b>Technology Stack:</b>\n"
        f"• Python 3.8+\n"
        f"• Selenium WebDriver\n"
        f"• python-telegram-bot\n"
        f"• Chrome/Chromium\n\n"
        f"<b>Security Notes:</b>\n"
        f"• All sessions are user-isolated\n"
        f"• Pairing codes are temporary\n"
        f"• Data is not stored permanently\n",
        parse_mode="HTML"
    )

async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Settings command"""
    user_id = update.effective_user.id
    await update.message.reply_text(
        f"<b>⚙️ User Settings</b>\n\n"
        f"<b>Your User ID:</b> <code>{user_id}</code>\n"
        f"<b>Username:</b> @{update.effective_user.username or 'Not set'}\n"
        f"<b>First Name:</b> {update.effective_user.first_name}\n\n"
        f"<b>Notification Settings:</b>\n"
        f"• Session alerts: ✅ Enabled\n"
        f"• Status updates: ✅ Enabled\n",
        parse_mode="HTML"
    )

async def set_bot_commands(application: Application):
    """Set bot commands in Telegram"""
    commands = [
        BotCommand("start", "Start the bot"),
        BotCommand("pair", "Start WhatsApp pairing"),
        BotCommand("cancel", "Cancel current session"),
        BotCommand("help", "Show help information"),
        BotCommand("info", "Bot information"),
        BotCommand("status", "Check bot status"),
        BotCommand("contact", "Contact owner"),
        BotCommand("commands", "List all commands"),
        BotCommand("about", "About this bot"),
        BotCommand("settings", "User settings"),
    ]
    await application.bot.set_my_commands(commands)
    logger.info("Bot commands set successfully")

def main():
    """Start the bot"""
    
    # Create the Application
    application = Application.builder().token(TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("pair", pair_command))
    application.add_handler(CommandHandler("cancel", cancel_command))
    application.add_handler(CommandHandler("info", info_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("contact", contact_command))
    application.add_handler(CommandHandler("commands", commands_command))
    application.add_handler(CommandHandler("about", about_command))
    application.add_handler(CommandHandler("settings", settings_command))
    
    # Set bot commands on startup
    application.post_init = set_bot_commands
    
    logger.info(f"Starting {BOT_NAME} - Owner: {BOT_OWNER_NAME}")
    
    # Start the Bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()