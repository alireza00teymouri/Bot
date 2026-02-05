
#!/usr/bin/env python3
import asyncio
import sys

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

TOKEN = "8514527291:AAFT-4Oj0kDVMoEz10gJzQ2P-PBcBIHQtjg"

print("🚀 راه‌اندازی بات...")

async def start_bot():
    from telegram.ext import Application
    from core.app import Router
    
    app = Application.builder().token(TOKEN).build()
    router = Router(app)
    
    if router.register_routes():
        bot = await app.bot.get_me()
        print(f"✅ {bot.first_name} (@{bot.username})")
        print("📡 شروع دریافت پیام‌ها...")
        await app.run_polling()
    else:
        print("❌ خطا در ثبت handlers")

if __name__ == "__main__":
    try:
        asyncio.run(start_bot())
    except KeyboardInterrupt:
        print("\n👋 خداحافظ")