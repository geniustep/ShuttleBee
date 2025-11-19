# -*- coding: utf-8 -*-

from odoo import api, SUPERUSER_ID


def post_init_hook(env):
    """Create GPS position multi-company rule and access rights after models are loaded"""
    
    # Find the model
    model = env['ir.model'].search([
        ('model', '=', 'shuttle.gps.position')
    ], limit=1)
    
    if model:
        # Remove existing rule if any
        env['ir.rule'].search([
            ('name', '=', 'GPS Position: Multi-Company'),
            ('model_id', '=', model.id)
        ]).unlink()
        
        # Create the rule
        group = env.ref('base.group_multi_company', raise_if_not_found=False)
        if group:
            env['ir.rule'].create({
                'name': 'GPS Position: Multi-Company',
                'model_id': model.id,
                'domain_force': "[('company_id', 'in', company_ids)]",
                'groups': [(4, group.id)],
            })
        
        # Create access rights
        groups = {
            'user': env.ref('shuttlebee.group_shuttle_user', raise_if_not_found=False),
            'driver': env.ref('shuttlebee.group_shuttle_driver', raise_if_not_found=False),
            'dispatcher': env.ref('shuttlebee.group_shuttle_dispatcher', raise_if_not_found=False),
            'manager': env.ref('shuttlebee.group_shuttle_manager', raise_if_not_found=False),
        }
        
        access_rights = [
            ('user', True, False, False, False),
            ('driver', True, True, False, False),
            ('dispatcher', True, True, True, False),
            ('manager', True, True, True, True),
        ]
        
        for role, read, write, create, unlink in access_rights:
            group = groups.get(role)
            if group:
                # Remove existing access if any
                env['ir.model.access'].search([
                    ('name', '=', f'shuttle.gps.position.{role}'),
                    ('model_id', '=', model.id),
                    ('group_id', '=', group.id)
                ]).unlink()
                
                # Create access right
                env['ir.model.access'].create({
                    'name': f'shuttle.gps.position.{role}',
                    'model_id': model.id,
                    'group_id': group.id,
                    'perm_read': read,
                    'perm_write': write,
                    'perm_create': create,
                    'perm_unlink': unlink,
                })
    
    # Auto-assign ShuttleBee groups to existing users
    users = env['res.users'].search([('active', '=', True)])
    if users:
        users._auto_assign_shuttle_groups()
    
    # Recompute location displays for all passenger group lines
    with env.registry.cursor() as cr:
        env_cr = api.Environment(cr, SUPERUSER_ID, {})
        lines = env_cr['shuttle.passenger.group.line'].search([])
        if lines:
            lines._compute_location_displays()
            cr.commit()

