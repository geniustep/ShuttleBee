# 🚀 ShuttleBee - Flutter Integration Guide
## دليل تكامل تطبيق Flutter مع نظام الإشعارات

---

## 📋 نظرة عامة

تم تطوير نظام إشعارات متكامل يدعم:
- ✅ WhatsApp عبر WAHA API (Self-hosted)
- ✅ SMS
- ✅ Push Notifications
- ✅ Email
- ✅ قوالب رسائل قابلة للتخصيص (عربي، إنجليزي، فرنسي)

---

## 🔗 API Endpoints المتاحة

### Base URL
```
https://propanel.ma/api/v1/
```

### Authentication
```http
Authorization: Bearer {access_token}
```

---

## 📱 1. إرسال إشعار Approaching (السائق يقترب)

### Endpoint
```http
POST /api/v1/shuttle/trip-line/{trip_line_id}/notify/approaching
```

### Response
```json
{
  "success": true,
  "notification_id": 123,
  "channel": "whatsapp",
  "status": "sent",
  "message": "Notification sent successfully"
}
```

### Flutter Code
```dart
Future<void> sendApproachingNotification(int tripLineId) async {
  final response = await dio.post(
    '/api/v1/shuttle/trip-line/$tripLineId/notify/approaching',
    options: Options(headers: {'Authorization': 'Bearer $accessToken'}),
  );
  
  if (response.data['success']) {
    // Show success message
    showSnackBar('تم إرسال إشعار الاقتراب');
  }
}
```

---

## 📱 2. إرسال إشعار Arrived (السائق وصل)

### Endpoint
```http
POST /api/v1/shuttle/trip-line/{trip_line_id}/notify/arrived
```

### Flutter Code
```dart
Future<void> sendArrivedNotification(int tripLineId) async {
  final response = await dio.post(
    '/api/v1/shuttle/trip-line/$tripLineId/notify/arrived',
  );
  
  if (response.data['success']) {
    showSnackBar('تم إرسال إشعار الوصول');
  }
}
```

---

## 📱 3. إرسال إشعار مخصص

### Endpoint
```http
POST /api/v1/shuttle/notification/send
```

### Request Body
```json
{
  "passenger_id": 123,
  "trip_id": 456,
  "notification_type": "custom",
  "channel": "whatsapp",
  "message": "رسالة مخصصة هنا"
}
```

### Flutter Code
```dart
Future<void> sendCustomNotification({
  required int passengerId,
  required int tripId,
  required String message,
  String channel = 'whatsapp',
}) async {
  final response = await dio.post(
    '/api/v1/shuttle/notification/send',
    data: {
      'passenger_id': passengerId,
      'trip_id': tripId,
      'notification_type': 'custom',
      'channel': channel,
      'message': message,
    },
  );
  
  return response.data;
}
```

---

## 📱 4. الحصول على قوالب الرسائل

### Endpoint
```http
GET /api/v1/shuttle/message-templates
```

### Query Parameters
| Parameter | Type | Description |
|-----------|------|-------------|
| `notification_type` | string | approaching, arrived, trip_started, cancelled, reminder |
| `language` | string | ar, en, fr |
| `channel` | string | whatsapp, sms, email, all |

### Response
```json
{
  "templates": [
    {
      "id": 1,
      "name": "إشعار اقتراب السائق (عربي)",
      "notification_type": "approaching",
      "language": "ar",
      "channel": "all",
      "body": "مرحباً {passenger_name} 👋\n\nالسائق {driver_name} يقترب...",
      "is_default": true
    }
  ]
}
```

### Flutter Code
```dart
class MessageTemplate {
  final int id;
  final String name;
  final String notificationType;
  final String language;
  final String body;
  final bool isDefault;
  
  MessageTemplate.fromJson(Map<String, dynamic> json)
      : id = json['id'],
        name = json['name'],
        notificationType = json['notification_type'],
        language = json['language'],
        body = json['body'],
        isDefault = json['is_default'];
}

Future<List<MessageTemplate>> getMessageTemplates({
  String? notificationType,
  String? language,
}) async {
  final response = await dio.get(
    '/api/v1/shuttle/message-templates',
    queryParameters: {
      if (notificationType != null) 'notification_type': notificationType,
      if (language != null) 'language': language,
    },
  );
  
  return (response.data['templates'] as List)
      .map((t) => MessageTemplate.fromJson(t))
      .toList();
}
```

---

## 📱 5. معاينة الرسالة قبل الإرسال

### Endpoint
```http
POST /api/v1/shuttle/message-templates/{template_id}/preview
```

### Request Body
```json
{
  "passenger_name": "أحمد محمد",
  "driver_name": "خالد علي",
  "vehicle_name": "حافلة 1",
  "stop_name": "محطة المدرسة",
  "eta": "10"
}
```

### Response
```json
{
  "preview": "مرحباً أحمد محمد 👋\n\nالسائق خالد علي يقترب من نقطة الالتقاط محطة المدرسة.\n\n🚐 المركبة: حافلة 1\n⏱️ الوقت المتوقع للوصول: 10 دقائق"
}
```

---

## 📱 6. حالة الإشعار (Notification Status)

### Endpoint
```http
GET /api/v1/shuttle/notification/{notification_id}/status
```

### Response
```json
{
  "id": 123,
  "status": "delivered",
  "channel": "whatsapp",
  "sent_date": "2024-01-15T10:30:00Z",
  "delivered_date": "2024-01-15T10:30:05Z",
  "read_date": null,
  "provider_message_id": "wamid.xxx"
}
```

### Status Values
| Status | Description |
|--------|-------------|
| `pending` | في انتظار الإرسال |
| `sent` | تم الإرسال |
| `delivered` | تم التسليم |
| `read` | تمت القراءة |
| `failed` | فشل الإرسال |

---

## 📱 7. سجل الإشعارات للراكب

### Endpoint
```http
GET /api/v1/shuttle/passenger/{passenger_id}/notifications
```

### Query Parameters
| Parameter | Type | Description |
|-----------|------|-------------|
| `limit` | int | عدد النتائج (default: 50) |
| `trip_id` | int | فلترة حسب الرحلة |

### Flutter Code
```dart
Future<List<Notification>> getPassengerNotifications(
  int passengerId, {
  int limit = 50,
  int? tripId,
}) async {
  final response = await dio.get(
    '/api/v1/shuttle/passenger/$passengerId/notifications',
    queryParameters: {
      'limit': limit,
      if (tripId != null) 'trip_id': tripId,
    },
  );
  
  return (response.data['notifications'] as List)
      .map((n) => Notification.fromJson(n))
      .toList();
}
```

---

## 🎯 أمثلة عملية للتطبيق

### 1. شاشة تفاصيل الرحلة (Trip Details Screen)

```dart
class TripDetailsScreen extends StatelessWidget {
  final Trip trip;
  
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: ListView.builder(
        itemCount: trip.passengers.length,
        itemBuilder: (context, index) {
          final passenger = trip.passengers[index];
          return PassengerCard(
            passenger: passenger,
            onNotifyApproaching: () => _sendApproachingNotification(passenger),
            onNotifyArrived: () => _sendArrivedNotification(passenger),
          );
        },
      ),
    );
  }
  
  Future<void> _sendApproachingNotification(Passenger passenger) async {
    try {
      await NotificationService.sendApproaching(passenger.tripLineId);
      showSuccessSnackBar('تم إرسال إشعار الاقتراب لـ ${passenger.name}');
    } catch (e) {
      showErrorSnackBar('فشل إرسال الإشعار: $e');
    }
  }
}
```

### 2. زر إرسال الإشعارات

```dart
class NotificationButtons extends StatelessWidget {
  final int tripLineId;
  final String passengerStatus;
  
  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        if (passengerStatus == 'planned')
          ElevatedButton.icon(
            icon: Icon(Icons.directions_car),
            label: Text('إشعار اقتراب'),
            style: ElevatedButton.styleFrom(
              backgroundColor: Colors.orange,
            ),
            onPressed: () => _sendApproachingNotification(context),
          ),
        SizedBox(width: 8),
        if (passengerStatus == 'notified_approaching')
          ElevatedButton.icon(
            icon: Icon(Icons.location_on),
            label: Text('إشعار وصول'),
            style: ElevatedButton.styleFrom(
              backgroundColor: Colors.green,
            ),
            onPressed: () => _sendArrivedNotification(context),
          ),
      ],
    );
  }
}
```

### 3. مؤشر حالة الإشعار

```dart
class NotificationStatusIndicator extends StatelessWidget {
  final String status;
  
  @override
  Widget build(BuildContext context) {
    final statusConfig = {
      'pending': {'icon': Icons.schedule, 'color': Colors.grey, 'text': 'في الانتظار'},
      'sent': {'icon': Icons.check, 'color': Colors.blue, 'text': 'تم الإرسال'},
      'delivered': {'icon': Icons.done_all, 'color': Colors.green, 'text': 'تم التسليم'},
      'read': {'icon': Icons.visibility, 'color': Colors.purple, 'text': 'تمت القراءة'},
      'failed': {'icon': Icons.error, 'color': Colors.red, 'text': 'فشل'},
    };
    
    final config = statusConfig[status] ?? statusConfig['pending']!;
    
    return Chip(
      avatar: Icon(config['icon'] as IconData, size: 16, color: config['color'] as Color),
      label: Text(config['text'] as String),
      backgroundColor: (config['color'] as Color).withOpacity(0.1),
    );
  }
}
```

---

## ⚙️ إعدادات القناة الافتراضية

يمكن للمستخدم تغيير قناة الإشعار الافتراضية من الإعدادات:
- **WhatsApp** (عبر WAHA) - الافتراضي
- **SMS**
- **Push Notification**
- **Email**

### للحصول على القناة الافتراضية:
```http
GET /api/v1/shuttle/settings/notification-channel
```

```json
{
  "default_channel": "whatsapp",
  "available_channels": ["whatsapp", "sms", "push", "email"]
}
```

---

## 🌐 Webhook للتحديثات الفورية (Real-time Updates)

### WebSocket Connection
```dart
final channel = WebSocketChannel.connect(
  Uri.parse('wss://propanel.ma/ws/shuttle/notifications'),
);

channel.stream.listen((message) {
  final data = jsonDecode(message);
  
  switch (data['event']) {
    case 'notification.sent':
      // إشعار تم إرساله
      break;
    case 'notification.delivered':
      // إشعار تم تسليمه
      break;
    case 'notification.read':
      // إشعار تمت قراءته
      break;
    case 'notification.failed':
      // فشل إرسال الإشعار
      break;
  }
});
```

---

## 📝 المتغيرات المتاحة في القوالب

| Variable | Description | Example |
|----------|-------------|---------|
| `{passenger_name}` | اسم الراكب | أحمد محمد |
| `{driver_name}` | اسم السائق | خالد علي |
| `{vehicle_name}` | اسم المركبة | حافلة 1 |
| `{vehicle_plate}` | لوحة المركبة | أ ب ج 1234 |
| `{stop_name}` | نقطة التوقف | محطة المدرسة |
| `{trip_name}` | اسم الرحلة | TRIP/2024/001 |
| `{trip_date}` | تاريخ الرحلة | 2024-01-15 |
| `{trip_time}` | وقت الرحلة | 07:30 |
| `{eta}` | الوقت المتوقع (دقائق) | 10 |
| `{company_name}` | اسم الشركة | شركة النقل |
| `{company_phone}` | هاتف الشركة | +212 600 000 000 |

---

## ❓ الأسئلة الشائعة

### 1. كيف أعرف إذا كان الإشعار تم تسليمه؟
استخدم endpoint `/notification/{id}/status` أو اشترك في WebSocket للحصول على تحديثات فورية.

### 2. هل يمكن إرسال إشعار بلغة مختلفة؟
نعم، النظام يكتشف تلقائياً لغة الراكب ويستخدم القالب المناسب. يمكنك أيضاً تحديد اللغة يدوياً.

### 3. ماذا يحدث إذا فشل الإشعار؟
يتم إعادة المحاولة تلقائياً 3 مرات. يمكنك إعادة المحاولة يدوياً من خلال `/notification/{id}/retry`.

### 4. هل يمكن إرسال إشعارات جماعية؟
نعم، استخدم endpoint `/trip/{trip_id}/notify/all` لإرسال إشعار لجميع ركاب الرحلة.

---

## 📞 للدعم الفني

- **Backend Team**: [backend@example.com]
- **Documentation**: `/shuttlebee/docs/`
- **API Swagger**: `https://propanel.ma/api/docs`

---

**آخر تحديث**: ديسمبر 2024
**الإصدار**: 2.0.0

