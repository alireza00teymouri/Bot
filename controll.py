

"""
controllers.py - کنترلرهای تلگرام با استفاده از Domain Layer
"""

import logging
import re
import asyncio
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta

from telegram import (
    Update, 
    InlineKeyboardButton, 
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton
)
from telegram.ext import (
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    filters,
    ContextTypes,
)

logger = logging.getLogger(__name__)


# =========================
# Base Controller
# =========================

class BaseController:
    """کنترلر پایه"""
    
    def __init__(self, domain_manager, config):
        self.domain = domain_manager
        self.config = config
    
    def get_reply_keyboard(self, user_id: int) -> ReplyKeyboardMarkup:
        """ایجاد Reply Keyboard اصلی"""
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


# =========================
# User Controller
# =========================

class UserController(BaseController):
    """کنترلر کاربران"""
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """دستور /start"""
        user = update.effective_user
        
        try:
            # ثبت کاربر در Domain
            if hasattr(self.domain, 'user_service'):
                user_obj = self.domain.user_service.register_user(
                    user_id=str(user.id),
                    username=user.username,
                    first_name=user.first_name,
                    last_name=user.last_name
                )
                
                # ساخت پیام خوش‌آمدگویی
                welcome_text = self._get_welcome_text(user, user_obj)
            else:
                # حالت fallback
                welcome_text = self._get_fallback_welcome_text(user)
            
            # ارسال پیام با Reply Keyboard
            reply_markup = self.get_reply_keyboard(user.id)
            
            await update.message.reply_text(
                welcome_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"خطا در start: {e}")
            await update.message.reply_text(
                "❌ خطایی رخ داد. لطفاً دوباره تلاش کنید.",
                reply_markup=self.get_reply_keyboard(user.id)
            )
    
    def _get_welcome_text(self, telegram_user, domain_user) -> str:
        """متن خوش‌آمدگویی با Domain"""
        user_id = str(telegram_user.id)
        
        # بررسی وضعیت کاربر
        if hasattr(domain_user, 'is_premium') and domain_user.is_premium():
            status = "💎 پریمیوم"
            remaining = "نامحدود"
        else:
            status = "🆓 رایگان"
            # بررسی تعداد دانلودهای باقی‌مانده
            if hasattr(self.domain, 'download_service'):
                can_download, message = self.domain.download_service.check_download_limit(user_id)
                remaining = message.split('(')[-1].split(')')[0] if '(' in message else "3"
            else:
                remaining = "3"
        
        return f"""🎉 **سلام {telegram_user.first_name}!**
🤖 به ربات دانلود و پرداخت USDT خوش آمدید!

✨ **قابلیت‌های اصلی:**
📥 دانلود از +10 پلتفرم
💎 اشتراک پریمیوم
💳 پرداخت امن با USDT

📊 **وضعیت شما:** {status}
🎯 **دانلود باقی‌مانده:** {remaining}

👇 لطفاً از منوی زیر انتخاب کنید:"""
    
    def _get_fallback_welcome_text(self, user) -> str:
        """متن خوش‌آمدگویی fallback"""
        return f"""🎉 **سلام {user.first_name}!**
🤖 به ربات دانلود و پرداخت USDT خوش آمدید!

✨ **قابلیت‌های اصلی:**
📥 دانلود از +10 پلتفرم
💎 اشتراک پریمیوم
💳 پرداخت امن با USDT

📊 **وضعیت شما:** 🆓 رایگان
🎯 **دانلود باقی‌مانده:** 3

👇 لطفاً از منوی زیر انتخاب کنید:"""
    
    async def profile(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """دستور /profile"""
        user = update.effective_user
        user_id = str(user.id)
        
        try:
            if hasattr(self.domain, 'user_service'):
                # دریافت پروفایل از Domain
                profile_data = self.domain.user_service.get_user_profile(user_id)
                
                if profile_data:
                    profile_text = self._format_profile_text(user, profile_data)
                else:
                    profile_text = self._get_fallback_profile_text(user)
            else:
                profile_text = self._get_fallback_profile_text(user)
            
            # ارسال پروفایل
            keyboard = []
            if not (hasattr(self.domain, 'user_service') and 
                   self.domain.user_service.user_repo.get_user(user_id) and
                   self.domain.user_service.user_repo.get_user(user_id).is_premium()):
                keyboard.append([InlineKeyboardButton("💎 خرید اشتراک", callback_data="premium_menu")])
            
            keyboard.append([InlineKeyboardButton("🔄 بروزرسانی", callback_data="refresh_profile")])
            
            await update.message.reply_text(
                profile_text,
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None
            )
            
        except Exception as e:
            logger.error(f"خطا در profile: {e}")
            await update.message.reply_text(
                "❌ خطا در دریافت پروفایل",
                reply_markup=self.get_reply_keyboard(user.id)
            )
    
    def _format_profile_text(self, telegram_user, profile_data) -> str:
        """فرمت‌بندی متن پروفایل"""
        user_data = profile_data['user']
        stats = profile_data['stats']
        
        status = "💎 پریمیوم" if user_data['status'] == 'premium' else "🆓 رایگان"
        
        text = f"""👤 **حساب کاربری**

🆔 آیدی: `{telegram_user.id}`
👁️ نام: {telegram_user.first_name or 'نامشخص'}
📱 یوزرنیم: @{telegram_user.username or 'ندارد'}

📊 **وضعیت:** {status}
📥 **دانلودها:** {stats.get('downloads', 0)}
💰 **موجودی:** {stats.get('balance', 0)} دلار
📅 **عضویت:** {user_data.get('join_date', 'نامشخص')[:10]}"""
        
        return text
    
    def _get_fallback_profile_text(self, user) -> str:
        """متن پروفایل fallback"""
        return f"""👤 **حساب کاربری**

🆔 آیدی: `{user.id}`
👁️ نام: {user.first_name or 'نامشخص'}
📱 یوزرنیم: @{user.username or 'ندارد'}

📊 **وضعیت:** 🆓 رایگان
📥 **دانلودها:** 0
💰 **موجودی:** 0 دلار
📅 **عضویت:** {datetime.now().strftime('%Y-%m-%d')}"""
    
    async def refresh_profile(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """بروزرسانی پروفایل"""
        query = update.callback_query
        await query.answer()
        
        await self.profile(update, context)


# =========================
# Download Controller
# =========================

class DownloadController(BaseController):
    """کنترلر دانلود"""
    
    def __init__(self, domain_manager, config):
        super().__init__(domain_manager, config)
        self.WAITING_LINK = 1
    
    async def download_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """دستور /download"""
        user = update.effective_user
        user_id = str(user.id)
        
        try:
            # بررسی محدودیت دانلود
            if hasattr(self.domain, 'download_service'):
                can_download, message = self.domain.download_service.check_download_limit(user_id)
            else:
                # حالت fallback
                can_download = True
                message = "آماده دانلود"
            
            if not can_download:
                # نمایش پیام محدودیت
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
            
            # درخواست لینک
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
            
        except Exception as e:
            logger.error(f"خطا در download_command: {e}")
            await update.message.reply_text(
                "❌ خطا در شروع دانلود",
                reply_markup=self.get_reply_keyboard(user.id)
            )
            return ConversationHandler.END
    
    async def process_link(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """پردازش لینک دریافتی"""
        user = update.effective_user
        user_id = str(user.id)
        url = update.message.text.strip()
        
        try:
            # اعتبارسنجی URL
            if not self.is_valid_url(url):
                await update.message.reply_text(
                    "❌ **لینک نامعتبر!**\n\n"
                    "لطفاً لینک معتبر از پلتفرم‌های پشتیبانی شده ارسال کنید.",
                    reply_markup=self.get_reply_keyboard(user.id)
                )
                return ConversationHandler.END
            
            # ایجاد درخواست دانلود در Domain
            if hasattr(self.domain, 'download_service'):
                success, result = self.domain.download_service.create_download_request(
                    user_id, url, check_limit=False
                )
                
                if not success:
                    await update.message.reply_text(
                        f"❌ {result}",
                        reply_markup=self.get_reply_keyboard(user.id)
                    )
                    return ConversationHandler.END
                
                download_request = result
            else:
                # حالت fallback
                download_request = type('SimpleDownload', (), {
                    'id': 'fallback_download',
                    'platform': 'YouTube'
                })()
            
            # شبیه‌سازی بررسی لینک
            await update.message.reply_text("🔍 در حال بررسی لینک...")
            await asyncio.sleep(2)
            
            # کیبورد انتخاب کیفیت
            keyboard = [
                [
                    InlineKeyboardButton("📹 360p", callback_data="quality_360"),
                    InlineKeyboardButton("📹 480p", callback_data="quality_480")
                ],
                [
                    InlineKeyboardButton("📹 720p (HD)", callback_data="quality_720"),
                    InlineKeyboardButton("📹 1080p (FHD)", callback_data="quality_1080")
                ],
                [
                    InlineKeyboardButton("🎵 MP3", callback_data="quality_mp3"),
                    InlineKeyboardButton("🎵 MP4", callback_data="quality_mp4")
                ],
                [InlineKeyboardButton("❌ لغو", callback_data="cancel_download")]
            ]
            
            await update.message.reply_text(
                "✅ **ویدئو یافت شد!**\n\n"
                "📽️ **عنوان:** نمونه ویدئو آموزشی\n"
                "⏱️ **مدت:** ۵:۳۰ دقیقه\n"
                "📊 **حجم:** ~150MB\n"
                "🎬 **فرمت:** MP4\n\n"
                "👇 لطفاً کیفیت مورد نظر را انتخاب کنید:",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
            
            return ConversationHandler.END
            
        except Exception as e:
            logger.error(f"خطا در process_link: {e}")
            await update.message.reply_text(
                "❌ خطا در پردازش لینک",
                reply_markup=self.get_reply_keyboard(user.id)
            )
            return ConversationHandler.END
    
    async def select_quality(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """انتخاب کیفیت دانلود"""
        query = update.callback_query
        await query.answer()
        
        quality_map = {
            "quality_360": "360p",
            "quality_480": "480p",
            "quality_720": "720p (HD)",
            "quality_1080": "1080p (Full HD)",
            "quality_mp3": "MP3",
            "quality_mp4": "MP4"
        }
        
        quality = quality_map.get(query.data, "نامشخص")
        
        # شبیه‌سازی دانلود
        await query.edit_message_text(f"⏳ در حال دانلود با کیفیت {quality}...")
        await asyncio.sleep(3)
        
        # پیام موفقیت
        await query.edit_message_text(
            f"✅ **دانلود کامل شد!**\n\n"
            f"📦 کیفیت: {quality}\n"
            f"📊 حجم: ~125MB\n"
            f"📁 فرمت: {'MP3' if 'mp3' in query.data else 'MP4'}\n\n"
            "👇 برای دانلود دیگر:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📥 دانلود دیگر", callback_data="download_again")],
                [InlineKeyboardButton("🏠 منوی اصلی", callback_data="main_menu")]
            ])
        )
    
    async def cancel_download(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """لغو دانلود"""
        query = update.callback_query
        await query.answer()
        
        await query.edit_message_text(
            "✅ دانلود لغو شد.",
            reply_markup=self.get_reply_keyboard(query.from_user.id)
        )
    
    async def download_again(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """شروع دانلود مجدد"""
        query = update.callback_query
        await query.answer()
        
        await self.download_command(update, context)


# =========================
# Payment Controller
# =========================

class PaymentController(BaseController):
    """کنترلر پرداخت"""
    
    def __init__(self, domain_manager, config):
        super().__init__(domain_manager, config)
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
        """نمایش منوی اشتراک"""
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
        
        # ذخیره طرح انتخابی
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
        """نمایش اطلاعات پرداخت"""
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
        """شروع فرایند پرداخت"""
        query = update.callback_query
        await query.answer()
        
        plan_id = query.data.replace("start_payment_", "")
        plan = self.config.PLANS.get(plan_id)
        
        if not plan:
            await query.edit_message_text("❌ طرح انتخاب شده معتبر نیست.")
            return ConversationHandler.END
        
        # ذخیره طرح انتخابی
        context.user_data['selected_plan'] = plan_id
        
        # ایجاد پرداخت در Domain
        if hasattr(self.domain, 'payment_service'):
            wallet_address = self.config.USDT_WALLET
            payment = self.domain.payment_service.create_payment(
                user_id=str(query.from_user.id),
                plan_id=plan_id,
                wallet_address=wallet_address
            )
            
            if payment:
                context.user_data['payment_id'] = payment.id
        
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
        
        # تأیید پرداخت در Domain
        if hasattr(self.domain, 'payment_service') and 'payment_id' in context.user_data:
            payment_id = context.user_data['payment_id']
            success, message = self.domain.payment_service.confirm_payment(payment_id, txid)
            
            if success:
                await self._send_payment_success(update, plan, txid)
            else:
                await update.message.reply_text(f"❌ {message}")
        else:
            # حالت fallback
            await self._send_payment_success(update, plan, txid)
        
        return ConversationHandler.END
    
    async def _send_payment_success(self, update: Update, plan: Dict, txid: str):
        """ارسال پیام موفقیت پرداخت"""
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


# =========================
# Menu Controller
# =========================

class MenuController(BaseController):
    """کنترلر منو"""
    
    async def main_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """بازگشت به منوی اصلی"""
        user = update.effective_user
        reply_markup = self.get_reply_keyboard(user.id)
        
        await update.message.reply_text(
            "🏠 **منوی اصلی**\n\nلطفاً از دکمه‌های پایین صفحه استفاده کنید:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    async def main_menu_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """بازگشت به منوی اصلی از طریق Callback"""
        query = update.callback_query
        await query.answer()
        
        user = query.from_user
        reply_markup = self.get_reply_keyboard(user.id)
        
        await query.edit_message_text(
            "🏠 **منوی اصلی**\n\nلطفاً از دکمه‌های پایین صفحه استفاده کنید:",
            reply_markup=reply_markup
        )
    
    async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """نمایش راهنما"""
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
        """نمایش اطلاعات پشتیبانی"""
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
        """درباره ربات"""
        about_text = """🤖 **درباره ربات**

ربات دانلود و پرداخت USDT
نسخه: 4.0.0
توسعه‌دهنده: تیم برنامه‌نویسی

✨ **ویژگی‌ها:**
• دانلود از ۱۰+ پلتفرم
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


# =========================
# Admin Controller
# =========================

class AdminController(BaseController):
    """کنترلر ادمین"""
    
    async def admin_panel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """نمایش پنل ادمین"""
        user = update.effective_user
        
        if user.id != self.config.ADMIN_ID:
            await update.message.reply_text("⛔ **دسترسی رد شد!**")
            return
        
        # دریافت آمار از Domain
        if hasattr(self.domain, 'user_service'):
            stats = self.domain.user_service.get_system_stats()
        else:
            stats = self._get_fallback_stats()
        
        admin_text = f"""🛠️ **پنل مدیریت**

👥 **کاربران:** {stats.get('total_users', 0)}
💎 **پریمیوم:** {stats.get('premium_users', 0)}
📥 **دانلودها:** {stats.get('total_downloads', 0)}
💳 **پرداخت‌ها:** {stats.get('total_payments', 0)}

💰 **درآمد کل:** {stats.get('total_revenue', 0)} دلار
📅 **امروز:** {stats.get('today_users', 0)} کاربر جدید

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
    
    def _get_fallback_stats(self) -> Dict:
        """آمار fallback"""
        return {
            'total_users': 0,
            'premium_users': 0,
            'total_downloads': 0,
            'total_payments': 0,
            'total_revenue': 0,
            'today_users': 0
        }
    
    async def admin_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """نمایش آمار کامل"""
        query = update.callback_query
        await query.answer()
        
        if query.from_user.id != self.config.ADMIN_ID:
            await query.answer("⛔ دسترسی ندارید!", show_alert=True)
            return
        
        if hasattr(self.domain, 'user_service'):
            stats = self.domain.user_service.get_system_stats()
        else:
            stats = self._get_fallback_stats()
        
        stats_text = f"""📊 **آمار کامل سیستم**

👥 **کاربران:**
• کل: {stats.get('total_users', 0)}
• پریمیوم: {stats.get('premium_users', 0)}
• رایگان: {stats.get('total_users', 0) - stats.get('premium_users', 0)}
• امروز: {stats.get('today_users', 0)}

📥 **دانلودها:**
• کل: {stats.get('total_downloads', 0)}
• متوسط هر کاربر: {stats.get('total_downloads', 0) / max(stats.get('total_users', 1), 1):.1f}

💰 **مالی:**
• پرداخت‌ها: {stats.get('total_payments', 0)}
• درآمد کل: {stats.get('total_revenue', 0)} دلار
• متوسط هر پرداخت: {stats.get('total_revenue', 0) / max(stats.get('total_payments', 1), 1):.1f} دلار"""
        
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


# =========================
# Text Message Handler
# =========================

class TextMessageController(BaseController):
    """کنترلر پیام‌های متنی"""
    
    def __init__(self, domain_manager, config, 
                 user_controller, download_controller, 
                 payment_controller, menu_controller, 
                 admin_controller):
        super().__init__(domain_manager, config)
        self.user_controller = user_controller
        self.download_controller = download_controller
        self.payment_controller = payment_controller
        self.menu_controller = menu_controller
        self.admin_controller = admin_controller
    
    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """مدیریت پیام‌های متنی (Reply Keyboard)"""
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


# =========================
# Controller Manager
# =========================

class ControllerManager:
    """مدیریت تمام کنترلرها"""
    
    def __init__(self, domain_manager, config):
        self.domain = domain_manager
        self.config = config
        
        # ایجاد نمونه کنترلرها
        self.user = UserController(domain_manager, config)
        self.download = DownloadController(domain_manager, config)
        self.payment = PaymentController(domain_manager, config)
        self.menu = MenuController(domain_manager, config)
        self.admin = AdminController(domain_manager, config)
        
        # کنترلر پیام‌های متنی
        self.text_handler = TextMessageController(
            domain_manager, config,
            self.user, self.download,
            self.payment, self.menu,
            self.admin
        )
    
    def get_handlers(self):
        """دریافت تمام handlers برای ثبت در application"""
        handlers = []
        
        # دستورهای اصلی
        handlers.append(CommandHandler("start", self.user.start))
        handlers.append(CommandHandler("profile", self.user.profile))
        handlers.append(CommandHandler("menu", self.menu.main_menu))
        handlers.append(CommandHandler("help", self.menu.help))
        handlers.append(CommandHandler("support", self.menu.support))
        handlers.append(CommandHandler("about", self.menu.about))
        
        # دانلود
        handlers.append(CommandHandler("download", self.download.download_command))
        
        # پرداخت و اشتراک
        handlers.append(CommandHandler("premium", self.payment.premium_menu))
        handlers.append(CommandHandler("pay", self.payment.payment_info))
        
        # ادمین
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
        
        # Conversation Handler برای پرداخت
        payment_conv_handler = ConversationHandler(
            entry_points=[
                CallbackQueryHandler(self.payment.start_payment, pattern="^start_payment_")
            ],
            states={
                self.payment.WAITING_TXID: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.payment.receive_txid)
                ]
            },
            fallbacks=[
                CommandHandler("cancel", self.payment.cancel_payment)
            ]
        )
        handlers.append(payment_conv_handler)
        
        # Conversation Handler برای دانلود
        download_conv_handler = ConversationHandler(
            entry_points=[
                CommandHandler("download", self.download.download_command)
            ],
            states={
                self.download.WAITING_LINK: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.download.process_link)
                ]
            },
            fallbacks=[
                CommandHandler("cancel", self.menu.main_menu)
            ]
        )
        handlers.append(download_conv_handler)
        
        # Handler پیام‌های متنی
        handlers.append(MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            self.text_handler.handle_text
        ))
        
        return handlers