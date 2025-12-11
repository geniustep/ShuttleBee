# -*- coding: utf-8 -*-
{
    'name': 'ShuttleBee - Shuttle Management',
    'version': '18.0.2.2.0',
    'category': 'Operations/Transportation',
    'summary': 'Manage shuttle transportation services with drivers, passengers, and real-time tracking',
    'description': """
ShuttleBee - Comprehensive Shuttle Management System
=====================================================

Features:
---------
* Trip Management (Pickup/Dropoff routes)
* Driver & Vehicle Assignment with Conflict Detection
* Passenger Management with Attendance Tracking
* Pickup/Dropoff Stop Management with GPS Coordinates
* Automated Notifications (SMS/WhatsApp/Push/Email)
* Real-time Status Updates with Webhooks
* Comprehensive Reporting & Analytics
* Multi-company Support
* Mobile-ready for future driver app integration
* Advanced Rate Limiting and Retry Logic
* Structured Logging for Better Monitoring
* Provider Adapters for SMS/WhatsApp/Push

Perfect for:
------------
* Corporate shuttle services
* School transportation
* Hotel shuttle services
* Airport transfers
* Any organized group transportation

Version 2.0.0 Improvements:
---------------------------
* Optimized conflict detection with database-level queries
* Enhanced notification system with provider adapters
* Exponential backoff retry mechanism for API calls
* Rate limiting to prevent API quota exhaustion
* Webhook support for delivery status updates
* Structured JSON logging for better observability
* Centralized validation utilities
* Improved phone number validation
* Secure template rendering to prevent injection attacks
* WAHA (WhatsApp HTTP API) Integration for self-hosted WhatsApp
* Send text, images, files, locations via WhatsApp
* Session management with QR code authentication
* Real-time webhook support for message delivery status
* Route Optimizer API Integration for automatic passenger sequence optimization
* Google OR-Tools powered VRP (Vehicle Routing Problem) solver

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
    'external_dependencies': {
        'python': [
            'requests',
            'jinja2',
            'phonenumbers',  # Optional but recommended
        ],
    },
    'data': [
        # Security
        'security/shuttle_security.xml',
        'security/ir.model.access.csv',

        # Data
        'data/ir_sequence_data.xml',
        'data/mail_template_data.xml',
        'data/ir_cron_data.xml',
        'data/waha_config_data.xml',
        'data/shuttle_message_template_data.xml',

        # Views
        'views/shuttle_trip_views.xml',
        'views/shuttle_trip_line_views.xml',
        'views/shuttle_stop_views.xml',
        'views/shuttle_group_views.xml',
        'views/shuttle_passenger_group_line_views.xml',
        'views/shuttle_group_schedule_views.xml',
        'views/shuttle_vehicle_views.xml',
        'views/res_partner_views.xml',
        'views/res_company_views.xml',
        'views/res_users_views.xml',
        'views/shuttle_notification_views.xml',
        'views/shuttle_message_template_views.xml',
        'views/res_config_settings_views.xml',
        'views/shuttle_trip_wizard_views.xml',
        'views/shuttle_waha_qr_wizard_views.xml',
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
    'currency': 'MAD',
    'post_init_hook': 'post_init_hook',
}
