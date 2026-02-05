
from telegram.ext import Application
from core.app import Router
import asyncio
import signal
import sys
import os
import signal
import sys
import asyncio
from typing import Optional
from telegram.ext import Application
from core.app import Router
from dotenv import load_dotenv

"""
bot_manager.py - مدیریت بات تلگرام
"""

import os
import signal
import sys
import asyncio
from typing import Optional

from telegram.ext import Application
from core.app import Router
from dotenv import load_dotenv

load_dotenv()

class BotManager:
    def __init__(self, token: str = None, mode: str = 'polling', 
                 webhook_url: Optional[str] = None):
        self.token = token or os.getenv('BOT_TOKEN')
        if not self.token:
            raise ValueError("❌ توکن بات یافت نشد.")
        
        self.mode = mode
        self.webhook_url = webhook_url
        self.app = self._build_app()
        self.router = Router(self.app)
        self._setup_graceful_shutdown()
    
    def _build_app(self) -> Application:
        return Application.builder().token(self.token).build()
    
    def _setup_graceful_shutdown(self):
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        print(f"\n🛑 دریافت سیگنال توقف ({signum})...")
        
        # ذخیره داده‌ها
        if hasattr(self, 'router') and hasattr(self.router, 'data_manager'):
            self.router.data_manager.save_all()
        
        # توقف بات
        if self.app.running:
            self.app.stop()
            self.app.shutdown()
        
        print("✅ بات با موفقیت متوقف شد")
        sys.exit(0)
    
    def start(self):
        print("=" * 50)
        print("🤖 ربات دانلود و پرداخت USDT")
        print(f"📡 حالت اجرا: {self.mode.upper()}")
        print("=" * 50)
        
        # ثبت مسیرها
        if not self.router.register_routes():
            print("❌ خطا در ثبت مسیرها")
            return
        
        print("✅ Router آماده است")
        print("🚀 شروع به کار بات...")
        
        try:
            if self.mode == 'webhook' and self.webhook_url:
                self._start_webhook()
            else:
                self._start_polling()
                
        except KeyboardInterrupt:
            print("\n🛑 توقف بات توسط کاربر...")
        except Exception as e:
            print(f"❌ خطا در اجرای بات: {e}")
            import traceback
            traceback.print_exc()
    
    def _start_polling(self):
        print("📡 استفاده از روش Polling...")
        
        poll_params = {
            'drop_pending_updates': True,
            'allowed_updates': ['message', 'callback_query'],
            'close_loop': False,
            'poll_interval': 0.5,
            'timeout': 10
        }
        
        self.app.run_polling(**poll_params)
    
    def _start_webhook(self):
        print(f"🌐 استفاده از Webhook: {self.webhook_url}")
        
        webhook_params = {
            'listen': '0.0.0.0',
            'port': int(os.getenv('PORT', 8443)),
            'url_path': self.token,
            'webhook_url': f"{self.webhook_url}/{self.token}",
            'drop_pending_updates': True
        }
        
        self.app.run_webhook(**webhook_params)
    
    def stop(self):
        print("🛑 درخواست توقف دستی بات...")
        self._signal_handler(signal.SIGINT, None)