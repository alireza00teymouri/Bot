
import os
import nest_asyncio
import asyncio
from dotenv import load_dotenv
from core.bot_manager import BotManager

import os
from telegram.ext import Application, CommandHandler

def main():
    TOKEN = "8514527291:AAFT-4Oj0kDVMoEz10gJzQ2P-PBcBIHQtjg"  # توکن واقعی خود را قرار دهید
    
    print("🤖 شروع ربات...")
    
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", lambda u,c: u.message.reply_text("سلام!")))
    
    print("✅ ربات فعال شد")
    app.run_polling()

if __name__ == "__main__":
    main()