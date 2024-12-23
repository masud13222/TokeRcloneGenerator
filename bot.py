import logging
from dotenv import load_dotenv
load_dotenv()

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes
from config import Config
from helpers.uploader import TelegramUploader, GofileUploader
from helpers.downloader import M3u8Downloader
from helpers import is_admin, format_size
import os
from helpers.rclone_helper import RcloneManager
from collections import defaultdict
from typing import Dict, List
import asyncio
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from helpers.error_manager import ErrorManager
from telegram.error import TimedOut, NetworkError, RetryAfter
import backoff
from http.server import HTTPServer, BaseHTTPRequestHandler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

executor = ThreadPoolExecutor(max_workers=10)  # Allow 10 concurrent tasks

# Create error manager
error_manager = ErrorManager()

# Add retry decorator
def retry_on_telegram_error(func):
    @backoff.on_exception(
        backoff.expo,
        (TimedOut, NetworkError, RetryAfter),
        max_tries=3,
        max_time=30
    )
    async def wrapper(*args, **kwargs):
        return await func(*args, **kwargs)
    return wrapper

# Modify command handlers with retry decorator
@retry_on_telegram_error
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("দুঃখিত, আপনি এই বট ব্যবহার করার অনুমতি পাননি।")
        return
        
    welcome_text = (
        "*🎥 M3U8 ডাউনলোডার বট*\n\n"
        "🔰 *মূল ফিচার:*\n"
        "• যেকোনো M3U8 লিংক ডাউনলোড করুন\n"
        "• BongoBD এবং Chorki ভিডিও সাপোর্ট\n"
        "• টফি ভিডিও ডাউনলোড সাপোর্ট\n\n"
        "📤 *আপলোড অপশন:*\n"
        "• টেলিগ্রাম - ডাইরেক্ট আপলোড\n"
        "• গুগল ড্রাইভ - প্রাইভেট ড্রাইভে আপলোড\n"
        "• GoFile - পাবলিক শেয়ারিং\n\n"
        "📝 *কমান্ড লিস্ট:*\n"
        "• /m3u8 \\- M3U8 লিংক ডাউনলোড\n"
        "• /rclone \\- ড্রাইভ কনফিগার করুন\n\n"
        "👨‍💻 *ডেভেলপার:* @cinemazbd\n"
        "🌟 *ভার্শন:* 2\\.0"
    )
    
    try:
        await update.message.reply_text(welcome_text, parse_mode='MarkdownV2')
    except Exception as e:
        # If markdown fails, send without formatting
        await update.message.reply_text(
            welcome_text.replace('*', '').replace('\\', ''),
            parse_mode=None
        )

@retry_on_telegram_error
async def handle_filename(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("দুঃখিত, আপনি এই বট ব্যবহার করার অনুমতি পাননি।")
        return
        
    # Check if waiting for rclone code
    if context.user_data.get('waiting_rclone_code'):
        response_url = update.message.text.strip()
        try:
            # Extract code from URL
            if "code=" in response_url:
                code = response_url.split("code=")[1].split("&")[0]
            else:
                code = response_url  # If user directly pasted the code
                
            rclone = RcloneManager()
            await rclone.save_token(update.effective_user.id, code)
            await update.message.reply_text("✅ Google Drive কনফিগারেশন সফল হয়েছে!")
            
            # Show upload options with Rclone
            keyboard = [
                [
                    InlineKeyboardButton("📤 Telegram", callback_data='upload_telegram'),
                    InlineKeyboardButton("☁️ GoFile", callback_data='upload_gofile'),
                    InlineKeyboardButton("📁 Drive", callback_data='upload_drive')
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text("পপলোড অপশন বাছাই করুন:", reply_markup=reply_markup)
            
        except Exception as e:
            await update.message.reply_text(f"❌ ত্রুটি: {str(e)}")
        context.user_data['waiting_rclone_code'] = False
        return
        
    # Only process if waiting for filename after /m3u8 command
    if not context.user_data.get('waiting_filename'):
        return  # Ignore normal messages if not waiting for filename
    
    filename = update.message.text.strip()
    url = context.user_data.get('m3u8_url')
    
    if not url:
        await update.message.reply_text("দয়া করে আবার /m3u8 কমান্ড ব্যবহার করুন।")
        return
    
    # Clear waiting state
    context.user_data['waiting_filename'] = False
    
    # Store filename in user_data
    context.user_data['filename'] = filename
    
    # Show all upload options for everyone
    keyboard = [
        [
            InlineKeyboardButton("📤 Telegram", callback_data='upload_telegram'),
            InlineKeyboardButton("☁️ GoFile", callback_data='upload_gofile'),
            InlineKeyboardButton("📁 Drive", callback_data='upload_drive')
        ]
    ]
    
    keyboard.append([InlineKeyboardButton("🔄 নাম পরিবর্তন", callback_data='change_name')])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    msg = await update.message.reply_text(
        f"ফাইল নাম: {filename}\n\nআপলোড অপশন বাছাই করুন:",
        reply_markup=reply_markup
    )

@retry_on_telegram_error
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == 'change_name':
        context.user_data['waiting_filename'] = True
        await query.message.delete()
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="নতুন ফাইলের নাম লিখুন:"
        )
        return
    
    if query.data == 'rclone_default':
        rclone = RcloneManager()
        auth_url = rclone.get_auth_url(update.effective_user.id, use_default=True)
        
        await query.message.edit_text(
            "1. নীচের লিংকে ক্লিক করুন\n"
            "2. Google অ্যাকাউন্ট সিলেক্ট করুন\n"
            "3. Allow তে ক্লিক করুন\n"
            "4. রিডাইরেক্ট URL থেকে code= এর পরের অংশ কপি করে এখানে পেস্ট করুন\n\n"
            f"[অথোরাইজেশন লিংক]({auth_url})",
            parse_mode='Markdown'
        )
        context.user_data['waiting_rclone_code'] = True
        return
        
    action, platform = query.data.split('_')
    url = context.user_data.get('m3u8_url')
    filename = context.user_data.get('filename')
    
    # Delete options message
    await query.message.delete()
    
    if not url:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="দয়া করে আবার /m3u8 কমান্ড ব্যবহার করুন।"
        )
        return
        
    if '.m3u8' not in url:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="দয়া করে একটি সঠিক m3u8 লিংক পাঠান।"
        )
        return
    
    # Send initial status message
    status_message = await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"⏳ প্কক্রিয়াকরণ শুরু হচ্ছে...\n"
             f"👤 ইউজার: {update.effective_user.first_name}\n"
             f"🔄 ইঞ্জিন: {'Telegram' if platform == 'telegram' else 'Drive' if platform == 'drive' else 'GoFile'}"
    )
    
    try:
        # Create downloader
        downloader = M3u8Downloader(
            url, 
            filename, 
            status_message,
            update.effective_user.first_name
        )
        
        # Wait for download to complete
        file_path = await downloader.download()
        
        # Then handle upload based on platform
        if platform == 'drive':
            # Check if drive is configured
            rclone = RcloneManager()
            if not rclone.check_token(update.effective_user.id):
                await status_message.edit_text(
                    "❌ Google Drive কনফিগার করা নেই। /rclone কমান্ড ব্যবহার করুন।"
                )
                return
                
            await handle_drive_upload(update, context, url, filename, status_message, file_path)
        else:
            await handle_other_upload(update, context, url, filename, status_message, platform, file_path)
            
    except Exception as e:
        await status_message.edit_text(f"❌ ত্রুটি: {str(e)}")
        logger.error(f"Error: {str(e)}")

async def handle_drive_upload(update, context, url, filename, status_message, file_path):
    """Handle Drive upload"""
    try:
        rclone = RcloneManager()
        if not rclone.check_token(update.effective_user.id):
            await status_message.edit_text("❌ Google Drive কনফিগার করা নেই। /rclone কমান্ড ব্যবহার করুন।")
            return
            
        try:
            drive_link = await rclone.upload_file(
                file_path=file_path,
                filename=filename,
                status_message=status_message,
                user_id=update.effective_user.id,
                username=update.effective_user.first_name
            )
            
            await status_message.edit_text(
                f"✅ Drive আপলোড সম্পন্ন!\n\n"
                f"🎥 ফাইল: {filename}",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔗 Drive লিংক", url=drive_link)]
                ])
            )
            
            if Config.LOG_CHANNEL:
                try:
                    log_text = (
                        f"#NewDownload\n"
                        f"User: {update.effective_user.mention_html()}\n"
                        f"File: {filename}\n"
                        f"Link: {url}\n"
                        f"Upload: Drive\n"
                        f"Drive Link: {drive_link}"
                    )
                    await context.bot.send_message(
                        chat_id=Config.LOG_CHANNEL,
                        text=log_text,
                        parse_mode='HTML'
                    )
                except Exception as e:
                    logger.error(f"Failed to send log: {e}")
                
        finally:
            if os.path.exists(file_path):
                os.remove(file_path)
                
    except Exception as e:
        error_id = error_manager.log_error(
            user_id=update.effective_user.id,
            error_type="drive_upload",
            error_message=str(e),
            task_info={
                "filename": filename,
                "url": url
            }
        )
        
        short_error = error_manager.get_short_error(str(e))
        await status_message.edit_text(
            f"❌ ত্রুটি: {short_error}\n"
            f"Error ID: {error_id}"
        )
        logger.error(f"Drive upload error: {str(e)}")

async def handle_other_upload(update, context, url, filename, status_message, platform, file_path):
    """Handle other uploads as separate tasks"""
    try:
        if platform == 'telegram':
            uploader = TelegramUploader()
            message = await uploader.upload(
                file_path=file_path,
                status_message=status_message,
                chat_id=update.effective_chat.id
            )
        else:
            uploader = GofileUploader(Config.GOFILE_TOKEN)
            link = await uploader.upload(file_path, status_message)
        
        # Handle logging
        if Config.LOG_CHANNEL:
            try:
                log_text = (
                    f"#NewDownload\n"
                    f"User: {update.effective_user.mention_html()}\n"
                    f"File: {filename}\n"
                    f"Link: {url}\n"
                    f"Upload: {platform.title()}"
                )
                
                # For Telegram uploads, send file to log channel
                if platform == 'telegram':
                    await context.bot.send_video(
                        chat_id=Config.LOG_CHANNEL,
                        video=message.video.file_id,
                        caption=log_text,
                        parse_mode='HTML'
                    )
                else:
                    log_text += f"\n{platform.title()} Link: {link}"
                    await context.bot.send_message(
                        Config.LOG_CHANNEL, 
                        log_text, 
                        parse_mode='HTML'
                    )
            except Exception as e:
                logger.error(f"Failed to send log: {e}")
                
    except Exception as e:
        error_id = error_manager.log_error(
            user_id=update.effective_user.id,
            error_type=f"{platform}_upload",
            error_message=str(e),
            task_info={
                "filename": filename,
                "url": url
            }
        )
        
        short_error = error_manager.get_short_error(str(e))
        await status_message.edit_text(
            f"❌ ত্রুটি: {short_error}\n"
            f"Error ID: {error_id}"
        )
        logger.error(f"Upload error: {str(e)}")

async def set_thumbnail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("Sorry, you are not authorized to use this bot.")
        return
        
    if not update.message.reply_to_message or not update.message.reply_to_message.photo:
        await update.message.reply_text("Reply to an image with /set to set it as thumbnail")
        return
        
    photo = update.message.reply_to_message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    
    os.makedirs("Thumbnails", exist_ok=True)
    thumb_path = f"Thumbnails/{update.effective_user.id}.jpg"
    await file.download_to_drive(thumb_path)
    
    await update.message.reply_text("✅ Custom thumbnail saved successfully!")

@retry_on_telegram_error
async def m3u8_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("দুঃখিত, আপনি এই বট ব্যবহার করার অনুমতি পাননি।")
        return
        
    if not context.args:
        usage_text = (
            "*M3U8 ডাউনলোড কমান্ড*\n\n"
            "ব্যবহার বিধি:\n"
            "`/m3u8 <m3u8_link>`\n\n"
            "উদাহরণ:\n"
            "`/m3u8 https://example.com/video.m3u8`"
        )
        await update.message.reply_text(usage_text, parse_mode='MarkdownV2')
        return
        
    url = context.args[0]
    if '.m3u8' not in url:
        await update.message.reply_text("দয়া করে একটি সঠিক m3u8 লিংক পাঠান।")
        return
        
    # Store URL and set waiting state
    user_data = {
        'm3u8_url': url,
        'waiting_filename': True
    }
    context.user_data.update(user_data)
    
    await update.message.reply_text("ফাইলের নাম লিখুন:")

@retry_on_telegram_error
async def rclone_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("দুঃখিত, আপনি এই বট ব্যবহার করার অনুমতি পাননি।")
        return
        
    rclone = RcloneManager()
    user_id = update.effective_user.id
    
    if rclone.check_token(user_id):
        await update.message.reply_text(
            "✅ আপনার Google Drive অ্যাকাউন্ট কনফিগার করা আছে।\n\n"
            "পুনরায় কনফিগার করতে চাইলে /rclone কমান্ড আবার ব্যবহার করুন।"
        )
        return
        
    keyboard = [
        [InlineKeyboardButton("🔑 ডিফল্ট ক্রেডেনশিয়লল ব্যবহার করুন", callback_data='rclone_default')]
    ]
    
    await update.message.reply_text(
        "*Google Drive কনফিগারেশন*\n\n"
        "1\\. নিজের ক্রেডেনশিয়াল ব্যবহার করতে:\n"
        "   • Google Cloud Console থেকে credentials নিন\n"
        "    `/rclone client\\_id client\\_secret` কমান্ড দিন\n\n"
        "2\\. অথবা নীচের বাটনে ক্লিক করুন ডিফল্ট ক্রেডেনশিয়াল ব্যবহার করতে",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='MarkdownV2'
    )

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b"OK")

def run_health_server():
    server = HTTPServer(('0.0.0.0', 8080), HealthCheckHandler)
    server.serve_forever()

# Add this before main():
def start_health_server():
    thread = threading.Thread(target=run_health_server)
    thread.daemon = True
    thread.start()

def main():
    # Add this line at the start of main()
    start_health_server()
    
    # Create application with custom settings and error handlers
    application = (
        Application.builder()
        .token(Config.BOT_TOKEN)
        .concurrent_updates(True)
        .connection_pool_size(Config.MAX_CONNECTIONS)
        .pool_timeout(Config.TIMEOUT)
        .connect_timeout(Config.TIMEOUT)
        .read_timeout(Config.TIMEOUT)
        .write_timeout(Config.TIMEOUT)
        .build()
    )
    
    # Add error handler
    async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            if isinstance(context.error, TimedOut):
                await update.message.reply_text(
                    "⚠️ কমান্ড টাইমআউট হয়েছে। আবার চেষ্টা করুন।"
                )
            elif isinstance(context.error, NetworkError):
                await update.message.reply_text(
                    "⚠️ নেটওয়ার্ক সমস্যা। আবার চেষ্টা করুন।"
                )
            else:
                logger.error(f"Update {update} caused error {context.error}")
        except:
            pass
            
    application.add_error_handler(error_handler)
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("set", set_thumbnail))
    application.add_handler(CommandHandler("m3u8", m3u8_command))
    application.add_handler(CommandHandler("rclone", rclone_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_filename))
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Run with custom settings
    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        pool_timeout=None,
        drop_pending_updates=True
    )

if __name__ == '__main__':
    main() 