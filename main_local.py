
#!/usr/bin/env python3

import os
import sys
from dotenv import load_dotenv
from core.bot_manager import BotManager
"""
main_local.py - اجرا روی PC (کاربران رایگان)
"""

import os
import sys
from dotenv import load_dotenv
from core.bot_manager import BotManager

load_dotenv()

def main():
    TOKEN = os.getenv('BOT_TOKEN')
    ADMIN_ID = os.getenv('ADMIN_ID', 6102531955)
    
    print("=" * 50)
    print("🤖 بات دانلود و پرداخت USDT")
    print(f"👤 آیدی ادمین: {ADMIN_ID}")
    print("=" * 50)
    
    if not TOKEN:
        print("❌ توکن بات تنظیم نشده است!")
        print("لطفاً فایل .env را ایجاد کنید:")
        print("BOT_TOKEN=8514527291:AAFT-4Oj0kDVMoEz10gJzQ2P-PBcBIHQtjg")
        print("ADMIN_ID=6102531955")
        print("USDT_WALLET=آدرس_کیف_پول")
        print("SUPPORT_USERNAME=@username")
        return
    
    try:
        bot = BotManager(token=TOKEN, mode='polling')
        print("✅ BotManager ایجاد شد")
        print("⏳ در حال شروع بات...")
        bot.start()
    except KeyboardInterrupt:
        print("\n👋 بات توسط کاربر متوقف شد")
    except Exception as e:
        print(f"❌ خطا در اجرای بات: {e}")
        print("\n🔧 راه‌حل‌های احتمالی:")
        print("1. توکن را در .env تنظیم کنید")
        print("2. اتصال اینترنت را چک کنید")
        print("3. از VPN استفاده کنید (اگر در ایران هستید)")
        print("4. کتابخانه‌ها را آپدیت کنید:")
        print("   pip install --upgrade python-telegram-bot python-dotenv")


if __name__ == "__main__":
    main()