# -*- coding: utf-8 -*-
{
    'name': 'ShuttleBee - Shuttle Management',
    'version': '18.0.1.0.0',
    'category': 'Operations/Transportation',
    'summary': 'Manage shuttle transportation services with drivers, passengers, and real-time tracking',
    'description': """
ShuttleBee - Comprehensive Shuttle Management System
=====================================================

Features:
---------
* Trip Management (Pickup/Dropoff routes)
* Driver & Vehicle Assignment
* Passenger Management with Attendance Tracking
* Pickup/Dropoff Stop Management with GPS Coordinates
* Automated Notifications (SMS/WhatsApp/Push/Email)
* Real-time Status Updates
* Comprehensive Reporting & Analytics
* Multi-company Support
* Mobile-ready for future driver app integration

Perfect for:
------------
* Corporate shuttle services
* School transportation
* Hotel shuttle services
* Airport transfers
* Any organized group transportation

    """,
    'author': 'Your Company',
    'website': 'https://www.yourcompany.com',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'mail',
        'contacts',
        'partner_autocomplete',
        'fleet',
        'account',
    ],
    'data': [
        # Security
        'security/shuttle_security.xml',
        'security/ir.model.access.csv',

        # Data
        'data/ir_sequence_data.xml',
        'data/mail_template_data.xml',
        'data/ir_cron_data.xml',

        # Views
        'views/shuttle_trip_views.xml',
        'views/shuttle_trip_line_views.xml',
        'views/shuttle_stop_views.xml',
        'views/shuttle_group_views.xml',
        'views/shuttle_vehicle_views.xml',
        'views/res_partner_views.xml',
        'views/shuttle_notification_views.xml',
        'views/res_config_settings_views.xml',
        'views/shuttle_trip_wizard_views.xml',
        'views/shuttle_menus.xml',

        # Reports
        'report/shuttle_report_templates.xml',
    ],
    'demo': [],
    'images': [
        'static/description/banner.png',
        'static/description/icon.png',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'price': 0.00,
    'currency': 'USD',
    'post_init_hook': 'post_init_hook',
}
