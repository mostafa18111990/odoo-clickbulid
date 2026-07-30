import json

from odoo import _, api, fields, models
from odoo.exceptions import UserError


SEED_VERSION = '1.0'
DEMO_CONTEXT = {
    'tracking_disable': True,
    'mail_create_nosubscribe': True,
    'mail_notrack': True,
}
SECTOR_SCENARIOS = {
    'construction': {
        'customer': 'شركة الأفق للمقاولات (تجريبي)',
        'project': 'مشروع تجهيز فرع الرياض (تجريبي)',
        'stock': ('مواد تشطيب قياسية', 185.0, 115.0),
        'stock_2': ('وحدة إنارة للمشروعات', 240.0, 150.0),
        'service': ('خدمة إدارة وتنفيذ المشروع', 12500.0, 0.0),
    },
    'trading': {
        'customer': 'شركة مسارات التوزيع (تجريبي)',
        'project': 'إطلاق قناة توزيع جديدة (تجريبي)',
        'stock': ('جهاز أعمال احترافي', 1450.0, 920.0),
        'stock_2': ('ملحق جهاز أعمال', 280.0, 160.0),
        'service': ('خدمة تركيب وتدريب', 1800.0, 0.0),
    },
    'retail': {
        'customer': 'متاجر الواجهة الحديثة (تجريبي)',
        'project': 'افتتاح فرع تجزئة جديد (تجريبي)',
        'stock': ('منتج تجزئة رئيسي', 129.0, 72.0),
        'stock_2': ('منتج تجزئة مكمل', 69.0, 34.0),
        'service': ('خدمة توصيل وتجهيز', 120.0, 0.0),
    },
    'restaurant': {
        'customer': 'مجموعة مذاق الأعمال (تجريبي)',
        'project': 'تجهيز قائمة موسمية (تجريبي)',
        'stock': ('مادة غذائية أساسية', 48.0, 27.0),
        'stock_2': ('عبوات تقديم', 18.0, 9.0),
        'service': ('خدمة ضيافة شركات', 2200.0, 0.0),
    },
    'manufacturing': {
        'customer': 'مصنع الحلول المتقدمة (تجريبي)',
        'project': 'تحسين خط الإنتاج (تجريبي)',
        'stock': ('مكوّن صناعي رئيسي', 320.0, 190.0),
        'stock_2': ('مكوّن صناعي مساعد', 95.0, 48.0),
        'service': ('خدمة ضبط جودة وتشغيل', 4500.0, 0.0),
    },
    'services': {
        'customer': 'شركة رؤية للاستشارات (تجريبي)',
        'project': 'مشروع التحول التشغيلي (تجريبي)',
        'stock': ('حزمة أجهزة ميدانية', 980.0, 620.0),
        'stock_2': ('قطع غيار للخدمة', 160.0, 85.0),
        'service': ('باقة استشارات وتنفيذ', 15000.0, 0.0),
    },
    'real_estate': {
        'customer': 'شركة نماء العقارية (تجريبي)',
        'project': 'تسويق وإدارة مجمع أعمال (تجريبي)',
        'stock': ('حزمة تجهيز وحدة', 850.0, 520.0),
        'stock_2': ('مواد صيانة وحدة', 210.0, 125.0),
        'service': ('خدمة إدارة وتسويق عقاري', 9000.0, 0.0),
    },
    'ecommerce': {
        'customer': 'متجر بوابة السوق (تجريبي)',
        'project': 'إطلاق حملة المتجر الرقمية (تجريبي)',
        'stock': ('منتج متجر إلكتروني', 249.0, 135.0),
        'stock_2': ('إضافة للمنتج', 79.0, 38.0),
        'service': ('خدمة تجهيز وشحن سريع', 85.0, 0.0),
    },
    'education': {
        'customer': 'أكاديمية المهارات الحديثة (تجريبي)',
        'project': 'إطلاق برنامج تدريبي جديد (تجريبي)',
        'stock': ('حقيبة متدرب', 190.0, 95.0),
        'stock_2': ('مادة تعليمية مطبوعة', 65.0, 28.0),
        'service': ('برنامج تدريبي للشركات', 7800.0, 0.0),
    },
    'other': {
        'customer': 'شركة رواد الأعمال (تجريبي)',
        'project': 'تطوير العمليات الداخلية (تجريبي)',
        'stock': ('منتج أعمال رئيسي', 450.0, 260.0),
        'stock_2': ('منتج أعمال مساعد', 125.0, 68.0),
        'service': ('خدمة تنفيذ ودعم', 6500.0, 0.0),
    },
}
SCENARIO_ALIASES = {
    'trading-distribution': 'trading',
    'restaurants-cafes': 'restaurant',
    'professional-services': 'services',
    'field-services': 'services',
    'startups-smes': 'other',
}


class SaasDemoSeed(models.AbstractModel):
    _name = 'saas.demo.seed'
    _description = 'Safe Enterprise Demo Business Cycle Seeder'

    @api.model
    def seed_demo_cycle(self, sector='other'):
        params = self.env['ir.config_parameter'].sudo()
        demo_mode = (params.get_param('saas.demo_mode') or '').strip().lower()
        if demo_mode not in ('1', 'true', 'yes'):
            raise UserError(_('Sample operations can only be created in an isolated demo database.'))

        previous = params.get_param('saas.demo.seed.version')
        if previous == SEED_VERSION:
            raw_summary = params.get_param('saas.demo.seed.summary') or '{}'
            try:
                summary = json.loads(raw_summary)
            except (TypeError, ValueError):
                summary = {'status': 'already_seeded', 'version': SEED_VERSION}
            return self._seed_sector_pack(sector, summary)

        scenario_key = SCENARIO_ALIASES.get(sector, sector)
        scenario = SECTOR_SCENARIOS.get(scenario_key) or SECTOR_SCENARIOS['other']
        env = self.env(context=dict(self.env.context, **DEMO_CONTEXT))
        company = env.company

        customer = env['res.partner'].create({
            'name': scenario['customer'],
            'company_type': 'company',
            'customer_rank': 1,
            'email': 'customer.demo@example.invalid',
            'phone': '+966 50 000 0101',
            'city': 'الرياض',
            'country_id': company.country_id.id,
            'company_id': company.id,
            'comment': 'بيانات تجريبية آمنة لشرح دورة العمل.',
        })
        vendor = env['res.partner'].create({
            'name': 'شركة الإمداد الذكي (تجريبي)',
            'company_type': 'company',
            'supplier_rank': 1,
            'email': 'vendor.demo@example.invalid',
            'phone': '+966 50 000 0202',
            'city': 'جدة',
            'country_id': company.country_id.id,
            'company_id': company.id,
            'comment': 'مورد تجريبي لدورة المشتريات والمخزون.',
        })
        prospect = env['res.partner'].create({
            'name': 'مؤسسة نمو المستقبل (عميل محتمل تجريبي)',
            'company_type': 'company',
            'customer_rank': 1,
            'email': 'prospect.demo@example.invalid',
            'phone': '+966 50 000 0303',
            'city': 'الدمام',
            'country_id': company.country_id.id,
            'company_id': company.id,
        })

        products = []
        for name, sale_price, cost in (scenario['stock'], scenario['stock_2']):
            template = env['product.template'].create({
                'name': '%s (تجريبي)' % name,
                'type': 'consu',
                'is_storable': True,
                'sale_ok': True,
                'purchase_ok': True,
                'list_price': sale_price,
                'standard_price': cost,
                'company_id': company.id,
            })
            products.append(template.product_variant_id)
        service_name, service_price, service_cost = scenario['service']
        service = env['product.template'].create({
            'name': '%s (تجريبي)' % service_name,
            'type': 'service',
            'sale_ok': True,
            'purchase_ok': False,
            'list_price': service_price,
            'standard_price': service_cost,
            'company_id': company.id,
        }).product_variant_id

        lead_new = env['crm.lead'].create({
            'name': 'طلب عرض أولي — مؤسسة نمو المستقبل (تجريبي)',
            'partner_id': prospect.id,
            'type': 'opportunity',
            'expected_revenue': 18000.0,
            'probability': 20.0,
            'company_id': company.id,
        })
        lead_qualified = env['crm.lead'].create({
            'name': 'توسعة عقد عميل قائم (تجريبي)',
            'partner_id': customer.id,
            'type': 'opportunity',
            'expected_revenue': 32000.0,
            'probability': 65.0,
            'company_id': company.id,
        })
        lead_won = env['crm.lead'].create({
            'name': 'توريد وتنفيذ متكامل (تجريبي)',
            'partner_id': customer.id,
            'type': 'opportunity',
            'expected_revenue': 45000.0,
            'probability': 90.0,
            'company_id': company.id,
        })
        lead_won.action_set_won_rainbowman()

        purchase = env['purchase.order'].create({
            'partner_id': vendor.id,
            'company_id': company.id,
            'origin': 'دورة ديمو متكاملة',
            'order_line': [
                (0, 0, {
                    'product_id': products[0].id,
                    'name': products[0].display_name,
                    'product_qty': 60.0,
                    'product_uom_id': products[0].uom_id.id,
                    'price_unit': scenario['stock'][2],
                    'date_planned': fields.Datetime.now(),
                }),
                (0, 0, {
                    'product_id': products[1].id,
                    'name': products[1].display_name,
                    'product_qty': 40.0,
                    'product_uom_id': products[1].uom_id.id,
                    'price_unit': scenario['stock_2'][2],
                    'date_planned': fields.Datetime.now(),
                }),
            ],
        })
        purchase.button_confirm()
        self._complete_pickings(purchase.picking_ids)
        purchase.action_create_invoice()
        vendor_bills = purchase.invoice_ids.filtered(lambda move: move.state == 'draft')
        vendor_bills.write({'invoice_date': fields.Date.context_today(self)})
        self._safe_post_demo_moves(vendor_bills)
        self._register_payments(vendor_bills)

        quotation = env['sale.order'].create({
            'partner_id': prospect.id,
            'company_id': company.id,
            'opportunity_id': lead_new.id,
            'client_order_ref': 'عرض متابعة تجريبي',
            'order_line': [
                (0, 0, {
                    'product_id': products[0].id,
                    'name': products[0].display_name,
                    'product_uom_id': products[0].uom_id.id,
                    'product_uom_qty': 6.0,
                    'price_unit': scenario['stock'][1],
                }),
                (0, 0, {
                    'product_id': service.id,
                    'name': service.display_name,
                    'product_uom_id': service.uom_id.id,
                    'product_uom_qty': 1.0,
                    'price_unit': scenario['service'][1],
                }),
            ],
        })
        sale = env['sale.order'].create({
            'partner_id': customer.id,
            'company_id': company.id,
            'opportunity_id': lead_won.id,
            'client_order_ref': 'أمر عميل تجريبي مكتمل',
            'order_line': [
                (0, 0, {
                    'product_id': products[0].id,
                    'name': products[0].display_name,
                    'product_uom_id': products[0].uom_id.id,
                    'product_uom_qty': 12.0,
                    'price_unit': scenario['stock'][1],
                }),
                (0, 0, {
                    'product_id': products[1].id,
                    'name': products[1].display_name,
                    'product_uom_id': products[1].uom_id.id,
                    'product_uom_qty': 8.0,
                    'price_unit': scenario['stock_2'][1],
                }),
                (0, 0, {
                    'product_id': service.id,
                    'name': service.display_name,
                    'product_uom_id': service.uom_id.id,
                    'product_uom_qty': 1.0,
                    'price_unit': scenario['service'][1],
                }),
            ],
        })
        sale.action_confirm()
        self._complete_pickings(sale.picking_ids)
        customer_invoices = sale._create_invoices()
        customer_invoices.write({'invoice_date': fields.Date.context_today(self)})
        self._safe_post_demo_moves(customer_invoices)
        self._register_payments(customer_invoices)

        project = env['project.project'].create({
            'name': scenario['project'],
            'partner_id': customer.id,
            'company_id': company.id,
        })
        tasks = env['project.task'].create([
            {
                'name': 'تحليل المتطلبات واعتماد النطاق (تجريبي)',
                'project_id': project.id,
                'partner_id': customer.id,
            },
            {
                'name': 'التجهيز والتنفيذ (تجريبي)',
                'project_id': project.id,
                'partner_id': customer.id,
            },
            {
                'name': 'التدريب والتسليم النهائي (تجريبي)',
                'project_id': project.id,
                'partner_id': customer.id,
            },
        ])

        summary = {
            'status': 'seeded',
            'version': SEED_VERSION,
            'sector': sector,
            'customers': 2,
            'vendors': 1,
            'products': len(products) + 1,
            'crm_opportunities': len(lead_new + lead_qualified + lead_won),
            'purchase_orders': len(purchase),
            'vendor_bills': len(vendor_bills),
            'quotations': len(quotation),
            'sales_orders': len(sale),
            'customer_invoices': len(customer_invoices),
            'projects': len(project),
            'tasks': len(tasks),
        }
        summary = self._seed_sector_pack(sector, summary)
        params.set_param('saas.demo.seed.version', SEED_VERSION)
        params.set_param('saas.demo.seed.summary', json.dumps(summary, ensure_ascii=False))
        return summary

    @api.model
    def _seed_sector_pack(self, sector, summary):
        requirements = {
            'manufacturing': {
                'maintenance.equipment', 'maintenance.request', 'mrp.bom',
                'mrp.production', 'mrp.workcenter', 'quality.check', 'quality.point',
            },
            'construction': {'account.analytic.line', 'project.milestone'},
            'trading-distribution': {
                'stock.warehouse', 'stock.warehouse.orderpoint'},
            'retail': {'pos.config', 'pos.session'},
            'restaurants-cafes': {
                'pos.config', 'pos.session', 'restaurant.floor', 'restaurant.table'},
            'professional-services': {
                'account.analytic.line', 'helpdesk.ticket', 'project.milestone'},
            'real-estate': {
                'documents.document', 'maintenance.equipment', 'maintenance.request'},
            'ecommerce': {'sale.order'},
            'field-services': {
                'helpdesk.ticket', 'maintenance.equipment', 'maintenance.request'},
            'education': {
                'event.event', 'event.event.ticket', 'event.registration'},
            'startups-smes': {
                'project.milestone', 'stock.warehouse.orderpoint'},
        }
        required = requirements.get(sector, set())
        missing = sorted(model for model in required if model not in self.env)
        if missing:
            raise UserError(_(
                'The %s demo requires these installed applications: %s',
                sector, ', '.join(missing)))
        if sector == 'manufacturing':
            sector_summary = self.env['saas.demo.seed.manufacturing'].sudo().seed()
        else:
            sector_summary = self.env[
                'saas.demo.seed.sector.operations'].sudo().seed(sector)
        summary = dict(summary)
        summary[sector] = sector_summary
        self.env['ir.config_parameter'].sudo().set_param(
            'saas.demo.seed.summary', json.dumps(summary, ensure_ascii=False))
        return summary

    @api.model
    def _complete_pickings(self, pickings):
        for picking in pickings.filtered(lambda item: item.state not in ('done', 'cancel')):
            picking.action_assign()
            for move in picking.move_ids.filtered(lambda item: item.state != 'cancel'):
                move.quantity = move.product_uom_qty
                if 'picked' in move._fields:
                    move.picked = True
            result = picking.button_validate()
            if isinstance(result, dict) and result.get('res_model') == 'stock.backorder.confirmation':
                wizard = self.env[result['res_model']].with_context(
                    result.get('context') or {}).create({})
                wizard.process_cancel_backorder()
            elif isinstance(result, dict) and result.get('res_model') == 'confirm.stock.sms':
                wizard = self.env[result['res_model']].with_context(
                    result.get('context') or {}).browse(result.get('res_id')).exists()
                if not wizard:
                    wizard = self.env[result['res_model']].with_context(
                        result.get('context') or {}).create({'pick_ids': [(6, 0, picking.ids)]})
                wizard.dont_send_sms()
        return True

    @api.model
    def _register_payments(self, invoices):
        posted = invoices.filtered(
            lambda move: move.state == 'posted' and move.payment_state not in ('paid', 'in_payment'))
        for invoice in posted:
            wizard = self.env['account.payment.register'].with_context(
                active_model='account.move',
                active_ids=invoice.ids,
            ).create({})
            wizard.action_create_payments()
        return True

    @api.model
    def _safe_post_demo_moves(self, moves):
        """Post demo invoices unless Saudi EDI still needs legal onboarding."""
        for move in moves.filtered(lambda item: item.state == 'draft'):
            try:
                with self.env.cr.savepoint():
                    move.action_post()
            except UserError:
                move.message_post(body=_(
                    'This sample invoice remains in draft because the isolated '
                    'demo company is not connected to ZATCA.'))
        return moves.filtered(lambda item: item.state == 'posted')
