
"""
domain.py - منطق اصلی کسب‌وکار بدون وابستگی به تلگرام
"""

import json
import re
import logging
from typing import Dict, List, Optional, Tuple, Any, Union
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass, asdict
from enum import Enum
import hashlib
import random
import string

logger = logging.getLogger(__name__)


# =========================
# Data Classes & Enums
# =========================

class UserStatus(Enum):
    FREE = "free"
    TRIAL = "trial"
    PREMIUM = "premium"
    ADMIN = "admin"


class DownloadStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class PaymentStatus(Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"


class AdType(Enum):
    BANNER = "banner"
    INTERSTITIAL = "interstitial"
    REWARDED = "rewarded"


@dataclass
class User:
    """مدل کاربر"""
    id: str
    username: Optional[str]
    first_name: str
    last_name: Optional[str]
    join_date: str
    status: UserStatus
    last_seen: str
    language: str = "fa"
    referred_by: Optional[str] = None
    balance: float = 0.0
    
    def to_dict(self) -> Dict:
        """تبدیل به دیکشنری"""
        data = asdict(self)
        data['status'] = self.status.value
        return data
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'User':
        """ساخت از دیکشنری"""
        data['status'] = UserStatus(data.get('status', UserStatus.FREE.value))
        return cls(**data)
    
    def is_premium(self) -> bool:
        """بررسی پریمیوم بودن"""
        return self.status == UserStatus.PREMIUM
    
    def is_admin(self) -> bool:
        """بررسی ادمین بودن"""
        return self.status == UserStatus.ADMIN
    
    def update_last_seen(self):
        """به‌روزرسانی آخرین مشاهده"""
        self.last_seen = datetime.now().isoformat()


@dataclass
class PremiumPlan:
    """مدل طرح اشتراک"""
    id: str
    name: str
    duration_days: int
    price_usdt: float
    discount_percent: int = 0
    features: List[str] = None
    is_active: bool = True
    
    def __post_init__(self):
        if self.features is None:
            self.features = []
    
    def get_discounted_price(self) -> float:
        """قیمت با تخفیف"""
        if self.discount_percent > 0:
            return self.price_usdt * (1 - self.discount_percent / 100)
        return self.price_usdt
    
    def to_dict(self) -> Dict:
        """تبدیل به دیکشنری"""
        return asdict(self)


@dataclass
class DownloadRequest:
    """درخواست دانلود"""
    id: str
    user_id: str
    url: str
    platform: str
    status: DownloadStatus
    requested_at: str
    completed_at: Optional[str] = None
    quality: Optional[str] = None
    format: Optional[str] = None
    file_size: Optional[float] = None
    file_path: Optional[str] = None
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict:
        """تبدیل به دیکشنری"""
        data = asdict(self)
        data['status'] = self.status.value
        return data
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'DownloadRequest':
        """ساخت از دیکشنری"""
        data['status'] = DownloadStatus(data.get('status', DownloadStatus.PENDING.value))
        return cls(**data)


@dataclass
class Payment:
    """مدل پرداخت"""
    id: str
    user_id: str
    plan_id: str
    amount_usdt: float
    status: PaymentStatus
    txid: Optional[str] = None
    wallet_address: Optional[str] = None
    created_at: str = None
    confirmed_at: Optional[str] = None
    expires_at: Optional[str] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()
    
    def to_dict(self) -> Dict:
        """تبدیل به دیکشنری"""
        data = asdict(self)
        data['status'] = self.status.value
        return data
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Payment':
        """ساخت از دیکشنری"""
        data['status'] = PaymentStatus(data.get('status', PaymentStatus.PENDING.value))
        return cls(**data)


@dataclass
class AdCampaign:
    """کمپین تبلیغاتی"""
    id: str
    title: str
    ad_type: AdType
    image_url: Optional[str] = None
    video_url: Optional[str] = None
    text: Optional[str] = None
    link: Optional[str] = None
    budget_usdt: float = 0.0
    spent_usdt: float = 0.0
    clicks: int = 0
    impressions: int = 0
    is_active: bool = True
    start_date: str = None
    end_date: Optional[str] = None
    
    def __post_init__(self):
        if self.start_date is None:
            self.start_date = datetime.now().isoformat()
    
    def to_dict(self) -> Dict:
        """تبدیل به دیکشنری"""
        data = asdict(self)
        data['ad_type'] = self.ad_type.value
        return data
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'AdCampaign':
        """ساخت از دیکشنری"""
        data['ad_type'] = AdType(data.get('ad_type', AdType.BANNER.value))
        return cls(**data)


# =========================
# Repository Classes
# =========================

class BaseRepository:
    """ریپوزیتوری پایه"""
    
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.data_dir.mkdir(exist_ok=True)
    
    def _generate_id(self, length: int = 10) -> str:
        """تولید شناسه منحصربه‌فرد"""
        chars = string.ascii_letters + string.digits
        return ''.join(random.choice(chars) for _ in range(length))
    
    def _load_json(self, filename: str) -> Dict:
        """بارگذاری فایل JSON"""
        try:
            file_path = self.data_dir / filename
            if file_path.exists():
                with open(file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"خطا در بارگذاری {filename}: {e}")
        return {}
    
    def _save_json(self, filename: str, data: Dict):
        """ذخیره فایل JSON"""
        try:
            file_path = self.data_dir / filename
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"خطا در ذخیره {filename}: {e}")


class UserRepository(BaseRepository):
    """ریپوزیتوری کاربران"""
    
    def __init__(self, data_dir: Path):
        super().__init__(data_dir)
        self.users_file = "users.json"
        self._users = self._load_users()
    
    def _load_users(self) -> Dict[str, User]:
        """بارگذاری کاربران"""
        data = self._load_json(self.users_file)
        users = {}
        for user_id, user_data in data.items():
            try:
                users[user_id] = User.from_dict(user_data)
            except Exception as e:
                logger.error(f"خطا در بارگذاری کاربر {user_id}: {e}")
        return users
    
    def _save_users(self):
        """ذخیره کاربران"""
        data = {user_id: user.to_dict() for user_id, user in self._users.items()}
        self._save_json(self.users_file, data)
    
    def get_user(self, user_id: str) -> Optional[User]:
        """دریافت کاربر"""
        return self._users.get(user_id)
    
    def get_all_users(self) -> List[User]:
        """دریافت تمام کاربران"""
        return list(self._users.values())
    
    def create_user(self, user_data: Dict) -> User:
        """ایجاد کاربر جدید"""
        user_id = user_data.get('id', self._generate_id())
        
        if user_id in self._users:
            raise ValueError(f"کاربر با شناسه {user_id} از قبل وجود دارد")
        
        user = User.from_dict(user_data)
        self._users[user_id] = user
        self._save_users()
        return user
    
    def update_user(self, user_id: str, updates: Dict) -> Optional[User]:
        """به‌روزرسانی کاربر"""
        user = self.get_user(user_id)
        if not user:
            return None
        
        # به‌روزرسانی فیلدها
        for key, value in updates.items():
            if hasattr(user, key):
                setattr(user, key, value)
        
        self._save_users()
        return user
    
    def delete_user(self, user_id: str) -> bool:
        """حذف کاربر"""
        if user_id in self._users:
            del self._users[user_id]
            self._save_users()
            return True
        return False
    
    def count_users(self) -> int:
        """تعداد کاربران"""
        return len(self._users)
    
    def get_premium_users(self) -> List[User]:
        """دریافت کاربران پریمیوم"""
        return [user for user in self._users.values() if user.is_premium()]


class DownloadRepository(BaseRepository):
    """ریپوزیتوری دانلود"""
    
    def __init__(self, data_dir: Path):
        super().__init__(data_dir)
        self.downloads_file = "downloads.json"
        self._downloads = self._load_downloads()
    
    def _load_downloads(self) -> Dict[str, DownloadRequest]:
        """بارگذاری دانلودها"""
        data = self._load_json(self.downloads_file)
        downloads = {}
        for download_id, download_data in data.items():
            try:
                downloads[download_id] = DownloadRequest.from_dict(download_data)
            except Exception as e:
                logger.error(f"خطا در بارگذاری دانلود {download_id}: {e}")
        return downloads
    
    def _save_downloads(self):
        """ذخیره دانلودها"""
        data = {d_id: d.to_dict() for d_id, d in self._downloads.items()}
        self._save_json(self.downloads_file, data)
    
    def create_download(self, user_id: str, url: str, platform: str) -> DownloadRequest:
        """ایجاد درخواست دانلود"""
        download_id = f"DL_{self._generate_id()}"
        
        download = DownloadRequest(
            id=download_id,
            user_id=user_id,
            url=url,
            platform=platform,
            status=DownloadStatus.PENDING,
            requested_at=datetime.now().isoformat()
        )
        
        self._downloads[download_id] = download
        self._save_downloads()
        return download
    
    def get_download(self, download_id: str) -> Optional[DownloadRequest]:
        """دریافت دانلود"""
        return self._downloads.get(download_id)
    
    def get_user_downloads(self, user_id: str) -> List[DownloadRequest]:
        """دریافت دانلودهای کاربر"""
        return [d for d in self._downloads.values() if d.user_id == user_id]
    
    def update_download(self, download_id: str, updates: Dict) -> Optional[DownloadRequest]:
        """به‌روزرسانی دانلود"""
        download = self.get_download(download_id)
        if not download:
            return None
        
        for key, value in updates.items():
            if hasattr(download, key):
                setattr(download, key, value)
        
        self._save_downloads()
        return download
    
    def complete_download(self, download_id: str, file_path: str, file_size: float) -> bool:
        """تکمیل دانلود"""
        download = self.get_download(download_id)
        if not download:
            return False
        
        download.status = DownloadStatus.COMPLETED
        download.completed_at = datetime.now().isoformat()
        download.file_path = file_path
        download.file_size = file_size
        
        self._save_downloads()
        return True
    
    def count_downloads(self) -> int:
        """تعداد دانلودها"""
        return len(self._downloads)
    
    def count_user_downloads(self, user_id: str) -> int:
        """تعداد دانلودهای کاربر"""
        return len(self.get_user_downloads(user_id))


class PaymentRepository(BaseRepository):
    """ریپوزیتوری پرداخت"""
    
    def __init__(self, data_dir: Path):
        super().__init__(data_dir)
        self.payments_file = "payments.json"
        self._payments = self._load_payments()
    
    def _load_payments(self) -> Dict[str, Payment]:
        """بارگذاری پرداخت‌ها"""
        data = self._load_json(self.payments_file)
        payments = {}
        for payment_id, payment_data in data.items():
            try:
                payments[payment_id] = Payment.from_dict(payment_data)
            except Exception as e:
                logger.error(f"خطا در بارگذاری پرداخت {payment_id}: {e}")
        return payments
    
    def _save_payments(self):
        """ذخیره پرداخت‌ها"""
        data = {p_id: p.to_dict() for p_id, p in self._payments.items()}
        self._save_json(self.payments_file, data)
    
    def create_payment(self, user_id: str, plan_id: str, amount_usdt: float, 
                      wallet_address: str) -> Payment:
        """ایجاد پرداخت جدید"""
        payment_id = f"PAY_{self._generate_id()}"
        
        payment = Payment(
            id=payment_id,
            user_id=user_id,
            plan_id=plan_id,
            amount_usdt=amount_usdt,
            wallet_address=wallet_address,
            status=PaymentStatus.PENDING,
            created_at=datetime.now().isoformat()
        )
        
        self._payments[payment_id] = payment
        self._save_payments()
        return payment
    
    def get_payment(self, payment_id: str) -> Optional[Payment]:
        """دریافت پرداخت"""
        return self._payments.get(payment_id)
    
    def get_user_payments(self, user_id: str) -> List[Payment]:
        """دریافت پرداخت‌های کاربر"""
        return [p for p in self._payments.values() if p.user_id == user_id]
    
    def update_payment(self, payment_id: str, updates: Dict) -> Optional[Payment]:
        """به‌روزرسانی پرداخت"""
        payment = self.get_payment(payment_id)
        if not payment:
            return None
        
        for key, value in updates.items():
            if hasattr(payment, key):
                setattr(payment, key, value)
        
        self._save_payments()
        return payment
    
    def confirm_payment(self, payment_id: str, txid: str) -> bool:
        """تأیید پرداخت"""
        payment = self.get_payment(payment_id)
        if not payment:
            return False
        
        payment.status = PaymentStatus.CONFIRMED
        payment.txid = txid
        payment.confirmed_at = datetime.now().isoformat()
        
        # محاسبه تاریخ انقضا (اگر plan_id مشخص باشد)
        # این بخش باید با سرویس اشتراک‌ها تکمیل شود
        
        self._save_payments()
        return True
    
    def complete_payment(self, payment_id: str) -> bool:
        """تکمیل پرداخت"""
        payment = self.get_payment(payment_id)
        if not payment:
            return False
        
        payment.status = PaymentStatus.COMPLETED
        self._save_payments()
        return True


class AdRepository(BaseRepository):
    """ریپوزیتوری تبلیغات"""
    
    def __init__(self, data_dir: Path):
        super().__init__(data_dir)
        self.ads_file = "ads.json"
        self._campaigns = self._load_campaigns()
    
    def _load_campaigns(self) -> Dict[str, AdCampaign]:
        """بارگذاری کمپین‌ها"""
        data = self._load_json(self.ads_file)
        campaigns = {}
        for campaign_id, campaign_data in data.items():
            try:
                campaigns[campaign_id] = AdCampaign.from_dict(campaign_data)
            except Exception as e:
                logger.error(f"خطا در بارگذاری کمپین {campaign_id}: {e}")
        return campaigns
    
    def _save_campaigns(self):
        """ذخیره کمپین‌ها"""
        data = {c_id: c.to_dict() for c_id, c in self._campaigns.items()}
        self._save_json(self.ads_file, data)
    
    def create_campaign(self, campaign_data: Dict) -> AdCampaign:
        """ایجاد کمپین جدید"""
        campaign_id = f"AD_{self._generate_id()}"
        campaign_data['id'] = campaign_id
        
        campaign = AdCampaign.from_dict(campaign_data)
        self._campaigns[campaign_id] = campaign
        self._save_campaigns()
        return campaign
    
    def get_campaign(self, campaign_id: str) -> Optional[AdCampaign]:
        """دریافت کمپین"""
        return self._campaigns.get(campaign_id)
    
    def get_active_campaigns(self) -> List[AdCampaign]:
        """دریافت کمپین‌های فعال"""
        return [c for c in self._campaigns.values() if c.is_active]
    
    def record_impression(self, campaign_id: str) -> bool:
        """ثبت نمایش تبلیغ"""
        campaign = self.get_campaign(campaign_id)
        if not campaign:
            return False
        
        campaign.impressions += 1
        self._save_campaigns()
        return True
    
    def record_click(self, campaign_id: str) -> bool:
        """ثبت کلیک روی تبلیغ"""
        campaign = self.get_campaign(campaign_id)
        if not campaign:
            return False
        
        campaign.clicks += 1
        self._save_campaigns()
        return True


# =========================
# Service Classes
# =========================

class UserService:
    """سرویس مدیریت کاربران"""
    
    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo
    
    def register_user(self, user_id: str, username: str, first_name: str, 
                     last_name: str = None) -> User:
        """ثبت کاربر جدید"""
        # بررسی وجود کاربر
        existing_user = self.user_repo.get_user(user_id)
        if existing_user:
            existing_user.update_last_seen()
            self.user_repo.update_user(user_id, {'last_seen': existing_user.last_seen})
            return existing_user
        
        # ایجاد کاربر جدید
        user_data = {
            'id': user_id,
            'username': username,
            'first_name': first_name,
            'last_name': last_name,
            'join_date': datetime.now().isoformat(),
            'status': UserStatus.FREE.value,
            'last_seen': datetime.now().isoformat()
        }
        
        return self.user_repo.create_user(user_data)
    
    def get_user_profile(self, user_id: str) -> Optional[Dict]:
        """دریافت پروفایل کاربر"""
        user = self.user_repo.get_user(user_id)
        if not user:
            return None
        
        download_repo = DownloadRepository(self.user_repo.data_dir)
        payment_repo = PaymentRepository(self.user_repo.data_dir)
        
        download_count = download_repo.count_user_downloads(user_id)
        payment_count = len(payment_repo.get_user_payments(user_id))
        
        return {
            'user': user.to_dict(),
            'stats': {
                'downloads': download_count,
                'payments': payment_count,
                'balance': user.balance
            }
        }
    
    def upgrade_to_premium(self, user_id: str, plan_id: str, expiry_date: str) -> bool:
        """ارتقا کاربر به پریمیوم"""
        user = self.user_repo.get_user(user_id)
        if not user:
            return False
        
        user.status = UserStatus.PREMIUM
        # می‌توانیم expiry_date را در metadata کاربر ذخیره کنیم
        self.user_repo.update_user(user_id, {
            'status': UserStatus.PREMIUM,
            'balance': user.balance  # حفظ موجودی
        })
        
        logger.info(f"کاربر {user_id} به پریمیوم ارتقا یافت")
        return True
    
    def check_download_limit(self, user_id: str, max_free_downloads: int = 3) -> Tuple[bool, str]:
        """بررسی محدودیت دانلود"""
        user = self.user_repo.get_user(user_id)
        if not user:
            return False, "کاربر یافت نشد"
        
        if user.is_premium():
            return True, "پریمیوم"
        
        download_repo = DownloadRepository(self.user_repo.data_dir)
        download_count = download_repo.count_user_downloads(user_id)
        
        if download_count < max_free_downloads:
            remaining = max_free_downloads - download_count
            return True, f"رایگان ({remaining} باقی‌مانده)"
        else:
            return False, f"دانلودهای رایگان شما به پایان رسیده است."
    
    def get_system_stats(self) -> Dict:
        """دریافت آمار سیستم"""
        total_users = self.user_repo.count_users()
        premium_users = len(self.user_repo.get_premium_users())
        
        download_repo = DownloadRepository(self.user_repo.data_dir)
        payment_repo = PaymentRepository(self.user_repo.data_dir)
        
        total_downloads = download_repo.count_downloads()
        
        # محاسبه درآمد
        total_revenue = 0
        for payment in payment_repo._payments.values():
            if payment.status == PaymentStatus.COMPLETED:
                total_revenue += payment.amount_usdt
        
        # کاربران امروز
        today = datetime.now().date().isoformat()
        today_users = sum(
            1 for user in self.user_repo._users.values()
            if datetime.fromisoformat(user.join_date).date().isoformat() == today
        )
        
        return {
            'total_users': total_users,
            'premium_users': premium_users,
            'total_downloads': total_downloads,
            'total_revenue': total_revenue,
            'today_users': today_users,
            'premium_percentage': (premium_users / total_users * 100) if total_users > 0 else 0
        }


class DownloadService:
    """سرویس مدیریت دانلود"""
    
    def __init__(self, download_repo: DownloadRepository, user_service: UserService):
        self.download_repo = download_repo
        self.user_service = user_service
        
        # پلتفرم‌های پشتیبانی شده
        self.supported_platforms = {
            'youtube.com': 'YouTube',
            'youtu.be': 'YouTube',
            'instagram.com': 'Instagram',
            'instagr.am': 'Instagram',
            'tiktok.com': 'TikTok',
            'twitter.com': 'Twitter',
            'x.com': 'Twitter',
            'facebook.com': 'Facebook',
            'fb.watch': 'Facebook',
            'reddit.com': 'Reddit',
            'dailymotion.com': 'Dailymotion',
            'vimeo.com': 'Vimeo',
            'twitch.tv': 'Twitch'
        }
    
    def validate_url(self, url: str) -> Tuple[bool, Optional[str]]:
        """اعتبارسنجی URL"""
        if not url.startswith(('http://', 'https://')):
            return False, "URL باید با http:// یا https:// شروع شود"
        
        url_lower = url.lower()
        for domain, platform in self.supported_platforms.items():
            if domain in url_lower:
                return True, platform
        
        return False, "پلتفرم پشتیبانی نمی‌شود"
    
    def create_download_request(self, user_id: str, url: str, 
                               check_limit: bool = True) -> Tuple[bool, Union[str, DownloadRequest]]:
        """ایجاد درخواست دانلود"""
        # اعتبارسنجی URL
        is_valid, platform = self.validate_url(url)
        if not is_valid:
            return False, platform
        
        # بررسی محدودیت کاربر
        if check_limit:
            can_download, message = self.user_service.check_download_limit(user_id)
            if not can_download:
                return False, message
        
        # ایجاد درخواست دانلود
        download = self.download_repo.create_download(user_id, url, platform)
        logger.info(f"درخواست دانلود ایجاد شد: {download.id} برای کاربر {user_id}")
        
        return True, download
    
    def get_download_info(self, download_id: str) -> Optional[Dict]:
        """دریافت اطلاعات دانلود"""
        download = self.download_repo.get_download(download_id)
        if not download:
            return None
        
        return {
            'download': download.to_dict(),
            'status_text': self._get_status_text(download.status),
            'estimated_time': self._estimate_download_time(download)
        }
    
    def _get_status_text(self, status: DownloadStatus) -> str:
        """متن وضعیت"""
        status_texts = {
            DownloadStatus.PENDING: "⏳ در انتظار پردازش",
            DownloadStatus.PROCESSING: "🔍 در حال پردازش",
            DownloadStatus.COMPLETED: "✅ تکمیل شده",
            DownloadStatus.FAILED: "❌ ناموفق"
        }
        return status_texts.get(status, "نامشخص")
    
    def _estimate_download_time(self, download: DownloadRequest) -> str:
        """تخمین زمان دانلود"""
        if download.status == DownloadStatus.COMPLETED and download.completed_at:
            requested = datetime.fromisoformat(download.requested_at)
            completed = datetime.fromisoformat(download.completed_at)
            duration = (completed - requested).total_seconds()
            
            if duration < 60:
                return f"{int(duration)} ثانیه"
            else:
                return f"{int(duration // 60)} دقیقه"
        
        return "نامشخص"
    
    def get_available_formats(self, platform: str) -> List[Dict]:
        """دریافت فرمت‌های موجود"""
        formats = {
            'YouTube': [
                {'id': '360p', 'name': '360p', 'quality': 'پایین'},
                {'id': '480p', 'name': '480p', 'quality': 'متوسط'},
                {'id': '720p', 'name': '720p (HD)', 'quality': 'بالا'},
                {'id': '1080p', 'name': '1080p (Full HD)', 'quality': 'عالی'},
                {'id': 'mp3', 'name': 'MP3', 'quality': 'صوت'}
            ],
            'Instagram': [
                {'id': 'sd', 'name': 'SD', 'quality': 'استاندارد'},
                {'id': 'hd', 'name': 'HD', 'quality': 'با کیفیت'}
            ],
            'TikTok': [
                {'id': 'watermark', 'name': 'با واترمارک', 'quality': 'پایین'},
                {'id': 'nowatermark', 'name': 'بدون واترمارک', 'quality': 'بالا'}
            ]
        }
        
        return formats.get(platform, [
            {'id': 'default', 'name': 'پیش‌فرض', 'quality': 'استاندارد'}
        ])
    
    def simulate_download(self, download_id: str, quality: str = None) -> bool:
        """شبیه‌سازی دانلود (برای تست)"""
        download = self.download_repo.get_download(download_id)
        if not download:
            return False
        
        # شبیه‌سازی پردازش
        download.status = DownloadStatus.PROCESSING
        self.download_repo.update_download(download_id, {'status': download.status})
        
        # در واقعیت، اینجا باید با API دانلود ارتباط برقرار کنیم
        # برای نمونه، شبیه‌سازی می‌کنیم
        
        file_size = random.uniform(10, 500)  # MB
        file_path = f"/downloads/{download_id}_{quality or 'default'}.mp4"
        
        download.quality = quality
        download.format = 'mp4'
        download.file_size = file_size
        download.file_path = file_path
        
        return self.download_repo.complete_download(download_id, file_path, file_size)


class PaymentService:
    """سرویس مدیریت پرداخت"""
    
    def __init__(self, payment_repo: PaymentRepository, user_service: UserService):
        self.payment_repo = payment_repo
        self.user_service = user_service
        
        # طرح‌های اشتراک
        self.plans = {
            "monthly": PremiumPlan(
                id="monthly",
                name="۱ ماهه",
                duration_days=30,
                price_usdt=5.0,
                discount_percent=0,
                features=[
                    "✅ دانلود نامحدود",
                    "✅ کیفیت 4K",
                    "✅ حذف واترمارک"
                ]
            ),
            "quarterly": PremiumPlan(
                id="quarterly",
                name="۳ ماهه",
                duration_days=90,
                price_usdt=12.0,
                discount_percent=20,
                features=[
                    "✅ دانلود نامحدود",
                    "✅ کیفیت 4K",
                    "✅ حذف واترمارک",
                    "🚀 سرعت بالا"
                ]
            ),
            "semi_annual": PremiumPlan(
                id="semi_annual",
                name="۶ ماهه",
                duration_days=180,
                price_usdt=20.0,
                discount_percent=33,
                features=[
                    "✅ دانلود نامحدود",
                    "✅ کیفیت 4K",
                    "✅ حذف واترمارک",
                    "🚀 سرعت بالا",
                    "☁️ ذخیره در ابر"
                ]
            ),
            "annual": PremiumPlan(
                id="annual",
                name="۱ ساله",
                duration_days=365,
                price_usdt=35.0,
                discount_percent=42,
                features=[
                    "✅ دانلود نامحدود",
                    "✅ کیفیت 4K",
                    "✅ حذف واترمارک",
                    "🚀 سرعت بالا",
                    "☁️ ذخیره در ابر",
                    "👑 پشتیبانی VIP"
                ]
            )
        }
    
    def get_plans(self) -> List[PremiumPlan]:
        """دریافت طرح‌های اشتراک"""
        return list(self.plans.values())
    
    def get_plan(self, plan_id: str) -> Optional[PremiumPlan]:
        """دریافت طرح"""
        return self.plans.get(plan_id)
    
    def create_payment(self, user_id: str, plan_id: str, wallet_address: str) -> Optional[Payment]:
        """ایجاد پرداخت جدید"""
        plan = self.get_plan(plan_id)
        if not plan:
            logger.error(f"طرح {plan_id} یافت نشد")
            return None
        
        user = self.user_service.user_repo.get_user(user_id)
        if not user:
            logger.error(f"کاربر {user_id} یافت نشد")
            return None
        
        amount = plan.get_discounted_price()
        payment = self.payment_repo.create_payment(user_id, plan_id, amount, wallet_address)
        
        logger.info(f"پرداخت ایجاد شد: {payment.id} برای کاربر {user_id}")
        return payment
    
    def validate_txid(self, txid: str) -> bool:
        """اعتبارسنجی TXID"""
        if not txid or len(txid) < 10:
            return False
        
        # الگوی TXID (حروف و اعداد)
        pattern = r'^[a-fA-F0-9]{10,64}$'
        return bool(re.match(pattern, txid))
    
    def confirm_payment(self, payment_id: str, txid: str) -> Tuple[bool, str]:
        """تأیید پرداخت"""
        if not self.validate_txid(txid):
            return False, "Transaction ID نامعتبر است"
        
        payment = self.payment_repo.get_payment(payment_id)
        if not payment:
            return False, "پرداخت یافت نشد"
        
        if payment.status != PaymentStatus.PENDING:
            return False, f"پرداخت در وضعیت {payment.status.value} است"
        
        # تأیید پرداخت
        success = self.payment_repo.confirm_payment(payment_id, txid)
        if not success:
            return False, "خطا در تأیید پرداخت"
        
        # ارتقای کاربر به پریمیوم
        plan = self.get_plan(payment.plan_id)
        if plan:
            expiry_date = (datetime.now() + timedelta(days=plan.duration_days)).strftime("%Y-%m-%d")
            self.user_service.upgrade_to_premium(payment.user_id, payment.plan_id, expiry_date)
            
            # تکمیل پرداخت
            self.payment_repo.complete_payment(payment_id)
            
            logger.info(f"پرداخت {payment_id} تأیید شد و کاربر ارتقا یافت")
            return True, "پرداخت با موفقیت تأیید شد و اشتراک فعال گردید"
        
        return False, "خطا در فعال‌سازی اشتراک"
    
    def get_payment_instructions(self, plan_id: str, wallet_address: str) -> Dict:
        """دریافت دستورالعمل پرداخت"""
        plan = self.get_plan(plan_id)
        if not plan:
            return {}
        
        amount = plan.get_discounted_price()
        
        return {
            'plan': plan.to_dict(),
            'amount': amount,
            'wallet_address': wallet_address,
            'instructions': [
                f"1. مبلغ {amount} دلار USDT را به آدرس زیر واریز کنید:",
                f"   `{wallet_address}`",
                "2. حتماً از شبکه TRC20 استفاده کنید",
                "3. پس از واریز، Transaction ID (TXID) را ذخیره کنید",
                "4. TXID را در ربات ارسال کنید تا پرداخت تأیید شود"
            ]
        }
    
    def get_user_payments(self, user_id: str) -> List[Dict]:
        """دریافت پرداخت‌های کاربر"""
        payments = self.payment_repo.get_user_payments(user_id)
        result = []
        
        for payment in payments:
            plan = self.get_plan(payment.plan_id)
            result.append({
                'payment': payment.to_dict(),
                'plan_name': plan.name if plan else 'نامشخص',
                'status_text': self._get_payment_status_text(payment.status)
            })
        
        return result
    
    def _get_payment_status_text(self, status: PaymentStatus) -> str:
        """متن وضعیت پرداخت"""
        status_texts = {
            PaymentStatus.PENDING: "⏳ در انتظار پرداخت",
            PaymentStatus.CONFIRMED: "✅ پرداخت تأیید شده",
            PaymentStatus.COMPLETED: "✅ تکمیل شده",
            PaymentStatus.FAILED: "❌ ناموفق",
            PaymentStatus.REFUNDED: "↩️ بازپرداخت شده"
        }
        return status_texts.get(status, "نامشخص")


class AdService:
    """سرویس مدیریت تبلیغات"""
    
    def __init__(self, ad_repo: AdRepository):
        self.ad_repo = ad_repo
    
    def create_campaign(self, title: str, ad_type: str, budget: float, 
                       **kwargs) -> AdCampaign:
        """ایجاد کمپین تبلیغاتی"""
        campaign_data = {
            'title': title,
            'ad_type': ad_type,
            'budget_usdt': budget,
            **kwargs
        }
        
        return self.ad_repo.create_campaign(campaign_data)
    
    def get_random_ad(self, user_id: str = None) -> Optional[Dict]:
        """دریافت تبلیغ تصادفی"""
        active_campaigns = self.ad_repo.get_active_campaigns()
        if not active_campaigns:
            return None
        
        # انتخاب تصادفی یک کمپین
        campaign = random.choice(active_campaigns)
        
        # ثبت نمایش
        self.ad_repo.record_impression(campaign.id)
        
        # ساخت پاسخ
        ad_data = {
            'campaign_id': campaign.id,
            'title': campaign.title,
            'type': campaign.ad_type.value,
            'text': campaign.text,
            'image_url': campaign.image_url,
            'video_url': campaign.video_url,
            'link': campaign.link,
            'cta': self._get_cta_text(campaign.ad_type)
        }
        
        return ad_data
    
    def _get_cta_text(self, ad_type: AdType) -> str:
        """متن Call to Action"""
        cta_texts = {
            AdType.BANNER: "👆 برای اطلاعات بیشتر کلیک کنید",
            AdType.INTERSTITIAL: "بستن تبلیغ",
            AdType.REWARDED: "🎁 مشاهده و دریافت پاداش"
        }
        return cta_texts.get(ad_type, "بیشتر بدانید")
    
    def record_ad_click(self, campaign_id: str, user_id: str = None) -> bool:
        """ثبت کلیک روی تبلیغ"""
        success = self.ad_repo.record_click(campaign_id)
        if success and user_id:
            # می‌توانیم پاداش به کاربر بدهیم
            logger.info(f"کاربر {user_id} روی تبلیغ {campaign_id} کلیک کرد")
        
        return success
    
    def get_campaign_stats(self, campaign_id: str) -> Optional[Dict]:
        """دریافت آمار کمپین"""
        campaign = self.ad_repo.get_campaign(campaign_id)
        if not campaign:
            return None
        
        # محاسبه CTR
        ctr = (campaign.clicks / campaign.impressions * 100) if campaign.impressions > 0 else 0
        
        # محاسبه هزینه هر کلیک
        cpc = (campaign.spent_usdt / campaign.clicks) if campaign.clicks > 0 else 0
        
        # محاسبه روزهای باقی‌مانده
        days_left = "نامحدود"
        if campaign.end_date:
            end = datetime.fromisoformat(campaign.end_date)
            days_left = max(0, (end - datetime.now()).days)
        
        return {
            'campaign': campaign.to_dict(),
            'stats': {
                'ctr': round(ctr, 2),
                'cpc': round(cpc, 2),
                'days_left': days_left,
                'budget_remaining': campaign.budget_usdt - campaign.spent_usdt
            }
        }


# =========================
# Factory & Manager Classes
# =========================

class DomainManager:
    """مدیریت یکپارچه دامنه"""
    
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        
        # ایجاد ریپوزیتوری‌ها
        self.user_repo = UserRepository(data_dir)
        self.download_repo = DownloadRepository(data_dir)
        self.payment_repo = PaymentRepository(data_dir)
        self.ad_repo = AdRepository(data_dir)
        
        # ایجاد سرویس‌ها
        self.user_service = UserService(self.user_repo)
        self.download_service = DownloadService(self.download_repo, self.user_service)
        self.payment_service = PaymentService(self.payment_repo, self.user_service)
        self.ad_service = AdService(self.ad_repo)
    
    def get_system_stats(self) -> Dict:
        """دریافت آمار کامل سیستم"""
        user_stats = self.user_service.get_system_stats()
        
        # آمار تبلیغات
        active_campaigns = self.ad_repo.get_active_campaigns()
        total_ad_spent = sum(c.spent_usdt for c in active_campaigns)
        
        return {
            **user_stats,
            'total_ads': len(active_campaigns),
            'total_ad_spent': total_ad_spent
        }
    
    def cleanup_old_data(self, days: int = 30):
        """پاکسازی داده‌های قدیمی"""
        cutoff_date = datetime.now() - timedelta(days=days)
        
        # پاکسازی دانلودهای قدیمی
        old_downloads = [
            d_id for d_id, d in self.download_repo._downloads.items()
            if datetime.fromisoformat(d.requested_at) < cutoff_date
            and d.status == DownloadStatus.COMPLETED
        ]
        
        for d_id in old_downloads:
            del self.download_repo._downloads[d_id]
        
        self.download_repo._save_downloads()
        logger.info(f"پاکسازی {len(old_downloads)} دانلود قدیمی")
    
    def backup_data(self, backup_dir: Path):
        """پشتیبان‌گیری از داده‌ها"""
        backup_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        for filename in ["users.json", "downloads.json", "payments.json", "ads.json"]:
            source = self.data_dir / filename
            if source.exists():
                target = backup_dir / f"{timestamp}_{filename}"
                import shutil
                shutil.copy2(source, target)
        
        logger.info(f"پشتیبان‌گیری در {backup_dir} انجام شد")


# =========================
# Export
# =========================

__all__ = [
    # Enums
    'UserStatus',
    'DownloadStatus',
    'PaymentStatus',
    'AdType',
    
    # Data Classes
    'User',
    'PremiumPlan',
    'DownloadRequest',
    'Payment',
    'AdCampaign',
    
    # Repositories
    'UserRepository',
    'DownloadRepository',
    'PaymentRepository',
    'AdRepository',
    
    # Services
    'UserService',
    'DownloadService',
    'PaymentService',
    'AdService',
    
    # Manager
    'DomainManager'
]