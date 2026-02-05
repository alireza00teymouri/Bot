# در ابتدای app.py
import logging
import asyncio  # این خط باید وجود داشته باشد
from typing import Dict, Set, Optional
from datetime import datetime

"""
app.py - Router اصلی بات تلگرام
نسخه نهایی با دانلود واقعی و رفع مشکلات
"""

import os
import json
import re
import logging
import asyncio
import tempfile
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
from pathlib import Path

from telegram import (
    Update, 
    InlineKeyboardButton, 
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    filters,
    ContextTypes,
)
from dotenv import load_dotenv

# تلاش برای وارد کردن yt-dlp برای دانلود واقعی
try:
    import yt_dlp
    YTDLP_AVAILABLE = True
except ImportError:
    YTDLP_AVAILABLE = False
    print("⚠️ yt-dlp نصب نیست. دانلود واقعی غیرفعال است.")
    print("برای دانلود واقعی: pip install yt-dlp")

# بارگذاری متغیرهای محیطی
load_dotenv()

# تنظیمات لاگ‌گیری
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


# =========================
# Configuration
# =========================

class Config:
    """کلاس پیکربندی"""
    
    # اطلاعات از .env
    BOT_TOKEN = os.getenv('BOT_TOKEN')
    ADMIN_ID = int(os.getenv('ADMIN_ID', 6102531955))
    USDT_WALLET = os.getenv('USDT_WALLET', 'YOUR_WALLET_ADDRESS_HERE')
    SUPPORT_USERNAME = os.getenv('SUPPORT_USERNAME', '@support_username')
    
    # فعال/غیرفعال کردن دانلود واقعی
    ENABLE_REAL_DOWNLOAD = YTDLP_AVAILABLE
    
    # طرح‌های اشتراک
    PLANS = {
        "monthly": {
            "name": "۱ ماهه",
            "duration_days": 30,
            "price_usdt": 5.0,
            "discount_percent": 0,
            "features": [
                "✅ دانلود نامحدود",
                "✅ کیفیت 4K",
                "✅ حذف واترمارک",
                "⏱️ پشتیبانی ۲۴ ساعته"
            ]
        },
        "quarterly": {
            "name": "۳ ماهه",
            "duration_days": 90,
            "price_usdt": 12.0,
            "discount_percent": 20,
            "features": [
                "✅ دانلود نامحدود",
                "✅ کیفیت 4K",
                "✅ حذف واترمارک",
                "🚀 سرعت بالا",
                "⏱️ پشتیبانی ۲۴ ساعته"
            ]
        },
        "semi_annual": {
            "name": "۶ ماهه",
            "duration_days": 180,
            "price_usdt": 20.0,
            "discount_percent": 33,
            "features": [
                "✅ دانلود نامحدود",
                "✅ کیفیت 4K",
                "✅ حذف واترمارک",
                "🚀 سرعت بالا",
                "☁️ ذخیره در ابر",
                "⏱️ پشتیبانی ۲۴ ساعته"
            ]
        },
        "annual": {
            "name": "۱ ساله",
            "duration_days": 365,
            "price_usdt": 35.0,
            "discount_percent": 42,
            "features": [
                "✅ دانلود نامحدود",
                "✅ کیفیت 4K",
                "✅ حذف واترمارک",
                "🚀 سرعت بالا",
                "☁️ ذخیره در ابر",
                "👑 پشتیبانی VIP",
                "🎯 اولویت در صف دانلود"
            ]
        }
    }
    
    # محدودیت‌ها
    MAX_FREE_DOWNLOADS = 3
    
    # پلتفرم‌های پشتیبانی شده
    SUPPORTED_PLATFORMS = [
        'youtube.com', 'youtu.be',
        'instagram.com', 'instagr.am',
        'tiktok.com',
        'twitter.com', 'x.com',
        'facebook.com', 'fb.watch',
        'reddit.com',
        'dailymotion.com',
        'vimeo.com',
        'twitch.tv',
    ]


# =========================
# Data Models & Domain Logic
# =========================

class User:
    """مدل کاربر"""
    
    def __init__(self, user_id: str, username: str, first_name: str, 
                 last_name: str = None):
        self.id = user_id
        self.username = username
        self.first_name = first_name
        self.last_name = last_name
        self.join_date = datetime.now().isoformat()
        self.status = "free"  # free, premium
        self.download_count = 0
        self.premium_expiry = None
    
    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'join_date': self.join_date,
            'status': self.status,
            'download_count': self.download_count,
            'premium_expiry': self.premium_expiry
        }
    
    @classmethod
    def from_dict(cls, data):
        user = cls(
            data['id'],
            data['username'],
            data['first_name'],
            data.get('last_name')
        )
        user.join_date = data.get('join_date', user.join_date)
        user.status = data.get('status', 'free')
        user.download_count = data.get('download_count', 0)
        user.premium_expiry = data.get('premium_expiry')
        return user
    
    def is_premium(self):
        if self.status != 'premium' or not self.premium_expiry:
            return False
        expiry = datetime.fromisoformat(self.premium_expiry)
        return datetime.now() < expiry
    
    def activate_premium(self, days: int):
        self.status = 'premium'
        self.premium_expiry = (datetime.now() + timedelta(days=days)).isoformat()


class DataManager:
    """مدیریت داده‌ها"""
    
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.data_dir.mkdir(exist_ok=True)
        self.users = self._load_data("users.json", {})
        self.downloads = self._load_data("downloads.json", {})
        self.payments = self._load_data("payments.json", {})
        self.premium_users = self._load_data("premium_users.json", {})
        
        # Convert dicts to User objects
        self._users_objs = {}
        for user_id, user_data in self.users.items():
            try:
                self._users_objs[user_id] = User.from_dict(user_data)
            except:
                pass
    
    def _load_data(self, filename: str, default=None):
        try:
            file_path = self.data_dir / filename
            if file_path.exists():
                with open(file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"خطا در بارگذاری {filename}: {e}")
        return default if default is not None else {}
    
    def _save_data(self, filename: str, data):
        try:
            file_path = self.data_dir / filename
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"خطا در ذخیره {filename}: {e}")
    
    def save_all(self):
        """ذخیره تمام داده‌ها"""
        # Convert User objects back to dicts
        self.users = {uid: user.to_dict() for uid, user in self._users_objs.items()}
        
        self._save_data("users.json", self.users)
        self._save_data("downloads.json", self.downloads)
        self._save_data("payments.json", self.payments)
        self._save_data("premium_users.json", self.premium_users)
        logger.debug("💾 داده‌ها ذخیره شدند")
    
    def get_user(self, user_id: str) -> Optional[User]:
        """دریافت کاربر"""
        return self._users_objs.get(str(user_id))
    
    def create_user(self, user: User):
        """ایجاد کاربر جدید"""
        self._users_objs[str(user.id)] = user
        self.save_all()
    
    def update_user(self, user: User):
        """به‌روزرسانی کاربر"""
        self._users_objs[str(user.id)] = user
        self.save_all()
    
    def get_download_count(self, user_id: str) -> int:
        """تعداد دانلودهای کاربر"""
        user = self.get_user(user_id)
        return user.download_count if user else 0
    
    def increment_downloads(self, user_id: str):
        """افزایش تعداد دانلودها"""
        user = self.get_user(user_id)
        if user:
            user.download_count += 1
            self.update_user(user)
    
    def add_payment(self, user_id: str, plan_name: str, amount: float, txid: str):
        """افزودن پرداخت"""
        if user_id not in self.payments:
            self.payments[user_id] = []
        
        self.payments[user_id].append({
            'plan': plan_name,
            'amount': amount,
            'txid': txid,
            'date': datetime.now().isoformat(),
            'status': 'completed'
        })
        
        # افزودن به پریمیوم
        self.premium_users[user_id] = {
            'plan': plan_name,
            'activated': datetime.now().isoformat(),
            'expiry': (datetime.now() + timedelta(days=30)).isoformat()
        }
        
        self.save_all()
    
    def get_system_stats(self) -> Dict:
        """دریافت آمار سیستم"""
        total_users = len(self._users_objs)
        premium_users = sum(1 for u in self._users_objs.values() if u.is_premium())
        total_downloads = sum(u.download_count for u in self._users_objs.values())
        total_payments = sum(len(p) for p in self.payments.values())
        
        # درآمد کل
        total_revenue = 0
        for user_payments in self.payments.values():
            for payment in user_payments:
                total_revenue += payment.get('amount', 0)
        
        # کاربران امروز
        today = datetime.now().date().isoformat()
        today_users = sum(
            1 for user in self._users_objs.values()
            if datetime.fromisoformat(user.join_date).date().isoformat() == today
        )
        
        return {
            'total_users': total_users,
            'premium_users': premium_users,
            'total_downloads': total_downloads,
            'total_payments': total_payments,
            'total_revenue': total_revenue,
            'today_users': today_users
        }


# =========================
# Controllers
# =========================

class BaseController:
    """کنترلر پایه"""
    
    def __init__(self, data_manager: DataManager, config: Config):
        self.data_manager = data_manager
        self.config = config
    
    def get_reply_keyboard(self, user_id: int) -> ReplyKeyboardMarkup:
        """ایجاد Reply Keyboard"""
        keyboard = [
            [KeyboardButton("📥 دانلود ویدئو")],
            [KeyboardButton("👤 حساب کاربری")],
            [KeyboardButton("💎 خرید اشتراک")],
            [KeyboardButton("💳 پرداخت USDT")],
            [KeyboardButton("📋 راهنما")],
            [KeyboardButton("📞 پشتیبانی")]
        ]
        
        if user_id == self.config.ADMIN_ID:
            keyboard.append([KeyboardButton("🛠️ پنل مدیریت")])
        
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    def get_cancel_keyboard(self) -> ReplyKeyboardMarkup:
        """کیبورد لغو"""
        return ReplyKeyboardMarkup([["❌ لغو"]], resize_keyboard=True)
    
    def is_valid_url(self, url: str) -> bool:
        """بررسی اعتبار URL"""
        url_lower = url.lower().strip()
        
        if not re.match(r'^https?://', url_lower):
            return False
        
        for platform in self.config.SUPPORTED_PLATFORMS:
            if platform in url_lower:
                return True
        
        return False
    
    def validate_txid(self, txid: str) -> bool:
        """اعتبارسنجی TXID"""
        if not txid or len(txid) < 10:
            return False
        
        pattern = r'^[a-fA-F0-9]{10,64}$'
        return bool(re.match(pattern, txid))
    
    def get_welcome_text(self, user) -> str:
        """متن خوش‌آمدگویی"""
        user_obj = self.data_manager.get_user(str(user.id))
        
        if user_obj and user_obj.is_premium():
            status = "💎 پریمیوم"
            remaining = "نامحدود"
        else:
            status = "🆓 رایگان"
            downloads = self.data_manager.get_download_count(str(user.id))
            remaining = max(0, self.config.MAX_FREE_DOWNLOADS - downloads)
        
        return f"""🎉 **سلام {user.first_name}!**
🤖 به ربات دانلود و پرداخت USDT خوش آمدید!

✨ **قابلیت‌های اصلی:**
📥 دانلود از +10 پلتفرم
💎 اشتراک پریمیوم
💳 پرداخت امن با USDT

📊 **وضعیت شما:** {status}
🎯 **دانلود باقی‌مانده:** {remaining}

👇 لطفاً از منوی زیر انتخاب کنید:"""


class UserController(BaseController):
    """کنترلر کاربران"""
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """دستور /start"""
        user = update.effective_user
        user_id = str(user.id)
        
        # ثبت کاربر
        if not self.data_manager.get_user(user_id):
            new_user = User(
                user_id=user_id,
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name
            )
            self.data_manager.create_user(new_user)
        
        # ارسال پیام خوش‌آمدگویی
        welcome_text = self.get_welcome_text(user)
        reply_markup = self.get_reply_keyboard(user.id)
        
        await update.message.reply_text(
            welcome_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    async def profile(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """دستور /profile"""
        user = update.effective_user
        user_id = str(user.id)
        
        user_obj = self.data_manager.get_user(user_id)
        
        if user_obj:
            profile_text = self._format_profile_text(user, user_obj)
        else:
            profile_text = self._get_fallback_profile_text(user)
        
        # کیبورد پروفایل
        keyboard = []
        if not user_obj or not user_obj.is_premium():
            keyboard.append([InlineKeyboardButton("💎 خرید اشتراک", callback_data="premium_menu")])
        keyboard.append([InlineKeyboardButton("🔄 بروزرسانی", callback_data="refresh_profile")])
        
        await update.message.reply_text(
            profile_text,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None
        )
    
    def _format_profile_text(self, telegram_user, user_obj: User) -> str:
        """فرمت‌بندی متن پروفایل"""
        status = "💎 پریمیوم" if user_obj.is_premium() else "🆓 رایگان"
        
        text = f"""👤 **حساب کاربری**

🆔 آیدی: `{telegram_user.id}`
👁️ نام: {telegram_user.first_name or 'نامشخص'}
📱 یوزرنیم: @{telegram_user.username or 'ندارد'}

📊 **وضعیت:** {status}"""
        
        if user_obj.premium_expiry:
            expiry = datetime.fromisoformat(user_obj.premium_expiry)
            text += f"\n📅 انقضا: {expiry.strftime('%Y-%m-%d')}"
        
        remaining = max(0, self.config.MAX_FREE_DOWNLOADS - user_obj.download_count)
        
        text += f"""
📥 **تعداد دانلودها:** {user_obj.download_count}
🎯 **دانلود باقی‌مانده:** {remaining} از {self.config.MAX_FREE_DOWNLOADS}
📅 **عضویت:** {user_obj.join_date[:10]}"""
        
        return text
    
    def _get_fallback_profile_text(self, user) -> str:
        """متن پروفایل fallback"""
        return f"""👤 **حساب کاربری**

🆔 آیدی: `{user.id}`
👁️ نام: {user.first_name or 'نامشخص'}
📱 یوزرنیم: @{user.username or 'ندارد'}

📊 **وضعیت:** 🆓 رایگان
📥 **تعداد دانلودها:** 0
🎯 **دانلود باقی‌مانده:** 3 از 3
📅 **عضویت:** {datetime.now().strftime('%Y-%m-%d')}"""
    
    async def refresh_profile(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """بروزرسانی پروفایل"""
        query = update.callback_query
        await query.answer()
        
        await self.profile(update, context)


class DownloadController(BaseController):
    """کنترلر دانلود"""
    
    def __init__(self, data_manager: DataManager, config: Config):
        super().__init__(data_manager, config)
        self.WAITING_LINK = 1
        
        # تنظیمات yt-dlp
        self.ydl_opts = {
            'format': 'best',
            'outtmpl': '%(title)s.%(ext)s',
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
        }
    
    def can_user_download(self, user_id: str) -> Tuple[bool, str]:
        """بررسی امکان دانلود کاربر"""
        user = self.data_manager.get_user(user_id)
        
        if user and user.is_premium():
            return True, "پریمیوم"
        
        downloads = self.data_manager.get_download_count(user_id)
        remaining = self.config.MAX_FREE_DOWNLOADS - downloads
        
        if remaining > 0:
            return True, f"رایگان ({remaining} باقی‌مانده)"
        else:
            return False, f"دانلودهای رایگان شما به پایان رسیده است."
    
    async def download_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """دستور /download"""
        user = update.effective_user
        user_id = str(user.id)
        
        # بررسی محدودیت
        can_download, message = self.can_user_download(user_id)
        
        if not can_download:
            keyboard = [
                [InlineKeyboardButton("💎 خرید اشتراک", callback_data="premium_menu")],
                [InlineKeyboardButton("🏠 منوی اصلی", callback_data="main_menu")]
            ]
            
            await update.message.reply_text(
                f"⛔ **محدودیت دانلود**\n\n{message}\n\n"
                "👇 برای دانلود نامحدود اشتراک پریمیوم بخرید:",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
            return ConversationHandler.END
        
        await update.message.reply_text(
            "📥 **لطفاً لینک ویدئو را ارسال کنید:**\n\n"
            "✅ **پلتفرم‌های پشتیبانی شده:**\n"
            "• YouTube, Instagram, TikTok\n"
            "• Twitter, Facebook, Reddit\n"
            "• Dailymotion, Vimeo, Twitch\n\n"
            "🔗 **مثال:** https://www.youtube.com/watch?v=...\n\n"
            "❌ برای لغو: /cancel",
            reply_markup=self.get_cancel_keyboard(),
            parse_mode='Markdown'
        )
        
        return self.WAITING_LINK
    
    async def process_link(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """پردازش لینک"""
        user = update.effective_user
        user_id = str(user.id)
        url = update.message.text.strip()
        
        # اعتبارسنجی URL
        if not self.is_valid_url(url):
            await update.message.reply_text(
                "❌ **لینک نامعتبر!**\n\n"
                "لطفاً لینک معتبر از پلتفرم‌های پشتیبانی شده ارسال کنید.",
                reply_markup=self.get_reply_keyboard(user.id)
            )
            return ConversationHandler.END
        
        # افزایش تعداد دانلودها
        self.data_manager.increment_downloads(user_id)
        
        # شبیه‌سازی بررسی لینک
        await update.message.reply_text("🔍 در حال بررسی لینک...")
        await asyncio.sleep(1)
        
        # کیبورد انتخاب کیفیت
        keyboard = [
            [
                InlineKeyboardButton("📹 360p", callback_data=f"quality_360_{url}"),
                InlineKeyboardButton("📹 480p", callback_data=f"quality_480_{url}")
            ],
            [
                InlineKeyboardButton("📹 720p (HD)", callback_data=f"quality_720_{url}"),
                InlineKeyboardButton("📹 1080p (FHD)", callback_data=f"quality_1080_{url}")
            ],
            [
                InlineKeyboardButton("🎵 MP3", callback_data=f"quality_mp3_{url}"),
                InlineKeyboardButton("🎵 MP4", callback_data=f"quality_mp4_{url}")
            ],
            [InlineKeyboardButton("❌ لغو", callback_data="cancel_download")]
        ]
        
        await update.message.reply_text(
            "✅ **ویدئو یافت شد!**\n\n"
            "👇 لطفاً کیفیت مورد نظر را انتخاب کنید:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        
        return ConversationHandler.END
    
    async def select_quality(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """انتخاب کیفیت"""
        query = update.callback_query
        await query.answer()
        
        # استخراج کیفیت و URL از callback_data
        data_parts = query.data.split('_')
        quality = data_parts[1]  # 360, 480, 720, 1080, mp3, mp4
        url = '_'.join(data_parts[2:])  # URL اصلی
        
        quality_text = {
            "360": "360p",
            "480": "480p",
            "720": "720p (HD)",
            "1080": "1080p (Full HD)",
            "mp3": "MP3",
            "mp4": "MP4"
        }.get(quality, "پیش‌فرض")
        
        await query.edit_message_text(f"⏳ در حال دانلود با کیفیت {quality_text}...")
        
        try:
            if self.config.ENABLE_REAL_DOWNLOAD:
                # دانلود واقعی با yt-dlp
                downloaded_file = await self._download_with_ytdlp(url, quality)
                
                if downloaded_file:
                    # ارسال فایل به کاربر
                    with open(downloaded_file, 'rb') as file:
                        if quality in ['mp3', 'mp4']:
                            await context.bot.send_document(
                                chat_id=query.from_user.id,
                                document=file,
                                caption=f"✅ دانلود با کیفیت {quality_text} کامل شد!"
                            )
                        else:
                            await context.bot.send_video(
                                chat_id=query.from_user.id,
                                video=file,
                                caption=f"✅ دانلود با کیفیت {quality_text} کامل شد!"
                            )
                    
                    # حذف فایل موقت
                    os.remove(downloaded_file)
                    
                    await query.edit_message_text(
                        f"✅ **دانلود کامل شد!**\n\n"
                        f"📦 کیفیت: {quality_text}\n"
                        f"📁 فرمت: {'MP3' if quality == 'mp3' else 'MP4' if quality == 'mp4' else 'ویدئو'}\n\n"
                        "👇 برای دانلود دیگر:",
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton("📥 دانلود دیگر", callback_data="download_again")],
                            [InlineKeyboardButton("🏠 منوی اصلی", callback_data="main_menu")]
                        ])
                    )
                else:
                    raise Exception("خطا در دانلود فایل")
            else:
                # شبیه‌سازی دانلود
                await asyncio.sleep(3)
                
                await query.edit_message_text(
                    f"✅ **دانلود کامل شد!**\n\n"
                    f"📦 کیفیت: {quality_text}\n"
                    f"📊 حجم: ~125MB\n"
                    f"📁 فرمت: {'MP3' if quality == 'mp3' else 'MP4' if quality == 'mp4' else 'ویدئو'}\n\n"
                    "⚠️ **توجه:** دانلود واقعی نیاز به نصب yt-dlp دارد.\n"
                    "برای دانلود واقعی: `pip install yt-dlp`\n\n"
                    "👇 برای دانلود دیگر:",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("📥 دانلود دیگر", callback_data="download_again")],
                        [InlineKeyboardButton("🏠 منوی اصلی", callback_data="main_menu")]
                    ])
                )
                
        except Exception as e:
            logger.error(f"خطا در دانلود: {e}")
            await query.edit_message_text(
                f"❌ **خطا در دانلود!**\n\n"
                f"خطا: {str(e)[:100]}\n\n"
                "لطفاً دوباره تلاش کنید یا لینک دیگری ارسال کنید.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📥 دانلود دیگر", callback_data="download_again")],
                    [InlineKeyboardButton("🏠 منوی اصلی", callback_data="main_menu")]
                ])
            )
    
    async def _download_with_ytdlp(self, url: str, quality: str) -> Optional[str]:
        """دانلود واقعی با yt-dlp"""
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                # تنظیمات بر اساس کیفیت
                ydl_opts = self.ydl_opts.copy()
                ydl_opts['outtmpl'] = os.path.join(tmpdir, '%(title)s.%(ext)s')
                
                if quality == 'mp3':
                    ydl_opts['format'] = 'bestaudio/best'
                    ydl_opts['postprocessors'] = [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '192',
                    }]
                elif quality == 'mp4':
                    ydl_opts['format'] = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4'
                elif quality in ['360', '480', '720', '1080']:
                    ydl_opts['format'] = f'bestvideo[height<={quality}]+bestaudio/best[height<={quality}]'
                
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    
                    # یافتن فایل دانلود شده
                    downloaded_files = [f for f in os.listdir(tmpdir) if f.endswith(('.mp4', '.mp3', '.webm', '.mkv'))]
                    
                    if downloaded_files:
                        return os.path.join(tmpdir, downloaded_files[0])
                    
        except Exception as e:
            logger.error(f"خطا در yt-dlp: {e}")
        
        return None
    
    async def cancel_download(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """لغو دانلود"""
        query = update.callback_query
        await query.answer()
        
        await query.edit_message_text(
            "✅ دانلود لغو شد.",
            reply_markup=self.get_reply_keyboard(query.from_user.id)
        )
    
    async def download_again(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """دانلود مجدد"""
        query = update.callback_query
        await query.answer()
        
        await self.download_command(update, context)


class PaymentController(BaseController):
    """کنترلر پرداخت"""
    
    def __init__(self, data_manager: DataManager, config: Config):
        super().__init__(data_manager, config)
        self.WAITING_TXID = 1
    
    def get_premium_text(self) -> str:
        """متن طرح‌های پریمیوم"""
        text = "💎 **طرح‌های اشتراک پریمیوم**\n\n"
        
        for plan_id, plan in self.config.PLANS.items():
            text += f"**{plan['name']}** - {plan['price_usdt']} دلار\n"
            if plan['discount_percent'] > 0:
                text += f"📉 تخفیف: {plan['discount_percent']}%\n"
            text += f"📅 مدت: {plan['duration_days']} روز\n"
            text += "✨ ویژگی‌ها:\n"
            for feature in plan['features']:
                text += f"• {feature}\n"
            text += "\n"
        
        return text
    
    def get_premium_keyboard(self) -> InlineKeyboardMarkup:
        """کیبورد طرح‌های پریمیوم"""
        keyboard = []
        
        for plan_id, plan in self.config.PLANS.items():
            button_text = f"{plan['name']} - {plan['price_usdt']}$"
            if plan['discount_percent'] > 0:
                button_text += f" ({plan['discount_percent']}% تخفیف)"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=f"plan_{plan_id}")])
        
        keyboard.append([
            InlineKeyboardButton("💳 پرداخت USDT", callback_data="payment_info"),
            InlineKeyboardButton("🏠 منوی اصلی", callback_data="main_menu")
        ])
        
        return InlineKeyboardMarkup(keyboard)
    
    async def premium_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """منوی اشتراک"""
        await update.message.reply_text(
            self.get_premium_text(),
            reply_markup=self.get_premium_keyboard(),
            parse_mode='Markdown'
        )
    
    async def show_plans(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """نمایش طرح‌ها"""
        query = update.callback_query
        await query.answer()
        
        await query.edit_message_text(
            self.get_premium_text(),
            reply_markup=self.get_premium_keyboard(),
            parse_mode='Markdown'
        )
    
    async def select_plan(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """انتخاب طرح"""
        query = update.callback_query
        await query.answer()
        
        plan_id = query.data.replace("plan_", "")
        plan = self.config.PLANS.get(plan_id)
        
        if not plan:
            await query.edit_message_text("❌ طرح انتخاب شده معتبر نیست.")
            return
        
        context.user_data['selected_plan'] = plan_id
        
        await query.edit_message_text(
            self._get_payment_text(plan, query.from_user),
            reply_markup=self._get_payment_keyboard(plan_id),
            parse_mode='Markdown'
        )
    
    def _get_payment_text(self, plan: Dict, user) -> str:
        """متن اطلاعات پرداخت"""
        return f"""💎 **خرید طرح {plan['name']}**

📋 **مشخصات:**
• مدت: {plan['duration_days']} روز
• قیمت: {plan['price_usdt']} دلار
• تخفیف: {plan['discount_percent']}%

✨ **ویژگی‌ها:**
{chr(10).join(['• ' + feature for feature in plan['features']])}

👤 **کاربر:** {user.first_name}
🆔 **آیدی:** `{user.id}`

👇 لطفاً روش پرداخت را انتخاب کنید:"""
    
    def _get_payment_keyboard(self, plan_id: str) -> InlineKeyboardMarkup:
        """کیبورد روش پرداخت"""
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("💰 پرداخت با USDT", callback_data=f"start_payment_{plan_id}")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="premium_menu")],
            [InlineKeyboardButton("🏠 منوی اصلی", callback_data="main_menu")]
        ])
    
    async def payment_info(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """اطلاعات پرداخت"""
        payment_text = f"""💳 **سیستم پرداخت USDT**

💰 **روش پرداخت:** USDT (شبکه TRC20)
📤 **آدرس کیف پول:**
`{self.config.USDT_WALLET}`

⚠️ **توجه مهم:**
1. فقط از شبکه TRC20 استفاده کنید
2. کارمزد شبکه را در نظر بگیرید
3. پس از پرداخت، Transaction ID را ارسال کنید
4. تأیید پرداخت ۲-۱۰ دقیقه طول می‌کشد

📋 **مراحل پرداخت:**
1. طرح مورد نظر را انتخاب کنید
2. مبلغ را به آدرس بالا واریز کنید
3. Transaction ID را برای ما ارسال کنید
4. اشتراک شما فعال می‌شود

👇 لطفاً گزینه مورد نظر را انتخاب کنید:"""
        
        keyboard = [
            [InlineKeyboardButton("💎 خرید اشتراک", callback_data="premium_menu")],
            [InlineKeyboardButton("📋 راهنما", callback_data="help")],
            [InlineKeyboardButton("🏠 منوی اصلی", callback_data="main_menu")]
        ]
        
        await update.message.reply_text(
            payment_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def start_payment(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """شروع پرداخت"""
        query = update.callback_query
        await query.answer()
        
        plan_id = query.data.replace("start_payment_", "")
        plan = self.config.PLANS.get(plan_id)
        
        if not plan:
            await query.edit_message_text("❌ طرح انتخاب شده معتبر نیست.")
            return ConversationHandler.END
        
        context.user_data['selected_plan'] = plan_id
        
        await query.edit_message_text(
            f"💳 **پرداخت برای طرح {plan['name']}**\n\n"
            f"💰 **مبلغ:** {plan['price_usdt']} دلار\n\n"
            f"📤 **آدرس کیف پول USDT (TRC20):**\n"
            f"`{self.config.USDT_WALLET}`\n\n"
            "⚠️ **لطفاً پس از پرداخت، Transaction ID را ارسال کنید:**\n\n"
            "❌ برای انصراف: /cancel",
            parse_mode='Markdown'
        )
        
        return self.WAITING_TXID
    
    async def receive_txid(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """دریافت TXID"""
        txid = update.message.text.strip()
        plan_id = context.user_data.get('selected_plan')
        plan = self.config.PLANS.get(plan_id) if plan_id else None
        
        if not plan:
            await update.message.reply_text("❌ اطلاعات پرداخت ناقص است.")
            return ConversationHandler.END
        
        # اعتبارسنجی TXID
        if not self.validate_txid(txid):
            await update.message.reply_text(
                "❌ **Transaction ID نامعتبر!**\n\n"
                "لطفاً TXID معتبر ارسال کنید (حداقل ۱۰ کاراکتر، فقط حروف و اعداد).",
                parse_mode='Markdown'
            )
            return self.WAITING_TXID
        
        # پردازش پرداخت
        await self._process_payment(update, context, plan, txid)
        return ConversationHandler.END
    
    async def _process_payment(self, update: Update, context: ContextTypes.DEFAULT_TYPE, 
                             plan: Dict, txid: str):
        """پردازش پرداخت"""
        user = update.effective_user
        user_id = str(user.id)
        
        await update.message.reply_text("⏳ در حال تأیید پرداخت...")
        await asyncio.sleep(2)
        
        # فعال‌سازی اشتراک
        self.data_manager.add_payment(
            user_id=user_id,
            plan_name=plan['name'],
            amount=plan['price_usdt'],
            txid=txid
        )
        
        # ارتقا کاربر به پریمیوم
        user_obj = self.data_manager.get_user(user_id)
        if user_obj:
            user_obj.activate_premium(plan['duration_days'])
            self.data_manager.update_user(user_obj)
        
        expiry_date = (datetime.now() + timedelta(days=plan['duration_days'])).strftime("%Y-%m-%d")
        
        success_text = f"""🎉 **پرداخت موفقیت‌آمیز!**

✅ **اشتراک {plan['name']} فعال شد.**
📅 **تاریخ انقضا:** {expiry_date}
🔗 **TXID:** `{txid[:20]}...`

✨ **ویژگی‌های فعال شده:**
{chr(10).join(['• ' + feature for feature in plan['features']])}

🎯 **اکنون می‌توانید:**
• دانلود نامحدود
• کیفیت 4K
• حذف واترمارک
• و سایر ویژگی‌ها

👇 برای شروع دانلود:"""
        
        keyboard = [
            [InlineKeyboardButton("📥 شروع دانلود", callback_data="download_after_premium")],
            [InlineKeyboardButton("🏠 منوی اصلی", callback_data="main_menu")]
        ]
        
        await update.message.reply_text(
            success_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def cancel_payment(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """لغو پرداخت"""
        await update.message.reply_text(
            "❌ پرداخت لغو شد.",
            reply_markup=self.get_reply_keyboard(update.effective_user.id)
        )
        return ConversationHandler.END


class MenuController(BaseController):
    """کنترلر منو"""
    
    async def main_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """منوی اصلی"""
        user = update.effective_user
        reply_markup = self.get_reply_keyboard(user.id)
        
        await update.message.reply_text(
            "🏠 **منوی اصلی**\n\nلطفاً از دکمه‌های پایین صفحه استفاده کنید:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    async def main_menu_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Callback منوی اصلی"""
        query = update.callback_query
        await query.answer()
        
        user = query.from_user
        reply_markup = self.get_reply_keyboard(user.id)
        
        await query.edit_message_text(
            "🏠 **منوی اصلی**\n\nلطفاً از دکمه‌های پایین صفحه استفاده کنید:",
            reply_markup=reply_markup
        )
    
    async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """راهنما"""
        help_text = f"""📚 **راهنمای ربات**

✨ **قابلیت‌های اصلی:**
• 📥 دانلود از ۱۰+ پلتفرم
• 💎 اشتراک پریمیوم
• 💳 پرداخت امن با USDT

🎯 **دستورات:**
• /start - شروع ربات
• /menu - منوی اصلی
• /download - دانلود ویدئو
• /profile - حساب کاربری
• /premium - خرید اشتراک
• /pay - پرداخت USDT
• /help - این راهنما
• /support - پشتیبانی

💎 **طرح‌های اشتراک:**
• ۱ ماهه - 5 دلار
• ۳ ماهه - 12 دلار (20% تخفیف)
• ۶ ماهه - 20 دلار (33% تخفیف)
• ۱ ساله - 35 دلار (42% تخفیف)

💳 **پرداخت:**
پرداخت از طریق USDT (شبکه TRC20)
آدرس کیف پول: `{self.config.USDT_WALLET}`

📞 **پشتیبانی:** {self.config.SUPPORT_USERNAME}
"""
        
        await update.message.reply_text(
            help_text,
            parse_mode='Markdown',
            reply_markup=self.get_reply_keyboard(update.effective_user.id)
        )
    
    async def support(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """پشتیبانی"""
        support_text = f"""📞 **پشتیبانی**

👨‍💻 ادمین: {self.config.SUPPORT_USERNAME}
🕒 ساعات پاسخگویی: ۹ صبح تا ۱۲ شب

⚠️ **توجه:**
• لطفاً قبل از ارسال پیام، راهنما را مطالعه کنید (/help)
• برای مشکلات پرداخت، حتماً Transaction ID را ارسال کنید
• برای گزارش باگ، از /report استفاده کنید

👇 برای ارتباط مستقیم با ادمین، پیام خود را ارسال کنید."""
        
        await update.message.reply_text(
            support_text,
            parse_mode='Markdown',
            reply_markup=self.get_reply_keyboard(update.effective_user.id)
        )
    
    async def about(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """درباره"""
        about_text = """🤖 **درباره ربات**

ربات دانلود و پرداخت USDT
نسخه: 5.0.0
توسعه‌دهنده: تیم برنامه‌نویسی

✨ **ویژگی‌ها:**
• دانلود از ۱۰+ پلتفرم (با yt-dlp)
• پرداخت امن با USDT
• رابط کاربری فارسی
• پشتیبانی ۲۴ ساعته

🔒 **امنیت:**
• تمام پرداخت‌ها مستقیم و بدون واسطه
• اطلاعات کاربران محفوظ
• تراکنش‌های شفاف"""
        
        await update.message.reply_text(
            about_text,
            parse_mode='Markdown',
            reply_markup=self.get_reply_keyboard(update.effective_user.id)
        )


class AdminController(BaseController):
    """کنترلر ادمین"""
    
    async def admin_panel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """پنل ادمین"""
        user = update.effective_user
        
        if user.id != self.config.ADMIN_ID:
            await update.message.reply_text("⛔ **دسترسی رد شد!**")
            return
        
        stats = self.data_manager.get_system_stats()
        
        admin_text = f"""🛠️ **پنل مدیریت**

👥 **کاربران:** {stats['total_users']}
💎 **پریمیوم:** {stats['premium_users']}
📥 **دانلودها:** {stats['total_downloads']}
💳 **پرداخت‌ها:** {stats['total_payments']}

💰 **درآمد کل:** {stats['total_revenue']} دلار
📅 **امروز:** {stats['today_users']} کاربر جدید

👇 گزینه مورد نظر را انتخاب کنید:"""
        
        keyboard = [
            [InlineKeyboardButton("📊 آمار کامل", callback_data="admin_stats")],
            [InlineKeyboardButton("👥 کاربران", callback_data="admin_users")],
            [InlineKeyboardButton("📤 ارسال همگانی", callback_data="admin_broadcast")],
            [InlineKeyboardButton("🔧 تنظیمات", callback_data="admin_settings")]
        ]
        
        await update.message.reply_text(
            admin_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def admin_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """آمار کامل"""
        query = update.callback_query
        await query.answer()
        
        if query.from_user.id != self.config.ADMIN_ID:
            await query.answer("⛔ دسترسی ندارید!", show_alert=True)
            return
        
        stats = self.data_manager.get_system_stats()
        
        stats_text = f"""📊 **آمار کامل سیستم**

👥 **کاربران:**
• کل: {stats['total_users']}
• پریمیوم: {stats['premium_users']}
• رایگان: {stats['total_users'] - stats['premium_users']}
• امروز: {stats['today_users']}

📥 **دانلودها:**
• کل: {stats['total_downloads']}
• متوسط هر کاربر: {stats['total_downloads'] / max(stats['total_users'], 1):.1f}

💰 **مالی:**
• پرداخت‌ها: {stats['total_payments']}
• درآمد کل: {stats['total_revenue']} دلار
• متوسط هر پرداخت: {stats['total_revenue'] / max(stats['total_payments'], 1):.1f} دلار"""
        
        await query.edit_message_text(
            stats_text,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📤 Export Data", callback_data="admin_export")],
                [InlineKeyboardButton("🔙 بازگشت", callback_data="admin_panel")]
            ])
        )
    
    async def admin_panel_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Callback پنل ادمین"""
        query = update.callback_query
        await query.answer()
        
        if query.from_user.id != self.config.ADMIN_ID:
            await query.answer("⛔ دسترسی ندارید!", show_alert=True)
            return
        
        await self.admin_panel(update, context)


class TextMessageController(BaseController):
    """کنترلر پیام‌های متنی"""
    
    def __init__(self, data_manager: DataManager, config: Config,
                 user_controller: UserController,
                 download_controller: DownloadController,
                 payment_controller: PaymentController,
                 menu_controller: MenuController,
                 admin_controller: AdminController):
        super().__init__(data_manager, config)
        self.user_controller = user_controller
        self.download_controller = download_controller
        self.payment_controller = payment_controller
        self.menu_controller = menu_controller
        self.admin_controller = admin_controller
    
    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """مدیریت پیام‌های متنی"""
        text = update.message.text
        user = update.effective_user
        
        # بررسی اگر در حالت انتظار لینک است
        if context.user_data.get('waiting_for_link'):
            await self.download_controller.process_link(update, context)
            context.user_data.pop('waiting_for_link', None)
            return
        
        # پردازش دکمه‌های Reply Keyboard
        if text == "📥 دانلود ویدئو":
            await self.download_controller.download_command(update, context)
        
        elif text == "👤 حساب کاربری":
            await self.user_controller.profile(update, context)
        
        elif text == "💎 خرید اشتراک":
            await self.payment_controller.premium_menu(update, context)
        
        elif text == "💳 پرداخت USDT":
            await self.payment_controller.payment_info(update, context)
        
        elif text == "📋 راهنما":
            await self.menu_controller.help(update, context)
        
        elif text == "📞 پشتیبانی":
            await self.menu_controller.support(update, context)
        
        elif text == "🛠️ پنل مدیریت" and user.id == self.config.ADMIN_ID:
            await self.admin_controller.admin_panel(update, context)
        
        elif text == "❌ لغو":
            await update.message.reply_text(
                "✅ عملیات لغو شد.",
                reply_markup=self.get_reply_keyboard(user.id)
            )
        
        elif text == "🏠 منوی اصلی":
            await self.menu_controller.main_menu(update, context)
        
        else:
            # اگر لینک باشد
            if self.is_valid_url(text):
                await self.download_controller.process_link(update, context)
            else:
                await update.message.reply_text(
                    "لطفاً از دکمه‌های منو استفاده کنید.",
                    reply_markup=self.get_reply_keyboard(user.id)
                )


class ControllerManager:
    """مدیر کنترلرها"""
    
    def __init__(self, data_manager: DataManager, config: Config):
        self.data_manager = data_manager
        self.config = config
        
        # ایجاد کنترلرها
        self.user = UserController(data_manager, config)
        self.download = DownloadController(data_manager, config)
        self.payment = PaymentController(data_manager, config)
        self.menu = MenuController(data_manager, config)
        self.admin = AdminController(data_manager, config)
        self.text_handler = TextMessageController(
            data_manager, config,
            self.user, self.download,
            self.payment, self.menu,
            self.admin
        )
    
    def get_handlers(self):
        """دریافت تمام handlers"""
        handlers = []
        
        # دستورات اصلی
        handlers.append(CommandHandler("start", self.user.start))
        handlers.append(CommandHandler("profile", self.user.profile))
        handlers.append(CommandHandler("menu", self.menu.main_menu))
        handlers.append(CommandHandler("help", self.menu.help))
        handlers.append(CommandHandler("support", self.menu.support))
        handlers.append(CommandHandler("about", self.menu.about))
        
        # دستورات دانلود و پرداخت
        handlers.append(CommandHandler("download", self.download.download_command))
        handlers.append(CommandHandler("premium", self.payment.premium_menu))
        handlers.append(CommandHandler("pay", self.payment.payment_info))
        
        # دستورات ادمین
        handlers.append(CommandHandler("admin", self.admin.admin_panel))
        
        # Callback Queries
        handlers.append(CallbackQueryHandler(self.user.refresh_profile, pattern="^refresh_profile$"))
        handlers.append(CallbackQueryHandler(self.menu.main_menu_callback, pattern="^main_menu$"))
        handlers.append(CallbackQueryHandler(self.payment.show_plans, pattern="^premium_menu$"))
        handlers.append(CallbackQueryHandler(self.payment.select_plan, pattern="^plan_"))
        handlers.append(CallbackQueryHandler(self.payment.payment_info, pattern="^payment_info$"))
        handlers.append(CallbackQueryHandler(self.download.select_quality, pattern="^quality_"))
        handlers.append(CallbackQueryHandler(self.download.cancel_download, pattern="^cancel_download$"))
        handlers.append(CallbackQueryHandler(self.download.download_again, pattern="^download_again$"))
        handlers.append(CallbackQueryHandler(self.download.download_command, pattern="^download_after_premium$"))
        handlers.append(CallbackQueryHandler(self.admin.admin_stats, pattern="^admin_stats$"))
        handlers.append(CallbackQueryHandler(self.admin.admin_panel_callback, pattern="^admin_panel$"))
        
        # Conversation Handlers
        payment_conv = ConversationHandler(
            entry_points=[
                CallbackQueryHandler(self.payment.start_payment, pattern="^start_payment_")
            ],
            states={
                self.payment.WAITING_TXID: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.payment.receive_txid)
                ]
            },
            fallbacks=[CommandHandler("cancel", self.payment.cancel_payment)]
        )
        handlers.append(payment_conv)
        
        download_conv = ConversationHandler(
            entry_points=[
                CommandHandler("download", self.download.download_command)
            ],
            states={
                self.download.WAITING_LINK: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.download.process_link)
                ]
            },
            fallbacks=[CommandHandler("cancel", self.menu.main_menu)]
        )
        handlers.append(download_conv)
        
        # Handler پیام‌های متنی (باید در آخر اضافه شود)
        handlers.append(MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            self.text_handler.handle_text
        ))
        
        return handlers


# =========================
# Main Router Class
# =========================

class Router:
    """Router اصلی"""
    
    def __init__(self, app: Application):
        self.app = app
        self.config = Config()
        
        # مدیر داده‌ها
        self.data_dir = Path("data")
        self.data_manager = DataManager(self.data_dir)
        
        # مدیر کنترلرها
        self.controller_manager = ControllerManager(self.data_manager, self.config)
        
        # تنظیم ذخیره خودکار
        self._setup_auto_save()
        
        logger.info(f"✅ Router راه‌اندازی شد - کاربران: {len(self.data_manager.users)}")
        
        if self.config.ENABLE_REAL_DOWNLOAD:
            logger.info("✅ دانلود واقعی فعال است (yt-dlp)")
        else:
            logger.warning("⚠️ دانلود واقعی غیرفعال است. برای فعال کردن: pip install yt-dlp")
    
    def _setup_auto_save(self):
        """تنظیم ذخیره خودکار"""
        import threading
        import time
        
        def save_loop():
            while True:
                time.sleep(300)  # هر 5 دقیقه
                self.data_manager.save_all()
        
        thread = threading.Thread(target=save_loop, daemon=True)
        thread.start()
    
    def register_routes(self):
        """ثبت مسیرها"""
        try:
            handlers = self.controller_manager.get_handlers()
            
            # اضافه کردن handlers به application
            for handler in handlers:
                self.app.add_handler(handler)
            
            # اضافه کردن error handler
            self.app.add_error_handler(self._error_handler)
            
            logger.info(f"✅ {len(handlers)} handler ثبت شدند")
            return True
            
        except Exception as e:
            logger.error(f"❌ خطا در ثبت مسیرها: {e}", exc_info=True)
            return False
    
    async def _error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """مدیریت خطاها"""
        logger.error(f"خطا در به‌روزرسانی {update}: {context.error}", exc_info=True)
        
        try:
            if update and update.effective_message:
                error_text = "❌ **خطا رخ داد، لطفاً دوباره تلاش کنید.**"
                
                if update.effective_user:
                    await update.effective_message.reply_text(
                        error_text,
                        reply_markup=self.controller_manager.menu.get_reply_keyboard(
                            update.effective_user.id
                        )
                    )
        except Exception as e:
            logger.error(f"خطا در ارسال پیام خطا: {e}")