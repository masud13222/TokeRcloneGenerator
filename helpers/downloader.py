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
        self.output_file = f"{filename}.mp4"
        
    def format_size(self, size):
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.2f} {unit}"
            size /= 1024.0
        return f"{size:.2f} TB"
        
    async def download(self):
        try:
            command = [
                'yt-dlp',
                '--referer', 'https://bongobd.com/',
                '--add-header', 'Origin: https://bongobd.com/',
                '--concurrent-fragments', '20',
                '--buffer-size', '32K',
                '--downloader', 'ffmpeg',
                '--downloader-args', 'ffmpeg_i:-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
                '--newline',
                '--progress',
                '-o', self.output_file,
                self.url
            ]
            
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            last_update_time = time.time()
            downloading_started = False
            
            while True:
                line = await process.stdout.readline()
                if not line:
                    break
                    
                line = line.decode().strip()
                logging.info(f"yt-dlp output: {line}")
                
                if '[download]' in line:
                    downloading_started = True
                    current_time = time.time()
                    if current_time - last_update_time >= 3:
                        try:
                            progress_text = (
                                f"📥 ডাউনলোড হচ্ছে...\n\n"
                                f"👤 ইউজার: {self.username}\n"
                            )
                            
                            # Extract percentage
                            if '%' in line:
                                try:
                                    percentage = line.split()[1].replace('%', '')
                                    bar_length = 20
                                    filled_length = int(float(percentage) * bar_length / 100)
                                    bar = '█' * filled_length + '░' * (bar_length - filled_length)
                                    progress_text += f"┌ প্রোগ্রেস: {percentage}%\n├ {bar}\n"
                                except:
                                    pass
                            
                            # Extract size
                            if 'of' in line:
                                try:
                                    size_parts = line.split('of')[1].strip().split()[0:2]
                                    size = ' '.join(size_parts)
                                    progress_text += f"├ সাইজ: {size}\n"
                                except:
                                    pass
                            
                            # Extract speed
                            if 'at' in line:
                                try:
                                    speed = line.split('at')[1].strip().split()[0]
                                    if speed != "Unknown":
                                        progress_text += f"├ স্পীড: {speed}/s\n"
                                except:
                                    pass
                            
                            # Extract ETA
                            if 'ETA' in line:
                                try:
                                    eta = line.split('ETA')[1].strip()
                                    if eta != "Unknown":
                                        progress_text += f"└ বাকি সময়: {eta}"
                                except:
                                    pass
                            
                            await self.status_message.edit_text(progress_text)
                            last_update_time = current_time
                            
                        except Exception as e:
                            logging.error(f"Error updating status: {str(e)}")
                            continue
            
            if not downloading_started:
                await self.status_message.edit_text("❌ ডাউনলোড শুরু করতে ব্যর্থ হয়েছে।")
                return None
            
            await process.wait()
            
            if process.returncode != 0:
                stderr = await process.stderr.read()
                raise Exception(f"Download failed: {stderr.decode()}")
            
            if os.path.exists(self.output_file):
                return self.output_file
            else:
                raise Exception("Download failed: File not found")
                
        except Exception as e:
            raise Exception(f"Download error: {str(e)}")