# -*- coding: utf-8 -*-

from odoo import api, fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    shuttle_role = fields.Selection([
        ('manager', 'ShuttleBee Manager'),
        ('dispatcher', 'ShuttleBee Dispatcher'),
        ('driver', 'ShuttleBee Driver'),
        ('user', 'ShuttleBee User'),
        ('none', 'No ShuttleBee Access'),
    ], string='ShuttleBee Role', compute='_compute_shuttle_role', store=True, readonly=True,
       help='User role in ShuttleBee system based on assigned groups')
    
    shuttle_dispatcher_group_ids = fields.Many2many(
        'shuttle.passenger.group',
        'shuttle_group_dispatcher_rel',
        'user_id',
        'group_id',
        string='Authorized Passenger Groups',
        help='Passenger groups this dispatcher has permission to view and manage.'
    )

    @api.depends('groups_id')
    def _compute_shuttle_role(self):
        """Compute user's ShuttleBee role based on assigned groups"""
        for user in self:
            if user.has_group('shuttlebee.group_shuttle_manager'):
                user.shuttle_role = 'manager'
            elif user.has_group('shuttlebee.group_shuttle_dispatcher'):
                user.shuttle_role = 'dispatcher'
            elif user.has_group('shuttlebee.group_shuttle_driver'):
                user.shuttle_role = 'driver'
            elif user.has_group('shuttlebee.group_shuttle_user'):
                user.shuttle_role = 'user'
            else:
                user.shuttle_role = 'none'

    @api.model_create_multi
    def create(self, vals_list):
        """Auto-assign ShuttleBee groups based on user permissions"""
        users = super().create(vals_list)
        users._auto_assign_shuttle_groups()
        return users

    def write(self, vals):
        """Auto-assign ShuttleBee groups when user groups change"""
        result = super().write(vals)
        if 'groups_id' in vals:
            self._auto_assign_shuttle_groups()
        return result


    def _auto_assign_shuttle_groups(self):
        """Automatically assign ShuttleBee groups based on user's existing groups"""
        for user in self:
            # Skip if user is not active
            if not user.active:
                continue
                
            # Get ShuttleBee groups
            shuttle_manager = self.env.ref('shuttlebee.group_shuttle_manager', raise_if_not_found=False)
            shuttle_dispatcher = self.env.ref('shuttlebee.group_shuttle_dispatcher', raise_if_not_found=False)
            shuttle_user = self.env.ref('shuttlebee.group_shuttle_user', raise_if_not_found=False)
            
            if not shuttle_user:
                continue
            
            # Get user's current groups
            user_groups = user.groups_id
            user_group_names = [g.name for g in user_groups]
            
            # Check if user has Manager or Administrator groups
            has_manager = (
                user.has_group('base.group_system') or
                user.has_group('base.group_erp_manager') or
                any('Manager' in name for name in user_group_names) or
                any('Administrator' in name for name in user_group_names)
            )
            
            # Auto-assign groups
            groups_to_add = []
            
            if has_manager and shuttle_manager:
                # Manager gets full access
                if shuttle_manager not in user_groups:
                    groups_to_add.append(shuttle_manager.id)
            elif shuttle_user:
                # Everyone else gets basic user access
                if shuttle_user not in user_groups:
                    groups_to_add.append(shuttle_user.id)
            
            # Add groups if needed
            if groups_to_add:
                user.sudo().write({'groups_id': [(4, gid) for gid in groups_to_add]})

