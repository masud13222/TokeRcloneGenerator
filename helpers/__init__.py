from config import Config

def is_admin(update):
    # Check if user is admin
    user_id = str(update.effective_user.id)
    if user_id in Config.ADMIN_USERS:
        return True
        
    # Check if chat is authorized
    chat_id = update.effective_chat.id
    if chat_id in Config.AUTHORIZED_CHATS:
        return True
        
    return False

def format_size(size):
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} TB"