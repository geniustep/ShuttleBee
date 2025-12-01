# 📢 تحديثات Frontend - ShuttleBee Module

**التاريخ**: 2025  
**الإصدار**: 18.0.1.0.0  
**الموضوع**: تحديثات واجهة المستخدم والأزرار المشروطة

---

## 🎯 ملخص التحديثات

تم إجراء تحديثات مهمة على واجهة المستخدم في ShuttleBee Module تتعلق بـ:

1. **أزرار مشروطة حسب نوع الرحلة** (`trip_type`)
2. **إحصائيات مشروطة حسب نوع الرحلة**

---

## 📋 التغييرات التفصيلية

### 1. أزرار ShuttleTripLine المشروطة

#### التغيير:
- **في رحلات Pickup** (`trip_type == 'pickup'`):
  - يظهر زر **"Mark Boarded"** (`action_mark_boarded`)
  - يختفي زر **"Mark Dropped"** (`action_mark_dropped`)

- **في رحلات Dropoff** (`trip_type == 'dropoff'`):
  - يظهر زر **"Mark Dropped"** (`action_mark_dropped`)
  - يختفي زر **"Mark Boarded"** (`action_mark_boarded`)

#### الملفات المتأثرة:
- `views/shuttle_trip_line_views.xml` (Form View)
- `views/shuttle_trip_views.xml` (Tree View داخل Form)

#### الكود:
```xml
<!-- في Form View -->
<button name="action_mark_boarded" 
        invisible="trip_type != 'pickup' or status in ['boarded', 'absent', 'dropped']"/>

<button name="action_mark_dropped" 
        invisible="trip_type != 'dropoff' or status in ['dropped', 'absent']"/>

<!-- في Tree View -->
<field name="trip_type" invisible="1"/>
<button name="action_mark_boarded"
        invisible="trip_type != 'pickup' or status in ['boarded', 'absent', 'dropped']"/>
<button name="action_mark_dropped"
        invisible="trip_type != 'dropoff' or status != 'boarded'"/>
```

---

### 2. إحصائيات Passenger Statistics المشروطة

#### التغيير:
- **في رحلات Pickup** (`trip_type == 'pickup'`):
  - يظهر حقل **"Boarded"** (`boarded_count`)
  - يختفي حقل **"Dropped"** (`dropped_count`)

- **في رحلات Dropoff** (`trip_type == 'dropoff'`):
  - يظهر حقل **"Dropped"** (`dropped_count`)
  - يختفي حقل **"Boarded"** (`boarded_count`)

#### الملفات المتأثرة:
- `models/shuttle_trip.py` (إضافة حقل `dropped_count`)
- `views/shuttle_trip_views.xml` (Passenger Statistics Group)

#### الحقول الجديدة:
```python
# في shuttle.trip model
dropped_count = fields.Integer(
    string='Dropped',
    compute='_compute_passenger_stats',
    store=True
)
```

#### الكود في View:
```xml
<group name="statistics" string="Passenger Statistics">
    <field name="passenger_count" readonly="1"/>
    <field name="present_count" readonly="1"/>
    <field name="absent_count" readonly="1"/>
    <field name="boarded_count" readonly="1"
           invisible="trip_type == 'dropoff'"/>
    <field name="dropped_count" readonly="1"
           invisible="trip_type == 'pickup'"/>
</group>
```

---

## 🔧 التغييرات في Backend

### 1. حقل `dropped_count` في Model

**الملف**: `models/shuttle_trip.py`

**التغيير**: تم إضافة حقل جديد `dropped_count` يتم حسابه تلقائياً في دالة `_compute_passenger_stats`:

```python
dropped_count = fields.Integer(
    string='Dropped',
    compute='_compute_passenger_stats',
    store=True
)

# في _compute_passenger_stats:
dropped_count = 0
for line in lines:
    if status == 'dropped':
        dropped_count += 1
trip.dropped_count = dropped_count
```

---

## 📱 تأثيرات على Frontend/API

### 1. حقول جديدة متاحة عبر API

عند استدعاء API للحصول على معلومات الرحلة (`shuttle.trip`):

```json
{
    "id": 1,
    "name": "Morning Trip",
    "trip_type": "dropoff",
    "boarded_count": 0,      // موجود مسبقاً
    "dropped_count": 3,      // ⭐ جديد
    "passenger_count": 4,
    "present_count": 3,
    "absent_count": 1
}
```

### 2. الأزرار المشروطة

عند استدعاء API للحصول على معلومات `shuttle.trip.line`:

- يجب التحقق من `trip_type` قبل عرض الأزرار:
  - إذا `trip_type == 'pickup'`: اعرض `action_mark_boarded` فقط
  - إذا `trip_type == 'dropoff'`: اعرض `action_mark_dropped` فقط

### 3. إحصائيات مشروطة

عند عرض Passenger Statistics:
- تحقق من `trip_type` قبل عرض الحقول:
  - إذا `trip_type == 'pickup'`: اعرض `boarded_count`
  - إذا `trip_type == 'dropoff'`: اعرض `dropped_count`

---

## 🎨 توصيات للتنفيذ في Frontend

### 1. عرض الأزرار

```javascript
// مثال React/Vue
const showMarkBoarded = trip.trip_type === 'pickup' && 
                       !['boarded', 'absent', 'dropped'].includes(line.status);

const showMarkDropped = trip.trip_type === 'dropoff' && 
                       line.status !== 'dropped' && 
                       line.status !== 'absent';

// في JSX/Template
{showMarkBoarded && (
    <button onClick={() => markBoarded(line.id)}>
        Mark Boarded
    </button>
)}

{showMarkDropped && (
    <button onClick={() => markDropped(line.id)}>
        Mark Dropped
    </button>
)}
```

### 2. عرض الإحصائيات

```javascript
// مثال React/Vue
const showBoarded = trip.trip_type === 'pickup';
const showDropped = trip.trip_type === 'dropoff';

// في JSX/Template
<div className="statistics">
    <div>Total Passengers: {trip.passenger_count}</div>
    <div>Present: {trip.present_count}</div>
    <div>Absent: {trip.absent_count}</div>
    
    {showBoarded && (
        <div>Boarded: {trip.boarded_count}</div>
    )}
    
    {showDropped && (
        <div>Dropped: {trip.dropped_count}</div>
    )}
</div>
```

---

## 🔄 API Endpoints المتأثرة

### 1. `shuttle.trip` - Read

**Response تغير**:
- إضافة حقل `dropped_count` في الاستجابة

```json
{
    "id": 1,
    "trip_type": "dropoff",
    "boarded_count": 0,
    "dropped_count": 3,  // ⭐ جديد
    ...
}
```

### 2. `shuttle.trip.line` - Read

**Response لم يتغير**، لكن يجب استخدام `trip_type` من `trip_id` لتحديد الأزرار المناسبة.

---

## ✅ Checklist للتنفيذ

- [ ] تحديث عرض الأزرار في قائمة الركاب (Tree View)
- [ ] تحديث عرض الأزرار في تفاصيل الراكب (Form View)
- [ ] تحديث عرض Passenger Statistics حسب `trip_type`
- [ ] إضافة حقل `dropped_count` في API responses
- [ ] تحديث الوثائق/التعليقات في الكود
- [ ] اختبار الأزرار في رحلات Pickup
- [ ] اختبار الأزرار في رحلات Dropoff
- [ ] اختبار الإحصائيات في رحلات Pickup
- [ ] اختبار الإحصائيات في رحلات Dropoff

---

## 📞 للاستفسارات

إذا كان لديكم أي استفسارات حول هذه التحديثات، يرجى التواصل مع فريق Backend.

---

**آخر تحديث**: 2025  
**الإصدار**: 18.0.1.0.0

