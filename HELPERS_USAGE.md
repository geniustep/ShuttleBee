# 📚 دليل استخدام Helper Utilities - ShuttleBee

هذا الدليل يوضح كيفية استخدام مكتبة Helper Utilities الجديدة في ShuttleBee.

---

## 📋 المحتويات

1. [ValidationHelper](#validationhelper) - التحقق من صحة البيانات
2. [RetryUtils](#retryutils) - إعادة المحاولة التلقائية
3. [NotificationProviders](#notificationproviders) - محولات مزودي الخدمة
4. [LoggingUtils](#loggingutils) - التسجيل المنظم
5. [ConflictDetector](#conflictdetector) - كشف التعارضات
6. [SecurityUtils](#securityutils) - الأمان
7. [RateLimiter](#ratelimiter) - تحديد المعدل

---

## 🔍 ValidationHelper

### نظرة عامة

`ValidationHelper` يوفر دوال مركزية للتحقق من صحة البيانات مثل أرقام الهواتف، البريد الإلكتروني، والإحداثيات الجغرافية.

### أمثلة الاستخدام

#### 1. التحقق من رقم الهاتف

```python
from shuttlebee.helpers.validation import ValidationHelper

# التحقق الأساسي
phone = "+212612345678"
is_valid = ValidationHelper.validate_phone(phone, country_code='MA', raise_error=False)

if is_valid:
    print("رقم الهاتف صحيح")
else:
    print("رقم الهاتف غير صحيح")

# التحقق مع رفع خطأ
try:
    ValidationHelper.validate_phone("123", raise_error=True)
except ValidationError as e:
    print(f"خطأ: {e}")

# استخدام مكتبة phonenumbers (إذا كانت مثبتة)
phone = "+212612345678"
is_valid = ValidationHelper.validate_phone(
    phone, 
    country_code='MA',
    use_phonenumbers=True  # يستخدم مكتبة phonenumbers إذا كانت متاحة
)
```

#### 2. التحقق من البريد الإلكتروني

```python
from shuttlebee.helpers.validation import ValidationHelper

email = "user@example.com"
is_valid = ValidationHelper.validate_email(email, raise_error=False)

if is_valid:
    print("البريد الإلكتروني صحيح")

# مع رفع خطأ
try:
    ValidationHelper.validate_email("invalid-email", raise_error=True)
except ValidationError as e:
    print(f"خطأ: {e}")
```

#### 3. التحقق من الإحداثيات الجغرافية

```python
from shuttlebee.helpers.validation import ValidationHelper

# التحقق من خط العرض (Latitude)
lat = 33.5731
is_valid = ValidationHelper.validate_latitude(lat, raise_error=False)

# التحقق من خط الطول (Longitude)
lon = -7.5898
is_valid = ValidationHelper.validate_longitude(lon, raise_error=False)

# التحقق من كلا الإحداثيات معاً
try:
    ValidationHelper.validate_coordinates(lat, lon, raise_error=True)
except ValidationError as e:
    print(f"خطأ: {e}")
```

---

## 🔄 RetryUtils

### نظرة عامة

`RetryUtils` يوفر آلية إعادة المحاولة التلقائية مع Exponential Backoff و Jitter لتحسين موثوقية الطلبات.

### أمثلة الاستخدام

#### 1. استخدام Decorator

```python
from shuttlebee.helpers.retry_utils import retry_with_backoff, RetryConfig

# استخدام الإعدادات الافتراضية
@retry_with_backoff
def send_api_request(url, data):
    response = requests.post(url, json=data, timeout=10)
    response.raise_for_status()
    return response.json()

# استخدام إعدادات مخصصة
config = RetryConfig(
    max_retries=5,
    initial_delay=2.0,
    max_delay=120.0,
    exponential_base=2.0,
    jitter=True
)

@retry_with_backoff(config=config)
def critical_api_call(url, data):
    response = requests.post(url, json=data, timeout=10)
    response.raise_for_status()
    return response.json()

# تحديد الاستثناءات التي يجب إعادة المحاولة لها
@retry_with_backoff(
    retry_on=(requests.exceptions.Timeout, requests.exceptions.ConnectionError)
)
def unreliable_api_call(url):
    return requests.get(url, timeout=5)
```

#### 2. استخدام Context Manager

```python
from shuttlebee.helpers.retry_utils import RetryContext

config = RetryConfig(max_retries=3, initial_delay=1.0)

with RetryContext(config) as retry:
    for attempt in retry:
        try:
            result = send_api_request(url, data)
            break  # نجح، اخرج من الحلقة
        except Exception as e:
            if attempt.is_last:
                raise  # آخر محاولة، ارفع الخطأ
            # سيتم الانتظار تلقائياً قبل المحاولة التالية
```

#### 3. استخدام يدوي

```python
from shuttlebee.helpers.retry_utils import retry_with_backoff

def send_notification(phone, message):
    # إعادة المحاولة يدوياً
    config = RetryConfig(max_retries=3)
    
    for attempt in range(config.max_retries):
        try:
            response = requests.post(
                api_url,
                json={'phone': phone, 'message': message},
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            if attempt == config.max_retries - 1:
                raise  # آخر محاولة
            delay = config.get_delay(attempt)
            time.sleep(delay)
```

---

## 📱 NotificationProviders

### نظرة عامة

`NotificationProviders` يوفر محولات موحدة لمزودي الخدمة المختلفة (SMS, WhatsApp, Push).

### أمثلة الاستخدام

#### 1. استخدام ProviderFactory

```python
from shuttlebee.helpers.notification_providers import ProviderFactory

# إنشاء مزود SMS (Twilio)
sms_provider = ProviderFactory.create_provider(
    provider_type='twilio_sms',
    api_url='https://api.twilio.com/2010-04-01/Accounts/ACxxx/Messages.json',
    api_key='your_account_sid',
    api_secret='your_auth_token'
)

# إرسال رسالة SMS
response = sms_provider.send(
    recipient='+212612345678',
    message='مرحباً! حافلتك تقترب من المحطة.'
)

print(f"Message ID: {response['message_id']}")
print(f"Status: {response['status']}")

# إنشاء مزود WhatsApp
whatsapp_provider = ProviderFactory.create_provider(
    provider_type='whatsapp_business',
    api_url='https://graph.facebook.com/v18.0/your_phone_number_id/messages',
    api_key='your_access_token',
    phone_number_id='your_phone_number_id'
)

# إرسال رسالة WhatsApp
response = whatsapp_provider.send(
    recipient='212612345678',
    message='مرحباً! حافلتك تقترب من المحطة.'
)
```

#### 2. إنشاء مزود مخصص

```python
from shuttlebee.helpers.notification_providers import NotificationProvider
import requests

class CustomSMSProvider(NotificationProvider):
    """مزود SMS مخصص"""
    
    def send(self, recipient: str, message: str, **kwargs) -> dict:
        """إرسال SMS عبر مزود مخصص"""
        try:
            response = requests.post(
                self.api_url,
                headers={
                    'Authorization': f'Bearer {self.api_key}',
                    'Content-Type': 'application/json'
                },
                json={
                    'to': recipient,
                    'message': message,
                    **kwargs
                },
                timeout=self.timeout
            )
            response.raise_for_status()
            data = response.json()
            
            return {
                'message_id': data.get('id'),
                'status': 'sent',
                'provider_response': data
            }
        except Exception as e:
            raise UserError(_('Failed to send SMS: %s') % str(e))

# استخدام المزود المخصص
custom_provider = CustomSMSProvider(
    api_url='https://api.custom-sms.com/send',
    api_key='your_api_key'
)

response = custom_provider.send('+212612345678', 'Hello!')
```

---

## 📊 LoggingUtils

### نظرة عامة

`LoggingUtils` يوفر تسجيل منظم بتنسيق JSON مع قياس وقت التنفيذ تلقائياً.

### أمثلة الاستخدام

#### 1. استخدام StructuredLogger

```python
from shuttlebee.helpers.logging_utils import StructuredLogger, notification_logger

# استخدام logger جاهز
notification_logger.info(
    'notification_sent',
    extra={
        'notification_id': 123,
        'channel': 'sms',
        'recipient': '+212612345678',
        'status': 'sent'
    }
)

# إنشاء logger مخصص
logger = StructuredLogger('shuttlebee.custom')

logger.info(
    'custom_event',
    extra={
        'user_id': 456,
        'action': 'trip_created',
        'trip_id': 789
    }
)
```

#### 2. قياس وقت التنفيذ

```python
from shuttlebee.helpers.logging_utils import StructuredLogger
import time

logger = StructuredLogger('shuttlebee.performance')

# قياس وقت التنفيذ يدوياً
start_time = time.time()
# ... كودك هنا ...
execution_time = time.time() - start_time

logger.info(
    'operation_completed',
    extra={
        'operation': 'send_notifications',
        'execution_time_seconds': execution_time,
        'notifications_count': 10
    }
)
```

#### 3. استخدام Context Manager للقياس التلقائي

```python
from shuttlebee.helpers.logging_utils import StructuredLogger

logger = StructuredLogger('shuttlebee.performance')

# سيتم قياس الوقت تلقائياً
with logger.measure_time('send_batch_notifications'):
    # ... كود إرسال الإشعارات ...
    send_notifications_batch(notifications)
# سيتم تسجيل الوقت تلقائياً عند الخروج من context
```

---

## ⚠️ ConflictDetector

### نظرة عامة

`ConflictDetector` يوفر كشف تعارضات محسّن للمركبات والسائقين باستخدام استعلامات قاعدة البيانات المباشرة.

### أمثلة الاستخدام

#### 1. التحقق من تعارض المركبة

```python
from shuttlebee.helpers.conflict_detector import ConflictDetector
from odoo import fields

# الحصول على موديل الرحلات
trip_model = self.env['shuttle.trip']

# إنشاء detector
detector = ConflictDetector(trip_model)

# التحقق من تعارض المركبة
trip_date = fields.Date.today()
start_time = fields.Datetime.now()
end_time = start_time + timedelta(hours=2)

has_conflict, conflict_data = detector.check_vehicle_conflict(
    vehicle_id=1,
    trip_date=trip_date,
    start_time=start_time,
    end_time=end_time,
    exclude_trip_id=None  # للرحلات الجديدة
)

if has_conflict:
    print(f"تعارض موجود! الرحلة المتعارضة: {conflict_data['conflicting_trip'].name}")
    raise ValidationError(_('Vehicle is already assigned to another trip!'))
```

#### 2. التحقق من تعارض السائق

```python
# التحقق من تعارض السائق
has_conflict, conflict_data = detector.check_driver_conflict(
    driver_id=5,
    trip_date=trip_date,
    start_time=start_time,
    end_time=end_time,
    exclude_trip_id=10  # استثناء رحلة محددة (للتحديث)
)

if has_conflict:
    raise ValidationError(_('Driver is already assigned to another trip!'))
```

#### 3. التحقق من كلا التعارضات معاً

```python
# التحقق من كلا التعارضات في استعلام واحد
conflicts = detector.check_all_conflicts(
    vehicle_id=1,
    driver_id=5,
    trip_date=trip_date,
    start_time=start_time,
    end_time=end_time,
    exclude_trip_id=None
)

if conflicts['vehicle_conflict']:
    print("تعارض في المركبة!")
if conflicts['driver_conflict']:
    print("تعارض في السائق!")
```

---

## 🔒 SecurityUtils

### نظرة عامة

`SecurityUtils` يوفر دوال للأمان مثل عرض القوالب الآمن وإدارة بيانات الاعتماد.

### أمثلة الاستخدام

#### 1. عرض القوالب الآمن

```python
from shuttlebee.helpers.security_utils import template_renderer

# عرض قالب آمن
template = "مرحباً {{ passenger_name }}! حافلتك تقترب من {{ stop_name }}."
context = {
    'passenger_name': 'محمد',
    'stop_name': 'محطة المدرسة'
}

safe_message = template_renderer.render(template, context)
print(safe_message)  # "مرحباً محمد! حافلتك تقترب من محطة المدرسة."

# منع حقن الكود
malicious_template = "{{ malicious_code }}"
context = {'malicious_code': '<script>alert("XSS")</script>'}

safe_message = template_renderer.render(malicious_template, context)
# سيتم تنظيف الكود تلقائياً
```

#### 2. تشفير بيانات الاعتماد

```python
from shuttlebee.helpers.security_utils import CredentialManager

# إنشاء manager
credential_manager = CredentialManager()

# تشفير بيانات الاعتماد
api_key = "my_secret_api_key"
encrypted = credential_manager.encrypt(api_key)

# فك التشفير
decrypted = credential_manager.decrypt(encrypted)
assert decrypted == api_key
```

---

## 🚦 RateLimiter

### نظرة عامة

`RateLimiter` يوفر تحديد المعدل لمنع استنفاد حصة API باستخدام Token Bucket Algorithm.

### أمثلة الاستخدام

#### 1. استخدام Rate Limiter للإشعارات

```python
from shuttlebee.helpers.rate_limiter import notification_rate_limiter

# التحقق من إمكانية الإرسال
channel = 'sms'
if notification_rate_limiter.can_send(channel):
    # إرسال الإشعار
    send_sms(phone, message)
    # تسجيل الاستخدام
    notification_rate_limiter.consume(channel)
else:
    print("تم الوصول للحد الأقصى من الإشعارات!")
    # انتظر حتى يتوفر token
    wait_time = notification_rate_limiter.get_wait_time(channel)
    print(f"انتظر {wait_time} ثانية")
```

#### 2. إنشاء Rate Limiter مخصص

```python
from shuttlebee.helpers.rate_limiter import RateLimiter

# إنشاء limiter مخصص
custom_limiter = RateLimiter(
    rate_per_minute=60,  # 60 طلب في الدقيقة
    burst_size=10  # 10 طلبات دفعة واحدة
)

# استخدام
if custom_limiter.can_send('api_calls'):
    make_api_call()
    custom_limiter.consume('api_calls')
```

---

## 🔗 أمثلة متكاملة

### مثال: إرسال إشعار مع إعادة المحاولة وتحديد المعدل

```python
from shuttlebee.helpers.validation import ValidationHelper
from shuttlebee.helpers.retry_utils import retry_with_backoff
from shuttlebee.helpers.notification_providers import ProviderFactory
from shuttlebee.helpers.rate_limiter import notification_rate_limiter
from shuttlebee.helpers.logging_utils import notification_logger

def send_notification_safely(phone, message, channel='sms'):
    """إرسال إشعار مع جميع الحماية"""
    
    # 1. التحقق من صحة البيانات
    ValidationHelper.validate_phone(phone, raise_error=True)
    
    # 2. التحقق من Rate Limit
    if not notification_rate_limiter.can_send(channel):
        wait_time = notification_rate_limiter.get_wait_time(channel)
        raise UserError(_('Rate limit exceeded. Wait %s seconds.') % wait_time)
    
    # 3. إنشاء Provider
    provider = ProviderFactory.create_provider(
        provider_type='twilio_sms' if channel == 'sms' else 'whatsapp_business',
        api_url=get_api_url(channel),
        api_key=get_api_key(channel)
    )
    
    # 4. إرسال مع إعادة المحاولة
    @retry_with_backoff(max_retries=3)
    def _send():
        response = provider.send(phone, message)
        notification_rate_limiter.consume(channel)
        return response
    
    try:
        response = _send()
        notification_logger.info(
            'notification_sent',
            extra={
                'phone': phone,
                'channel': channel,
                'message_id': response.get('message_id')
            }
        )
        return response
    except Exception as e:
        notification_logger.error(
            'notification_failed',
            extra={
                'phone': phone,
                'channel': channel,
                'error': str(e)
            }
        )
        raise
```

---

## 📖 مراجع إضافية

- [README.md](README.md) - الوثائق الرئيسية
- [FRONTEND_UPDATE.md](FRONTEND_UPDATE.md) - تحديثات الواجهة الأمامية
- [requirements.txt](requirements.txt) - قائمة التبعيات

---

**تم التطوير بـ ❤️ لتحسين إدارة خدمات النقل**

