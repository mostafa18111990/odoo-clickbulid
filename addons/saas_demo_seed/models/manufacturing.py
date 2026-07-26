from datetime import timedelta

from odoo import api, fields, models

from .seed_service import DEMO_CONTEXT


MANUFACTURING_PACK_VERSION = '1.0'


class SaasDemoSeedManufacturing(models.AbstractModel):
    _name = 'saas.demo.seed.manufacturing'
    _description = 'Manufacturing Enterprise Demo Scenario'

    @api.model
    def seed(self):
        params = self.env['ir.config_parameter'].sudo()
        if params.get_param('saas.demo.seed.manufacturing.version') == MANUFACTURING_PACK_VERSION:
            return self._summary('already_seeded')

        env = self.env(context=dict(self.env.context, **DEMO_CONTEXT))
        company = env.company
        vendor = env['res.partner'].search(
            [('email', '=', 'vendor.demo@example.invalid')], limit=1)

        raw_steel = self._product(
            env, 'ألواح فولاذ مقاوم (مادة خام تجريبية)', 0.0, 72.0,
            sale_ok=False, purchase_ok=True)
        raw_motor = self._product(
            env, 'محرك صناعي 2 حصان (مادة خام تجريبية)', 0.0, 640.0,
            sale_ok=False, purchase_ok=True)
        raw_packaging = self._product(
            env, 'عبوة وشعار المنتج (مادة تعبئة تجريبية)', 0.0, 18.0,
            sale_ok=False, purchase_ok=True)
        finished = self._product(
            env, 'مضخة ذكية صناعية — منتج نهائي (تجريبي)', 2850.0, 0.0,
            sale_ok=True, purchase_ok=False)
        raw_products = raw_steel + raw_motor + raw_packaging

        raw_purchase = env['purchase.order'].create({
            'partner_id': vendor.id,
            'company_id': company.id,
            'origin': 'توريد مواد خام لخطة الإنتاج (تجريبي)',
            'order_line': [
                (0, 0, self._purchase_line(raw_steel, 120.0)),
                (0, 0, self._purchase_line(raw_motor, 60.0)),
                (0, 0, self._purchase_line(raw_packaging, 200.0)),
            ],
        })
        raw_purchase.button_confirm()
        env['saas.demo.seed']._complete_pickings(raw_purchase.picking_ids)

        workcenters = env['mrp.workcenter'].create([
            {
                'name': 'مركز القص والتشكيل (تجريبي)',
                'code': 'DEMO-CUT',
                'company_id': company.id,
                'time_efficiency': 90.0,
                'costs_hour': 180.0,
            },
            {
                'name': 'خط التجميع (تجريبي)',
                'code': 'DEMO-ASM',
                'company_id': company.id,
                'time_efficiency': 95.0,
                'costs_hour': 220.0,
            },
            {
                'name': 'محطة الفحص والتعبئة (تجريبي)',
                'code': 'DEMO-QA',
                'company_id': company.id,
                'time_efficiency': 100.0,
                'costs_hour': 160.0,
            },
        ])

        category = env['maintenance.equipment.category'].create({
            'name': 'معدات خط المضخات (تجريبي)',
        })
        maintenance_team = env['maintenance.team'].search([], limit=1)
        equipment = env['maintenance.equipment'].create([
            {
                'name': 'ماكينة قص CNC-01 (تجريبي)',
                'equipment_assign_to': 'other',
                'category_id': category.id,
                'maintenance_team_id': maintenance_team.id,
                'company_id': company.id,
                'note': 'معدة تجريبية مرتبطة بمرحلة القص والتشكيل.',
            },
            {
                'name': 'محطة تجميع ASM-02 (تجريبي)',
                'equipment_assign_to': 'other',
                'category_id': category.id,
                'maintenance_team_id': maintenance_team.id,
                'company_id': company.id,
                'note': 'معدة تجريبية لعمليات التجميع النهائي.',
            },
            {
                'name': 'جهاز اختبار الضغط QA-03 (تجريبي)',
                'equipment_assign_to': 'other',
                'category_id': category.id,
                'maintenance_team_id': maintenance_team.id,
                'company_id': company.id,
                'note': 'جهاز تجريبي لاختبار جودة المنتج النهائي.',
            },
        ])

        bom = env['mrp.bom'].create({
            'code': 'DEMO-BOM-PUMP-01',
            'product_tmpl_id': finished.product_tmpl_id.id,
            'product_qty': 1.0,
            'product_uom_id': finished.uom_id.id,
            'type': 'normal',
            'company_id': company.id,
            'bom_line_ids': [
                (0, 0, {
                    'product_id': raw_steel.id,
                    'product_qty': 2.0,
                    'product_uom_id': raw_steel.uom_id.id,
                }),
                (0, 0, {
                    'product_id': raw_motor.id,
                    'product_qty': 1.0,
                    'product_uom_id': raw_motor.uom_id.id,
                }),
                (0, 0, {
                    'product_id': raw_packaging.id,
                    'product_qty': 1.0,
                    'product_uom_id': raw_packaging.uom_id.id,
                }),
            ],
        })
        operations = env['mrp.routing.workcenter'].create([
            {
                'name': 'قص وتشكيل جسم المضخة (تجريبي)',
                'bom_id': bom.id,
                'workcenter_id': workcenters[0].id,
                'time_cycle_manual': 25.0,
            },
            {
                'name': 'تركيب المحرك والتجميع (تجريبي)',
                'bom_id': bom.id,
                'workcenter_id': workcenters[1].id,
                'time_cycle_manual': 35.0,
            },
            {
                'name': 'اختبار الضغط والتعبئة (تجريبي)',
                'bom_id': bom.id,
                'workcenter_id': workcenters[2].id,
                'time_cycle_manual': 20.0,
            },
        ])

        quality_team = env['quality.alert.team'].search([], limit=1)
        test_type = env['quality.point.test_type'].search([], limit=1)
        manufacturing_type = env['stock.picking.type'].search([
            ('code', '=', 'mrp_operation'),
            ('company_id', 'in', (False, company.id)),
        ], limit=1)
        quality_points = env['quality.point'].create([
            {
                'name': 'فحص أبعاد جسم المضخة (تجريبي)',
                'team_id': quality_team.id,
                'test_type_id': test_type.id,
                'company_id': company.id,
                'product_ids': [(6, 0, finished.ids)],
                'picking_type_ids': [(6, 0, manufacturing_type.ids)],
                'operation_id': operations[0].id,
                'is_workorder_step': True,
                'note': 'التحقق من الأبعاد وسلامة الحواف بعد القص.',
            },
            {
                'name': 'فحص التجميع والعزم (تجريبي)',
                'team_id': quality_team.id,
                'test_type_id': test_type.id,
                'company_id': company.id,
                'product_ids': [(6, 0, finished.ids)],
                'picking_type_ids': [(6, 0, manufacturing_type.ids)],
                'operation_id': operations[1].id,
                'is_workorder_step': True,
                'note': 'التأكد من تثبيت المحرك وعزم المسامير.',
            },
            {
                'name': 'اختبار الضغط النهائي (تجريبي)',
                'team_id': quality_team.id,
                'test_type_id': test_type.id,
                'company_id': company.id,
                'product_ids': [(6, 0, finished.ids)],
                'picking_type_ids': [(6, 0, manufacturing_type.ids)],
                'operation_id': operations[2].id,
                'is_workorder_step': True,
                'note': 'تشغيل اختبار الضغط واعتماد المنتج قبل التعبئة.',
            },
        ])

        completed_mo = self._create_mo(env, finished, bom, 10.0)
        self._complete_mo(completed_mo)
        planned_mo = self._create_mo(env, finished, bom, 20.0)
        planned_mo.action_confirm()
        planned_mo.button_plan()
        planned_mo.action_assign()
        draft_mo = self._create_mo(env, finished, bom, 30.0)

        done_stage = env['maintenance.stage'].search([('done', '=', True)], limit=1)
        maintenance_requests = env['maintenance.request'].create([
            {
                'name': 'صيانة وقائية دورية لماكينة القص (تجريبي)',
                'equipment_id': equipment[0].id,
                'maintenance_type': 'preventive',
                'maintenance_team_id': maintenance_team.id,
                'company_id': company.id,
                'schedule_date': fields.Datetime.now() + timedelta(days=7),
                'duration': 2.0,
            },
            {
                'name': 'معالجة اهتزاز بمحطة التجميع (تجريبي)',
                'equipment_id': equipment[1].id,
                'maintenance_type': 'corrective',
                'maintenance_team_id': maintenance_team.id,
                'company_id': company.id,
                'schedule_date': fields.Datetime.now() - timedelta(days=2),
                'stage_id': done_stage.id,
                'close_date': fields.Date.context_today(self),
                'duration': 3.5,
            },
        ])

        manual_check = env['quality.check'].create({
            'name': 'عينة مرفوضة — تسريب ضغط (تجريبي)',
            'team_id': quality_team.id,
            'test_type_id': test_type.id,
            'company_id': company.id,
            'product_id': finished.id,
            'production_id': planned_mo.id,
            'point_id': quality_points[2].id,
            'note': 'سيناريو تجريبي يوضح حالة فشل الجودة وإعادة المعالجة.',
        })
        manual_check.do_fail()

        params.set_param(
            'saas.demo.seed.manufacturing.version', MANUFACTURING_PACK_VERSION)
        return {
            'status': 'seeded',
            'version': MANUFACTURING_PACK_VERSION,
            'raw_materials': len(raw_products),
            'finished_products': len(finished),
            'raw_material_purchase_orders': len(raw_purchase),
            'workcenters': len(workcenters),
            'equipment': len(equipment),
            'boms': len(bom),
            'operations': len(operations),
            'quality_points': len(quality_points),
            'quality_checks': env['quality.check'].search_count([
                ('production_id', 'in', (completed_mo + planned_mo).ids),
            ]),
            'manufacturing_orders_done': len(completed_mo.filtered(
                lambda record: record.state == 'done')),
            'manufacturing_orders_planned': len(planned_mo),
            'manufacturing_orders_draft': len(draft_mo),
            'maintenance_requests': len(maintenance_requests),
        }

    @api.model
    def _summary(self, status):
        env = self.env
        return {
            'status': status,
            'version': MANUFACTURING_PACK_VERSION,
            'raw_materials': env['product.product'].search_count([
                ('name', 'ilike', 'مادة خام تجريبية')]),
            'finished_products': env['product.product'].search_count([
                ('name', 'ilike', 'منتج نهائي')]),
            'workcenters': env['mrp.workcenter'].search_count([
                ('code', 'like', 'DEMO-')]),
            'equipment': env['maintenance.equipment'].search_count([
                ('name', 'ilike', 'تجريبي')]),
            'boms': env['mrp.bom'].search_count([
                ('code', '=', 'DEMO-BOM-PUMP-01')]),
            'manufacturing_orders_done': env['mrp.production'].search_count([
                ('bom_id.code', '=', 'DEMO-BOM-PUMP-01'), ('state', '=', 'done')]),
            'maintenance_requests': env['maintenance.request'].search_count([
                ('name', 'ilike', 'تجريبي')]),
        }

    @api.model
    def _product(self, env, name, sale_price, cost, sale_ok, purchase_ok):
        template = env['product.template'].create({
            'name': name,
            'type': 'consu',
            'is_storable': True,
            'sale_ok': sale_ok,
            'purchase_ok': purchase_ok,
            'list_price': sale_price,
            'standard_price': cost,
            'company_id': env.company.id,
        })
        return template.product_variant_id

    @api.model
    def _purchase_line(self, product, quantity):
        return {
            'product_id': product.id,
            'name': product.display_name,
            'product_qty': quantity,
            'product_uom_id': product.uom_id.id,
            'price_unit': product.standard_price,
            'date_planned': fields.Datetime.now(),
        }

    @api.model
    def _create_mo(self, env, product, bom, quantity):
        return env['mrp.production'].create({
            'product_id': product.id,
            'product_qty': quantity,
            'product_uom_id': product.uom_id.id,
            'bom_id': bom.id,
            'company_id': env.company.id,
        })

    @api.model
    def _complete_mo(self, production):
        production.action_confirm()
        production.button_plan()
        production.action_assign()
        for move in production.move_raw_ids:
            move.quantity = move.product_uom_qty
            if 'picked' in move._fields:
                move.picked = True
        production.qty_producing = production.product_qty
        for check in production.check_ids.filtered(
                lambda item: item.quality_state == 'none'):
            check.do_pass()
        for workorder in production.workorder_ids:
            if workorder.state == 'ready':
                workorder.button_start()
            for check in workorder.check_ids.filtered(
                    lambda item: item.quality_state == 'none'):
                check.do_pass()
            workorder.qty_producing = workorder.qty_remaining
            if workorder.state not in ('done', 'cancel'):
                workorder.button_finish()
        if production.state != 'done':
            production.button_mark_done()
        return True
