# -*- coding: utf-8 -*-

from odoo import api, SUPERUSER_ID


def post_init_hook(cr, registry):
    """Create GPS position multi-company rule after models are loaded"""
    env = api.Environment(cr, SUPERUSER_ID, {})
    
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

