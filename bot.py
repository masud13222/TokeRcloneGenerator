import logging
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from config import Config
from rclone_manager import RcloneManager
from token_manager import TokenManager
import os
from drive_manager import DriveManager
import asyncio
import socket
from threading import Thread

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize bot
app = Client(
    "gdrive_bot",
    api_id=Config.API_ID,
    api_hash=Config.API_HASH,
    bot_token=Config.BOT_TOKEN
)

rclone_manager = RcloneManager()
token_manager = TokenManager()

# Initialize drive manager
drive_manager = DriveManager()

# TCP Health Check Server
def tcp_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(('0.0.0.0', 8080))
    server.listen(1)
    
    while True:
        try:
            client, _ = server.accept()
            client.send(b'OK')
            client.close()
        except:
            pass

# Start TCP server in thread
Thread(target=tcp_server, daemon=True).start()

@app.on_message(filters.command("start"))
async def start_command(client, message: Message):
    text = (
        "🤖 স্বাগতম! আমি Google Drive টোকেন জেনারেটর বট।\n\n"
        "📝 কমান্ডসমূহ:\n"
        "/rclone - Rclone কনফিগ জেনারেট করুন\n"
        "/token - Token জেনারেট করুন (credentials.json রিপ্লাই করে)\n"
        "/refresh - Rclone কনফিগ রিফ্রেশ করুন (rclone.conf রিপ্লাই করে)\n"
        "/clone - Drive ফাইল/ফোল্ডার ক্লোন করুন (rclone.conf/token.pickle রিপ্লাই করে)"
    )
    await message.reply_text(text)

@app.on_message(filters.command("rclone"))
async def rclone_command(client, message: Message):
    user_id = message.from_user.id
    
    try:
        auth_url = rclone_manager.get_auth_url(user_id)
        
        text = (
            "1️⃣ নিচের লিংকে ক্লিক করুন\n"
            "2️⃣ Google অ্যাকাউন্ট সিলেক্ট করুন\n" 
            "3️⃣ Allow তে ক্লিক করুন\n"
            "4️⃣ কোড কপি করে /save <code> কমান্ড দিন"
        )
        
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔑 অথরাইজ করুন", url=auth_url)]
        ])
        
        await message.reply_text(text, reply_markup=markup)
        
    except Exception as e:
        await message.reply_text(f"❌ এরর: {str(e)}")

@app.on_message(filters.command("save"))
async def save_command(client, message: Message):
    try:
        user_id = message.from_user.id
        code = message.text.split(None, 1)[1]
        
        # Remove URL parts if present
        if "code=" in code:
            code = code.split("code=")[1].split("&")[0]
        
        success = await rclone_manager.save_token(user_id, code)
        if success:
            # Generate rclone.conf
            config_text = f"""[gdrive]
type = drive
client_id = {Config.RCLONE_CLIENT_ID}
client_secret = {Config.RCLONE_CLIENT_SECRET}
scope = drive
token = {success}
root_folder_id =
team_drive ="""

            with open("rclone.conf", "w") as f:
                f.write(config_text)
                
            await message.reply_document(
                "rclone.conf",
                caption="✅ আপনার rclone.conf ফাইল তৈরি হয়েছে"
            )
            os.remove("rclone.conf")
        else:
            await message.reply_text("❌ টোকেন সেভ করতে ব্যর্থ!")
            
    except Exception as e:
        await message.reply_text(f"❌ এরর: {str(e)}")

@app.on_message(filters.command("token"))
async def token_command(client, message: Message):
    try:
        if message.reply_to_message and message.reply_to_message.document:
            # Create BytesIO object from document
            file_content = await message.reply_to_message.download(in_memory=True)
            
            # Save to temp file
            with open("temp_cred.json", "wb") as f:
                f.write(file_content.getvalue())  # Convert BytesIO to bytes
            
            # Get auth URL
            auth_url = token_manager.get_auth_url("temp_cred.json")
            
            text = (
                "1️⃣ নিচের লিংকে ক্লিক করুন\n"
                "2️⃣ Google অ্যাকাউন্ট সিলেক্ট করুন\n"
                "3️⃣ Allow তে ক্লিক করুন\n"
                "4️⃣ কোড কপি করে /generate <code> কমান্ড দিন"
            )
            
            markup = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔑 অথরাইজ করুন", url=auth_url)]
            ])
            
            await message.reply_text(text, reply_markup=markup)
            
            # Cleanup
            os.remove("temp_cred.json")
            
        else:
            await message.reply_text("❌ credentials.json ফাইল রিপ্লাই করে কমান্ড দিন!")
            
    except Exception as e:
        if os.path.exists("temp_cred.json"):
            os.remove("temp_cred.json")
        await message.reply_text(f"❌ এরর: {str(e)}")

@app.on_message(filters.command("generate"))
async def generate_command(client, message: Message):
    try:
        code = message.text.split(None, 1)[1]
        
        # Extract code from URL if full URL is provided
        if "code=" in code:
            code = code.split("code=")[1].split("&")[0]
        
        success = await token_manager.generate_token(code)
        
        if success:
            await message.reply_document(
                "token.pickle",
                caption="✅ Token জেনারেট হয়েছে!"
            )
            os.remove("token.pickle")
        else:
            await message.reply_text("❌ Token জেনারেট করতে ব্যর্থ!")
            
    except Exception as e:
        await message.reply_text(f"❌ এরর: {str(e)}")

@app.on_message(filters.command("refresh"))
async def refresh_command(client, message: Message):
    try:
        if message.reply_to_message and message.reply_to_message.document:
            # Download rclone.conf
            file_content = await message.reply_to_message.download(in_memory=True)
            
            # Save to temp file
            with open("temp_rclone.conf", "wb") as f:
                f.write(file_content.getvalue())
            
            # Refresh token
            new_token = await rclone_manager.refresh_token("temp_rclone.conf")
            
            if new_token:
                # Generate new rclone.conf
                config_text = f"""[gdrive]
type = drive
client_id = {Config.RCLONE_CLIENT_ID}
client_secret = {Config.RCLONE_CLIENT_SECRET}
scope = drive
token = {new_token}
root_folder_id =
team_drive ="""

                with open("rclone.conf", "w") as f:
                    f.write(config_text)
                    
                await message.reply_document(
                    "rclone.conf",
                    caption="✅ নতুন টোকেন দিয়ে rclone.conf আপডেট করা হয়েছে!"
                )
                os.remove("rclone.conf")
            else:
                await message.reply_text("❌ টোকেন রিফ্রেশ করতে ব্যর্থ!")
                
            # Cleanup
            os.remove("temp_rclone.conf")
            
        else:
            await message.reply_text("❌ rclone.conf ফাইল রিপ্লাই করে কমান্ড দিন!")
            
    except Exception as e:
        if os.path.exists("temp_rclone.conf"):
            os.remove("temp_rclone.conf")
        await message.reply_text(f"❌ এরর: {str(e)}")

@app.on_message(filters.command("clone"))
async def clone_command(client, message: Message):
    try:
        # Check if files are replied
        if not message.reply_to_message or not message.reply_to_message.document:
            await message.reply_text(
                "❌ rclone.conf অথবা token.pickle ফাইল রিপ্লাই করে লিংক দিন!"
            )
            return
            
        # Get command arguments
        args = message.text.split()
        if len(args) < 2:
            await message.reply_text("❌ Google Drive লিংক দিন!")
            return
            
        # Download config file
        file_content = await message.reply_to_message.download(in_memory=True)
        file_name = message.reply_to_message.document.file_name
        
        # Save temp file
        temp_file = "temp_" + file_name
        with open(temp_file, "wb") as f:
            f.write(file_content.getvalue())
            
        # Send status message
        status_msg = await message.reply_text("⏳ ক্লোনিং শুরু হচ্ছে...")
        
        # Clone file/folder
        result = await drive_manager.clone_file(
            url=args[1],
            rclone_conf=temp_file if file_name.endswith('.conf') else None,
            token_pickle=temp_file if file_name.endswith('.pickle') else None
        )
        
        if result:
            await status_msg.edit_text(
                f"✅ ক্লোনিং সম্পন্ন হয়েছে!\n\n"
                f"📁 নাম: {result['name']}\n"
                f"🔗 লিংক: {result['link']}"
            )
        else:
            await status_msg.edit_text("❌ ক্লোনিং ব্যর্থ হয়েছে!")
            
        # Cleanup
        os.remove(temp_file)
        
    except Exception as e:
        await message.reply_text(f"❌ এরর: {str(e)}")

app.run() 