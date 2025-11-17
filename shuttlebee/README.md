# 🐝 ShuttleBee - Odoo 18 Shuttle Management Module

## Overview

ShuttleBee is a comprehensive shuttle transportation management system for Odoo 18. It helps organizations efficiently manage shuttle services, track passengers, coordinate drivers, and automate notifications.

## Features

### 🚌 Trip Management
- Plan and schedule pickup/dropoff trips
- Real-time trip status tracking (Draft → Planned → Ongoing → Done)
- Driver and vehicle assignment
- Capacity management with seat allocation
- Calendar and Kanban views for easy visualization

### 👥 Passenger Management
- Complete passenger profiles with shuttle preferences
- Default pickup/dropoff stop assignments
- Trip history and attendance statistics
- Attendance rate calculation
- Boarding status tracking

### 📍 Stop Management
- Define pickup and dropoff locations
- GPS coordinates support
- Address details and city-based organization
- Usage statistics per stop
- Sequence-based stop ordering

### 🔔 Smart Notifications
- Multi-channel notifications (SMS, WhatsApp, Email, Push)
- Automated approaching notifications
- Arrival notifications
- Trip cancellation alerts
- Configurable message templates
- Notification delivery tracking

### 📊 Reports & Analytics
- Trip reports with passenger lists
- Daily trip summaries
- Attendance reports
- Occupancy rate tracking
- Notification logs

### 🔐 Security
Four-tier role-based access control:
- **User**: View own trips
- **Driver**: Manage assigned trips, update passenger status
- **Dispatcher**: Create and manage all trips
- **Manager**: Full access including settings and deletion

## Installation

1. Copy the `shuttlebee` folder to your Odoo addons directory
2. Update the apps list: `odoo-bin -u all -d your_database`
3. Install the module from Apps menu
4. Configure settings in Settings → ShuttleBee

## Configuration

### Basic Setup

1. **Create Stops** (Configuration → Stops)
   - Add pickup and dropoff locations
   - Set GPS coordinates (optional)
   - Configure stop types (Pickup/Dropoff/Both)

2. **Register Passengers** (Operations → Passengers)
   - Mark contacts as shuttle passengers
   - Assign default pickup/dropoff stops
   - Add special requirements in shuttle notes

3. **Configure Notifications** (Settings → ShuttleBee)
   - Set default notification channel
   - Configure timing for approaching notifications
   - Set absence timeout
   - Add API credentials for SMS/WhatsApp

### API Configuration

#### SMS Integration
Configure your SMS gateway in Settings:
```
API URL: https://api.your-sms-provider.com
API Key: your-api-key
```

#### WhatsApp Integration
Configure WhatsApp Business API:
```
API URL: https://api.whatsapp.com
API Key: your-api-key
```

## Usage

### Creating a Trip

1. Go to Operations → Trips → Create
2. Fill in trip details:
   - Trip name and type (Pickup/Dropoff)
   - Date and time
   - Driver and vehicle
   - Total seats
3. Add passengers in the Passengers tab
4. Select pickup/dropoff stops for each passenger
5. Confirm the trip

### Managing Trips

**Driver Workflow:**
1. View assigned trips
2. Start the trip when ready
3. Send approaching notifications to passengers
4. Mark passengers as boarded/absent
5. Complete the trip upon arrival

**Automated Features:**
- System automatically sends approaching notifications
- Auto-marks absent passengers after timeout
- Sends daily summaries to managers

## Scheduled Tasks

Three automated cron jobs run in the background:

1. **Send Approaching Notifications** (Every 5 minutes)
   - Sends notifications to passengers when driver is approaching

2. **Mark Absent Passengers** (Every 10 minutes)
   - Automatically marks passengers as absent after timeout

3. **Daily Summary** (Once per day)
   - Sends daily trip summary emails to managers

## Database Schema

### Main Models

- `shuttle.trip` - Trip records
- `shuttle.trip.line` - Passenger lines in trips
- `shuttle.stop` - Pickup/dropoff locations
- `shuttle.notification` - Notification log
- `res.partner` - Extended for passenger info
- `res.config.settings` - Module configuration

## Technical Details

- **Odoo Version**: 18.0
- **Python Version**: 3.10+
- **Dependencies**: base, mail, contacts
- **License**: LGPL-3
- **Languages**: Arabic (primary), English (secondary)

## Customization

### Adding Custom Notification Channels

Extend `shuttle.notification` model:

```python
def _send_custom_channel(self):
    # Your custom implementation
    pass
```

### Creating Custom Reports

Add new report templates in `report/` directory following QWeb format.

### Extending Trip Workflow

Override trip methods to add custom states or actions:

```python
class ShuttleTrip(models.Model):
    _inherit = 'shuttle.trip'

    def action_custom_step(self):
        # Your custom logic
        pass
```

## Troubleshooting

### Notifications not sending
1. Check API credentials in Settings
2. Verify passenger has phone/email configured
3. Check notification log for error messages

### Cron jobs not running
1. Verify cron jobs are active in Settings → Technical → Scheduled Actions
2. Check Odoo server is running with `--max-cron-threads` > 0

### Permission errors
1. Verify user has correct security group assigned
2. Check record rules in Settings → Technical → Record Rules

## Roadmap

Future enhancements planned:

- [ ] Mobile driver app (React Native)
- [ ] Real-time GPS tracking
- [ ] Route optimization algorithms
- [ ] Passenger self-service portal
- [ ] Payment integration
- [ ] Advanced analytics dashboard
- [ ] Weather integration
- [ ] Traffic alerts

## Support

For support, bug reports, or feature requests:

- **Email**: support@yourcompany.com
- **Website**: https://www.yourcompany.com
- **Documentation**: https://docs.yourcompany.com/shuttlebee

## Credits

Developed by Your Company

## License

LGPL-3

---

**Version**: 1.0.0
**Last Updated**: 2025
**Status**: Production Ready
