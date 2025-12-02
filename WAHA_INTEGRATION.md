# WAHA (WhatsApp HTTP API) Integration Guide

## نظرة عامة | Overview

تم دمج WAHA (WhatsApp HTTP API) في موديول ShuttleBee للسماح بإرسال رسائل WhatsApp مباشرة من Odoo.

WAHA هو حل مفتوح المصدر يوفر واجهة برمجة تطبيقات HTTP للتفاعل مع WhatsApp.

## بيانات الاعتماد | Your Credentials

```
WAHA_API_URL: http://your-server:3000
WAHA_API_KEY: fd6b206c281d437cb0314adabef6aae2

WAHA_DASHBOARD_USERNAME: admin
WAHA_DASHBOARD_PASSWORD: f5820a80e4a4493ca06eed44908cb3e6

WHATSAPP_SWAGGER_USERNAME: admin
WHATSAPP_SWAGGER_PASSWORD: f5820a80e4a4493ca06eed44908cb3e6
```

## خطوات الإعداد | Setup Steps

### 1. تشغيل WAHA | Start WAHA

```bash
docker run -d \
  --name waha \
  -p 3000:3000 \
  -e WHATSAPP_API_KEY=fd6b206c281d437cb0314adabef6aae2 \
  -e WHATSAPP_SWAGGER_USERNAME=admin \
  -e WHATSAPP_SWAGGER_PASSWORD=f5820a80e4a4493ca06eed44908cb3e6 \
  -e WAHA_DASHBOARD_ENABLED=true \
  -e WAHA_DASHBOARD_USERNAME=admin \
  -e WAHA_DASHBOARD_PASSWORD=f5820a80e4a4493ca06eed44908cb3e6 \
  devlikeapro/waha
```

### 2. إعداد Odoo | Configure Odoo

1. اذهب إلى **الإعدادات** → **ShuttleBee**
2. في قسم **WhatsApp / WAHA Settings**:
   - **WhatsApp Provider**: WAHA (WhatsApp HTTP API)
   - **API URL**: `http://your-server:3000`
   - **API Key**: `fd6b206c281d437cb0314adabef6aae2`
   - **Session Name**: `default`
   - **Webhook URL**: `https://your-odoo.com/shuttlebee/webhook/waha`

### 3. إنشاء جلسة | Create Session

1. اضغط على زر **➕ Create Session**
2. اضغط على **📱 Get QR Code**
3. امسح QR Code باستخدام تطبيق WhatsApp على هاتفك
4. انتظر حتى تتغير الحالة إلى "✅ يعمل"

## API Endpoints المتاحة | Available Endpoints

### Session Management

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/sessions` | GET | List all sessions |
| `/api/sessions` | POST | Create a session |
| `/api/sessions/{session}` | GET | Get session info |
| `/api/sessions/{session}/start` | POST | Start session |
| `/api/sessions/{session}/stop` | POST | Stop session |
| `/api/sessions/{session}/restart` | POST | Restart session |
| `/api/sessions/{session}/logout` | POST | Logout session |

### Authentication

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/{session}/auth/qr` | GET | Get QR code for pairing |
| `/api/{session}/auth/request-code` | POST | Request auth code |

### Messaging

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/sendText` | POST | Send text message |
| `/api/sendImage` | POST | Send image |
| `/api/sendFile` | POST | Send file |
| `/api/sendVoice` | POST | Send voice message |
| `/api/sendVideo` | POST | Send video |
| `/api/sendLocation` | POST | Send location |
| `/api/sendContactVcard` | POST | Send contact vCard |
| `/api/sendPoll` | POST | Send poll |
| `/api/sendList` | POST | Send interactive list |
| `/api/forwardMessage` | POST | Forward message |

### Chat Actions

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/sendSeen` | POST | Mark as seen |
| `/api/startTyping` | POST | Start typing indicator |
| `/api/stopTyping` | POST | Stop typing |
| `/api/reaction` | PUT | React with emoji |
| `/api/star` | PUT | Star/unstar message |

## Webhook Events

WAHA يرسل الأحداث التالية إلى webhook الخاص بك:

| Event | Description |
|-------|-------------|
| `message` | Incoming message |
| `message.any` | All messages |
| `message.ack` | Message delivery status |
| `message.reaction` | Reaction to message |
| `state.change` | Session state change |
| `presence.update` | Contact presence |
| `poll.vote` | Poll vote |
| `call.received` | Incoming call |

## استخدام Python | Python Usage

```python
from odoo.addons.shuttlebee.helpers.waha_service import create_waha_service

# Create service
service = create_waha_service(
    api_url='http://your-server:3000',
    api_key='fd6b206c281d437cb0314adabef6aae2',
    session='default'
)

# Send text message
result = service.send_text(
    chat_id='1234567890@c.us',
    text='Hello from Odoo!'
)

# Send image
result = service.send_image(
    chat_id='1234567890@c.us',
    image_url='https://example.com/image.jpg',
    caption='Check this out!'
)

# Send location
result = service.send_location(
    chat_id='1234567890@c.us',
    latitude=31.2001,
    longitude=-7.9500,
    name='Marrakech',
    address='Marrakech, Morocco'
)

# Check session status
status = service.get_session()
print(status)
```

## استخدام من Odoo | Usage from Odoo

```python
# In a model method:
notification = self.env['shuttle.notification'].create({
    'passenger_id': partner.id,
    'notification_type': 'approaching',
    'channel': 'whatsapp',
    'message_content': 'Your shuttle is approaching!',
    'recipient_phone': partner.phone,
})
notification._send_notification()

# Send with location (WAHA specific)
notification.action_send_whatsapp_location(
    latitude=31.2001,
    longitude=-7.9500,
    name='Pickup Point',
    address='Your pickup location'
)
```

## حالات الخطأ | Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| `Session not found` | Session doesn't exist | Create session first |
| `QR code expired` | QR code timeout | Refresh QR code |
| `Not authenticated` | Session not connected | Scan QR code |
| `Rate limit exceeded` | Too many requests | Wait and retry |

## الدعم | Support

- WAHA Documentation: https://waha.devlike.pro/docs/overview/introduction/
- WAHA GitHub: https://github.com/devlikeapro/waha
- Swagger API: http://your-server:3000/

## الملفات المعدلة | Modified Files

1. `helpers/notification_providers.py` - Added WAHAWhatsAppProvider
2. `helpers/waha_service.py` - New comprehensive WAHA service
3. `models/res_config_settings.py` - WAHA configuration fields
4. `models/shuttle_notification.py` - Updated WhatsApp sending
5. `controllers/webhook_controller.py` - WAHA webhook handlers
6. `wizard/shuttle_waha_qr_wizard.py` - QR code display wizard
7. `views/res_config_settings_views.xml` - WAHA settings UI
8. `views/shuttle_waha_qr_wizard_views.xml` - QR wizard view

