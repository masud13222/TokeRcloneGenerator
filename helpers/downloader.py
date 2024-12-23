import os
import asyncio
import logging
import time

class M3u8Downloader:
    def __init__(self, url, filename, status_message, username):
        self.url = url
        self.filename = filename
        self.status_message = status_message
        self.username = username
        self.output_file = f"Downloads/{filename}.mp4"
        
    def format_size(self, size):
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.2f} {unit}"
            size /= 1024.0
        return f"{size:.2f} TB"
        
    async def download(self):
        try:
            # Create Downloads directory if not exists
            os.makedirs("Downloads", exist_ok=True)
            
            command = [
                'yt-dlp',
                '--referer', 'https://bongobd.com/',
                '--add-header', 'Origin: https://bongobd.com/',
                '--concurrent-fragments', '10',
                '--buffer-size', '16K',
                '--downloader', 'ffmpeg',
                '--downloader-args', 'ffmpeg_i:-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
                '--newline',
                '--progress',
                '-o', self.output_file,
                self.url
            ]
            
            # Add debug logging
            logging.info(f"Starting download with command: {' '.join(command)}")
            
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            last_update_time = time.time()
            
            while True:
                line = await process.stdout.readline()
                if not line:
                    break
                    
                line = line.decode().strip()
                logging.debug(f"yt-dlp output: {line}")
                
                if '[download]' in line:
                    current_time = time.time()
                    if current_time - last_update_time >= 3:
                        try:
                            # Update status even if we can't parse all info
                            progress_text = (
                                f"📥 ডাউনলোড হচ্ছে...\n\n"
                                f"👤 ইউজার: {self.username}\n"
                                f"📁 ফাইল: {self.filename}\n"
                            )
                            
                            if 'of ~' in line and 'at' in line:
                                try:
                                    parts = line.split()
                                    percentage = parts[1].replace('%', '')
                                    size = ' '.join(parts[3:5]).replace('~', '')
                                    speed = parts[6]
                                    eta = parts[8]
                                    
                                    bar_length = 20
                                    filled_length = int(float(percentage) * bar_length / 100)
                                    bar = '█' * filled_length + '░' * (bar_length - filled_length)
                                    
                                    progress_text += (
                                        f"┌ প্রোগ্রেস: {percentage}%\n"
                                        f"├ {bar}\n"
                                        f"├ সাইজ: {size}\n"
                                        f"├ স্পীড: {speed}\n"
                                        f"└ বাকি সময়: {eta}"
                                    )
                                except:
                                    progress_text += "⏳ ডাউনলোড চলছে..."
                            
                            await self.status_message.edit_text(progress_text)
                            last_update_time = current_time
                        except Exception as e:
                            logging.error(f"Error updating status: {str(e)}")
                            continue
            
            await process.wait()
            
            if process.returncode != 0:
                stderr = await process.stderr.read()
                error_msg = stderr.decode()
                logging.error(f"Download failed with error: {error_msg}")
                raise Exception(f"Download failed: {error_msg}")
            
            if os.path.exists(self.output_file):
                return self.output_file
            else:
                raise Exception("Download failed: File not found")
                
        except Exception as e:
            logging.error(f"Download error: {str(e)}")
            raise Exception(f"Download error: {str(e)}")