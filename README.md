# Google Drive Token Generator Bot

A Telegram bot to generate rclone.conf and token.pickle files for Google Drive access.

## Features
- Generate rclone.conf file
- Generate token.pickle file
- Refresh rclone tokens
- Clone Drive files/folders

## Commands
- `/start` - Start the bot
- `/rclone` - Generate rclone config
- `/save` - Save rclone authorization code
- `/token` - Generate token (Reply with credentials.json)
- `/generate` - Generate token.pickle from auth code
- `/refresh` - Refresh rclone config (Reply with rclone.conf)
- `/clone` - Clone Drive files (Reply with rclone.conf/token.pickle)

## Deploy to Koyeb

### Prerequisites
- Telegram Bot Token from [@BotFather](https://t.me/BotFather)
- API ID and Hash from [my.telegram.org](https://my.telegram.org)

### Deploy Steps
1. Fork this repository
2. Create new app on [Koyeb](https://app.koyeb.com)
3. Select GitHub repository
4. Add Environment Variables:
   ```
   API_ID=your_api_id
   API_HASH=your_api_hash
   BOT_TOKEN=your_bot_token
   ```
5. Deploy!

## Local Development
1. Clone repository:
   ```bash
   git clone https://github.com/yourusername/gdrive-token-bot
   cd gdrive-token-bot
   ```

2. Install requirements:
   ```bash
   pip install -r requirements.txt
   ```

3. Set environment variables:
   ```bash
   export API_ID=your_api_id
   export API_HASH=your_api_hash
   export BOT_TOKEN=your_bot_token
   ```

4. Run bot:
   ```bash
   python bot.py
   ```

## Usage
1. Start bot and send `/rclone` to generate rclone.conf
2. Or send `/token` with credentials.json to generate token.pickle
3. Use generated files with rclone/scripts

## Credits
- [Pyrogram](https://docs.pyrogram.org)
- [Google Drive API](https://developers.google.com/drive/api)
- [Rclone](https://rclone.org)

## License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details 