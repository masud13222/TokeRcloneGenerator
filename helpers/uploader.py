import os
import time
import math
import logging
import aiohttp
import asyncio
from pyrogram import Client
from config import Config

class TelegramUploader:
    def __init__(self):
        self._last_uploaded = 0
        self._start_time = None
        self._client = None
        self._flood_wait_time = 0
        
    def humanbytes(self, size):
        if not size:
            return ""
        power = 2**10
        n = 0
        Dic_powerN = {0: ' ', 1: 'Ki', 2: 'Mi', 3: 'Gi', 4: 'Ti'}
        while size > power:
            size /= power
            n += 1
        return str(round(size, 2)) + " " + Dic_powerN[n] + 'B'

    def TimeFormatter(self, milliseconds: int) -> str:
        seconds, milliseconds = divmod(int(milliseconds), 1000)
        minutes, seconds = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        days, hours = divmod(hours, 24)
        tmp = ((str(days) + "d, ") if days else "") + \
            ((str(hours) + "h, ") if hours else "") + \
            ((str(minutes) + "m, ") if minutes else "") + \
            ((str(seconds) + "s, ") if seconds else "")
        return tmp[:-2]

    async def progress(self, current, total, message, start):
        if self._start_time is None:
            self._start_time = start
            
        now = time.time()
        diff = now - start
        
        if current == total:
            self._last_uploaded = 0
        else:
            self._last_uploaded = current

        if round(diff % 3.00) == 0 or current == total:
            percentage = current * 100 / total
            speed = current / diff if diff > 0 else 0
            elapsed_time = round(diff) * 1000
            time_to_completion = round((total - current) / speed) * 1000 if speed > 0 else 0
            
            progress = "[{0}{1}]\nProgress: {2}%\n".format(
                ''.join(["█" for i in range(math.floor(percentage / 5))]),
                ''.join(["░" for i in range(20 - math.floor(percentage / 5))]),
                round(percentage, 2))
            
            tmp = progress + "{0} of {1}\nSpeed: {2}/s\nETA: {3}\n".format(
                self.humanbytes(current),
                self.humanbytes(total),
                self.humanbytes(speed),
                self.TimeFormatter(time_to_completion if time_to_completion != float('inf') else 0)
            )
            
            try:
                await message.edit_text(f"Uploading...\n{tmp}")
            except:
                pass

    async def _ensure_client(self):
        if self._client is None:
            self._client = Client(
                "bot",
                api_id=Config.API_ID,
                api_hash=Config.API_HASH,
                bot_token=Config.BOT_TOKEN,
                in_memory=True
            )
        
        if not self._client.is_connected:
            await self._client.start()
            
    async def _close_client(self):
        if self._client and self._client.is_connected:
            await self._client.stop()
            self._client = None

    async def upload(self, file_path, status_message, chat_id):
        try:
            if not os.path.exists(file_path):
                raise Exception("File not found")
            
            if not os.path.getsize(file_path):
                raise Exception("File is empty")

            # Initialize and connect client
            await self._ensure_client()

            try:
                # Check if we need to wait due to previous flood
                if self._flood_wait_time > 0:
                    await status_message.edit_text(
                        f"⏳ Flood wait: {self._flood_wait_time} seconds remaining..."
                    )
                    await asyncio.sleep(self._flood_wait_time)
                    self._flood_wait_time = 0

                # Add delay between uploads
                if time.time() - self._last_uploaded < 5:
                    await asyncio.sleep(5)

                # Send video with retry on flood wait
                try:
                    message = await self._client.send_video(
                        chat_id=chat_id,
                        video=file_path,
                        caption=os.path.basename(file_path),
                        supports_streaming=True,
                        progress=self.progress,
                        progress_args=(status_message, time.time())
                    )
                except Exception as e:
                    if "FLOOD_WAIT_X" in str(e):
                        wait_time = int(str(e).split()[6])  # Extract wait time
                        self._flood_wait_time = wait_time
                        await status_message.edit_text(
                            f"⏳ Rate limit exceeded. Waiting {wait_time} seconds..."
                        )
                        await asyncio.sleep(wait_time)
                        # Retry upload
                        message = await self._client.send_video(
                            chat_id=chat_id,
                            video=file_path,
                            caption=os.path.basename(file_path),
                            supports_streaming=True,
                            progress=self.progress,
                            progress_args=(status_message, time.time())
                        )
                    else:
                        raise e

                self._last_uploaded = time.time()
                
                # Show completion message
                await status_message.edit_text(
                    f"✅ Upload Complete!\n\n"
                    f"File: {os.path.basename(file_path)}\n"
                    f"Size: {self.humanbytes(os.path.getsize(file_path))}"
                )
                
                return message
                
            finally:
                # Close client after upload
                await self._close_client()
                
        except Exception as e:
            logging.error(f"Upload error: {str(e)}")
            # Make sure to close client on error
            await self._close_client()
            raise Exception(f"Upload error: {str(e)}")

class GofileUploader:
    def __init__(self, token):
        self.token = token
        
    async def upload(self, file_path, status_message):
        try:
            await status_message.edit_text("⏳ GoFile সার্ভার খোঁজা হচ্ছে...")
            
            headers = {
                'accept': 'application/json',
                'Authorization': f'Bearer {self.token}' if self.token else None
            }
            
            # Get best server
            async with aiohttp.ClientSession() as session:
                async with session.get("https://api.gofile.io/servers", headers=headers) as resp:
                    if resp.status != 200:
                        raise Exception("Server error")
                    server_data = await resp.json()
                    if not server_data.get("data", {}).get("servers"):
                        raise Exception("No servers available")
                    server = server_data["data"]["servers"][0]["name"]
                
                await status_message.edit_text("⬆️ GoFile এ আপলোড হচ্ছে...")
                
                # Upload file
                url = f"https://{server}.gofile.io/contents/uploadFile"
                
                data = aiohttp.FormData()
                data.add_field('file', 
                             open(file_path, 'rb'),
                             filename=os.path.basename(file_path))
                if self.token:
                    data.add_field('token', self.token)
                    
                async with session.post(url, data=data) as resp:
                    if resp.status != 200:
                        raise Exception("Upload failed")
                    upload_data = await resp.json()
                    if upload_data.get("status") != "ok":
                        raise Exception(upload_data.get("message", "Upload failed"))
                    
                    await status_message.edit_text(
                        f"✅ GoFile আপলোড সম্পন্ন!\n\n"
                        f"🔗 লিংক: {upload_data['data']['downloadPage']}"
                    )
                    return upload_data["data"]["downloadPage"]
                    
        except Exception as e:
            raise Exception(f"Gofile আপলোড ত্রুটি: {str(e)}")