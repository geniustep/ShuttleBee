# 📢 تحديثات Backend - ShuttleBee Module

**التاريخ:** 2025-12-01  
**الإصدار:** 18.0.1.0.0  
**النوع:** Feature Addition

---

## 🚗 إضافة نقطة انطلاق المركبة (Vehicle Home/Parking Location)

### 📋 نظرة عامة

تم إضافة ميزة جديدة لتحديد **موقف المركبة الثابت** (نقطة الانطلاق) في موديل `shuttle.vehicle`. هذه النقطة تمثل الموقع الذي تبيت/تُركن فيه المركبة وتنطلق منه للرحلات.

### 🎯 الهدف من التحديث

- تحديد نقطة البداية الثابتة لكل مركبة
- تمكين حساب المسافات الكلية للرحلات (من الموقف → الركاب → الوجهة → الموقف)
- تحسين تخطيط المسارات وتقدير الأوقات
- توفير بيانات دقيقة لخوارزميات التحسين المستقبلية

---

## 🔧 التغييرات التقنية

### 1. Model: `shuttle.vehicle`

تم إضافة **3 حقول جديدة**:

#### الحقول الجديدة:

```python
home_latitude = fields.Float(
    string='Parking Latitude',
    digits=(10, 7),
    tracking=True,
    help='GPS latitude of vehicle parking/home location'
)

home_longitude = fields.Float(
    string='Parking Longitude',
    digits=(10, 7),
    tracking=True,
    help='GPS longitude of vehicle parking/home location'
)

home_address = fields.Char(
    string='Parking Address',
    tracking=True,
    help='Physical address of vehicle parking location'
)
```

#### Validation/Constraints:

```python
@api.constrains('home_latitude', 'home_longitude')
def _check_home_coordinates(self):
    """Validate vehicle home/parking GPS coordinates"""
    for vehicle in self:
        if vehicle.home_latitude and not (-90 <= vehicle.home_latitude <= 90):
            raise ValidationError(_('Parking latitude must be between -90 and 90.'))
        if vehicle.home_longitude and not (-180 <= vehicle.home_longitude <= 180):
            raise ValidationError(_('Parking longitude must be between -180 and 180.'))
```

---

## 📊 بنية البيانات (Data Structure)

### Model: `shuttle.vehicle`

```json
{
  "id": 1,
  "name": "Bus 01",
  "fleet_vehicle_id": 5,
  "license_plate": "ABC-1234",
  "seat_capacity": 20,
  "driver_id": 10,
  "home_latitude": 33.5731,      // ← NEW
  "home_longitude": -7.5898,     // ← NEW
  "home_address": "Parking A, Casablanca", // ← NEW
  "active": true,
  "company_id": 1
}
```

---

## 🔌 API Endpoints (للواجهات الخارجية)

### 1. قراءة بيانات المركبة (Read)

**Endpoint:** `GET /api/shuttle.vehicle/{id}`

**Response Example:**
```json
{
  "id": 1,
  "name": "Bus 01",
  "home_latitude": 33.5731,
  "home_longitude": -7.5898,
  "home_address": "Parking A, Casablanca",
  "seat_capacity": 20
}
```

### 2. تحديث موقع المركبة (Update)

**Endpoint:** `PUT /api/shuttle.vehicle/{id}`

**Request Body:**
```json
{
  "home_latitude": 33.5731,
  "home_longitude": -7.5898,
  "home_address": "Parking A, Casablanca"
}
```

**Validation Rules:**
- `home_latitude`: -90 إلى 90 (اختياري)
- `home_longitude`: -180 إلى 180 (اختياري)
- `home_address`: نص حر (اختياري)

---

## 🎨 تحديثات الواجهة (UI Updates)

### View Changes (Odoo Backend)

تم تحديث `shuttle_vehicle_views.xml`:

1. **إضافة تبويب جديد**: "Parking Location"
2. **الحقول المعروضة**:
   - Parking Latitude (GPS)
   - Parking Longitude (GPS)
   - Parking Address (نص)
3. **رسالة توضيحية** للمستخدم عن استخدام الموقع

---

## 💡 حالات الاستخدام (Use Cases)

### 1. حساب المسافة الكلية للرحلة

```
المسار الكامل:
Parking → Passenger 1 → Passenger 2 → School → Parking
```

### 2. تقدير وقت البداية المطلوب

```python
# Example calculation
parking_to_first_passenger = calculate_distance(
    vehicle.home_latitude, 
    vehicle.home_longitude,
    first_passenger.pickup_latitude,
    first_passenger.pickup_longitude
)

required_departure_time = trip_start_time - estimated_travel_time
```

### 3. تحسين المسارات (Route Optimization)

يمكن الآن حساب المسار الأمثل الذي يبدأ وينتهي بموقف المركبة.

---

## 📱 توصيات للـ Frontend Team

### 1. **خرائط (Maps Integration)**

إذا كنتم تستخدمون Google Maps/Mapbox:

```javascript
// عرض موقف المركبة على الخريطة
const vehicleParkingMarker = {
  position: {
    lat: vehicle.home_latitude,
    lng: vehicle.home_longitude
  },
  title: "Vehicle Parking: " + vehicle.name,
  icon: "parking_icon.png", // أيقونة موقف
  color: "blue"
}
```

### 2. **نماذج الإدخال (Forms)**

عند إضافة/تعديل مركبة:

```jsx
// React Example
<div className="parking-location">
  <h3>Parking Location</h3>
  <Input
    type="number"
    name="home_latitude"
    label="Latitude"
    placeholder="e.g., 33.5731"
    min={-90}
    max={90}
    step={0.000001}
  />
  <Input
    type="number"
    name="home_longitude"
    label="Longitude"
    placeholder="e.g., -7.5898"
    min={-180}
    max={180}
    step={0.000001}
  />
  <Input
    type="text"
    name="home_address"
    label="Address"
    placeholder="Physical parking address"
  />
</div>
```

### 3. **عرض المعلومات (Display)**

في صفحة تفاصيل المركبة:

```jsx
{vehicle.home_latitude && vehicle.home_longitude ? (
  <div className="parking-info">
    <Icon name="parking" />
    <span>Parking: {vehicle.home_address || "GPS Location"}</span>
    <small>
      ({vehicle.home_latitude.toFixed(4)}, {vehicle.home_longitude.toFixed(4)})
    </small>
  </div>
) : (
  <div className="warning">
    ⚠️ No parking location set for this vehicle
  </div>
)}
```

---

## ⚠️ ملاحظات مهمة (Important Notes)

### 1. الحقول اختيارية (Optional)
- جميع الحقول الثلاثة **اختيارية** (ليست مطلوبة)
- يمكن للمركبة أن تعمل بدون تحديد موقف
- ولكن **يُنصح بشدة** بإضافة الموقع لتحسين الدقة

### 2. التوافق مع الإصدارات السابقة (Backward Compatibility)
- ✅ المركبات الموجودة لن تتأثر
- ✅ الحقول الجديدة ستكون `null` للمركبات القديمة
- ✅ لا حاجة لـ migration script

### 3. Validation
- Latitude: يجب أن يكون بين -90 و +90
- Longitude: يجب أن يكون بين -180 و +180
- سيتم رفض القيم خارج هذا النطاق

---

## 🧪 أمثلة للاختبار (Test Cases)

### Test Case 1: إضافة موقع صحيح
```json
{
  "home_latitude": 33.5731,
  "home_longitude": -7.5898,
  "home_address": "Parking A"
}
// ✅ Expected: Success
```

### Test Case 2: قيم GPS غير صحيحة
```json
{
  "home_latitude": 100.5,  // ❌ خارج النطاق
  "home_longitude": -7.5898
}
// ❌ Expected: ValidationError
```

### Test Case 3: إحداثيات فقط بدون عنوان
```json
{
  "home_latitude": 33.5731,
  "home_longitude": -7.5898,
  "home_address": null
}
// ✅ Expected: Success (العنوان اختياري)
```

### Test Case 4: عنوان فقط بدون GPS
```json
{
  "home_latitude": null,
  "home_longitude": null,
  "home_address": "Parking A, Casablanca"
}
// ✅ Expected: Success (لكن لن يمكن حساب المسافات)
```

---

## 📦 Migration Guide

### للمركبات الموجودة:

لا حاجة لأي عمل فوري. يمكن إضافة المواقع تدريجياً:

1. **Option 1: Manual Entry**
   - يدخل المستخدمون المواقع يدوياً

2. **Option 2: Bulk Import**
   - تحضير ملف CSV:
   ```csv
   vehicle_id,home_latitude,home_longitude,home_address
   1,33.5731,-7.5898,"Parking A, Casablanca"
   2,33.5825,-7.6100,"Parking B, Casablanca"
   ```

---

## 🔮 الاستخدامات المستقبلية (Future Use)

هذه البيانات ستُستخدم في:

1. ✅ حساب المسافات الكلية
2. ✅ تحسين المسارات (Route Optimization)
3. ✅ تقدير استهلاك الوقود
4. ✅ تحليل الأداء والكفاءة
5. ✅ إشعارات تأخير السائق عن الموقف
6. ✅ تتبع GPS والتحقق من موقع المركبة

---

## 📞 الدعم والتواصل

إذا كان لديكم أي استفسارات أو احتياج لتوضيحات:

- **Backend Team Lead:** [Your Name]
- **Email:** backend@shuttlebee.com
- **Slack:** #shuttlebee-dev

---

## ✅ Checklist للـ Frontend

- [ ] قراءة والفهم الكامل للتحديث
- [ ] تحديث API client للحقول الجديدة
- [ ] إضافة حقول الإدخال في نموذج المركبة
- [ ] إضافة validation للإحداثيات في Frontend
- [ ] عرض موقع الموقف على الخريطة (إن وجدت)
- [ ] تحديث الـ TypeScript interfaces/types
- [ ] اختبار الـ CRUD operations
- [ ] تحديث الوثائق الداخلية

---

**Happy Coding! 🚀**

*ShuttleBee Backend Team*
