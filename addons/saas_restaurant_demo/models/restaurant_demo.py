import json
from datetime import datetime, time, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from odoo.addons.saas_demo_seed.models.seed_service import DEMO_CONTEXT


RESTAURANT_SEED_VERSION = '2.0'


class RestaurantDemoChannel(models.Model):
    _name = 'restaurant.demo.channel'
    _description = 'Restaurant Sales Channel'
    _order = 'sequence, name'

    name = fields.Char(required=True)
    code = fields.Char(required=True, index=True)
    sequence = fields.Integer(default=10)
    channel_type = fields.Selection([
        ('dine_in', 'Dine In'),
        ('pickup', 'Pickup'),
        ('own_delivery', 'Own Delivery'),
        ('aggregator', 'Delivery Platform'),
    ], required=True)
    commission_rate = fields.Float(string='Commission %', digits=(5, 2))
    payment_gateway_rate = fields.Float(string='Gateway Fee %', digits=(5, 2))
    partner_id = fields.Many2one('res.partner')
    analytic_account_id = fields.Many2one('account.analytic.account')
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', required=True, default=lambda self: self.env.company)

    _code_company_unique = models.Constraint(
        'UNIQUE(code, company_id)', 'The channel code must be unique per company.')

    @api.constrains('commission_rate', 'payment_gateway_rate')
    def _check_rates(self):
        for record in self:
            if not 0 <= record.commission_rate <= 100:
                raise ValidationError(_('Commission must be between 0 and 100%.'))
            if not 0 <= record.payment_gateway_rate <= 100:
                raise ValidationError(_('Gateway fee must be between 0 and 100%.'))


class RestaurantDemoOrder(models.Model):
    _name = 'restaurant.demo.order'
    _description = 'Restaurant Omnichannel Order'
    _order = 'order_datetime desc, id desc'

    name = fields.Char(required=True, default='New')
    external_reference = fields.Char(required=True, index=True)
    order_datetime = fields.Datetime(required=True, default=fields.Datetime.now)
    channel_id = fields.Many2one(
        'restaurant.demo.channel', required=True, ondelete='restrict')
    partner_id = fields.Many2one('res.partner', string='Customer')
    product_id = fields.Many2one('product.product', required=True)
    quantity = fields.Float(default=1.0, required=True)
    branch_id = fields.Many2one(
        'account.analytic.account', string='Branch / Profit Center', required=True)
    pos_order_id = fields.Many2one('pos.order')
    driver_id = fields.Many2one('hr.employee')
    vehicle_id = fields.Many2one('fleet.vehicle')
    food_amount = fields.Monetary(required=True)
    vat_amount = fields.Monetary(required=True)
    delivery_fee = fields.Monetary()
    discount_amount = fields.Monetary()
    platform_discount_share = fields.Monetary()
    commission_amount = fields.Monetary(
        compute='_compute_financials', store=True)
    gateway_fee = fields.Monetary(
        compute='_compute_financials', store=True)
    net_due = fields.Monetary(compute='_compute_financials', store=True)
    cost_amount = fields.Monetary(required=True)
    margin_amount = fields.Monetary(compute='_compute_financials', store=True)
    margin_percent = fields.Float(compute='_compute_financials', store=True)
    preparation_minutes = fields.Integer(default=18)
    delivery_minutes = fields.Integer(default=0)
    state = fields.Selection([
        ('received', 'Received'),
        ('kitchen', 'In Kitchen'),
        ('ready', 'Ready'),
        ('out_for_delivery', 'Out for Delivery'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
        ('refunded', 'Refunded'),
    ], default='received', required=True)
    company_id = fields.Many2one(
        'res.company', required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one(
        related='company_id.currency_id', store=True, readonly=True)

    _external_channel_unique = models.Constraint(
        'UNIQUE(external_reference, channel_id)',
        'The external order reference must be unique per channel.')

    @api.depends(
        'food_amount', 'vat_amount', 'delivery_fee', 'discount_amount',
        'platform_discount_share', 'cost_amount',
        'channel_id.commission_rate', 'channel_id.payment_gateway_rate')
    def _compute_financials(self):
        for record in self:
            commission_base = max(record.food_amount - record.discount_amount, 0.0)
            record.commission_amount = (
                commission_base * record.channel_id.commission_rate / 100.0)
            record.gateway_fee = (
                commission_base * record.channel_id.payment_gateway_rate / 100.0)
            record.net_due = (
                record.food_amount + record.vat_amount + record.delivery_fee
                - record.discount_amount - record.commission_amount
                - record.gateway_fee + record.platform_discount_share)
            record.margin_amount = (
                record.food_amount - record.discount_amount
                - record.commission_amount - record.gateway_fee
                - record.cost_amount + record.platform_discount_share)
            net_sales = record.food_amount - record.discount_amount
            record.margin_percent = (
                record.margin_amount / net_sales * 100.0 if net_sales else 0.0)


class RestaurantDemoSettlement(models.Model):
    _name = 'restaurant.demo.settlement'
    _description = 'Restaurant Delivery Platform Settlement'
    _order = 'date_to desc, id desc'

    name = fields.Char(required=True)
    channel_id = fields.Many2one(
        'restaurant.demo.channel', required=True,
        domain=[('channel_type', '=', 'aggregator')])
    date_from = fields.Date(required=True)
    date_to = fields.Date(required=True)
    order_count = fields.Integer()
    gross_amount = fields.Monetary()
    commission_amount = fields.Monetary()
    gateway_fees = fields.Monetary()
    discounts = fields.Monetary()
    expected_net = fields.Monetary(compute='_compute_variance', store=True)
    received_amount = fields.Monetary()
    variance = fields.Monetary(compute='_compute_variance', store=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('reviewed', 'Reviewed'),
        ('matched', 'Matched'),
        ('difference', 'Difference'),
    ], default='draft', required=True)
    note = fields.Text()
    company_id = fields.Many2one(
        'res.company', required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one(
        related='company_id.currency_id', store=True, readonly=True)

    @api.depends(
        'gross_amount', 'commission_amount', 'gateway_fees', 'discounts',
        'received_amount')
    def _compute_variance(self):
        for record in self:
            record.expected_net = (
                record.gross_amount - record.commission_amount
                - record.gateway_fees - record.discounts)
            record.variance = record.received_amount - record.expected_net


class RestaurantDemoWaste(models.Model):
    _name = 'restaurant.demo.waste'
    _description = 'Restaurant Waste and Loss'
    _order = 'date desc, id desc'

    name = fields.Char(required=True)
    date = fields.Date(required=True, default=fields.Date.context_today)
    product_id = fields.Many2one('product.product', required=True)
    quantity = fields.Float(required=True)
    unit_cost = fields.Monetary(required=True)
    total_cost = fields.Monetary(compute='_compute_total', store=True)
    reason = fields.Selection([
        ('expired', 'Expired'),
        ('storage', 'Poor Storage'),
        ('preparation', 'Preparation Error'),
        ('cancelled', 'Cancelled Order'),
        ('return', 'Customer Return'),
        ('transport', 'Transport Damage'),
        ('overproduction', 'Overproduction'),
        ('employee_meal', 'Employee Meal'),
        ('sample', 'Free Sample'),
    ], required=True)
    branch_id = fields.Many2one(
        'account.analytic.account', required=True)
    notes = fields.Text()
    company_id = fields.Many2one(
        'res.company', required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one(
        related='company_id.currency_id', store=True, readonly=True)

    @api.depends('quantity', 'unit_cost')
    def _compute_total(self):
        for record in self:
            record.total_cost = record.quantity * record.unit_cost


class RestaurantDemoChecklist(models.Model):
    _name = 'restaurant.demo.checklist'
    _description = 'Restaurant Daily Checklist'
    _order = 'date desc, checklist_type, id desc'

    name = fields.Char(required=True)
    date = fields.Date(required=True, default=fields.Date.context_today)
    checklist_type = fields.Selection([
        ('opening', 'Branch Opening'),
        ('closing', 'Branch Closing'),
        ('food_safety', 'Food Safety'),
        ('cleaning', 'Cleaning'),
    ], required=True)
    branch_id = fields.Many2one(
        'account.analytic.account', required=True)
    responsible_id = fields.Many2one('hr.employee')
    items = fields.Text(required=True)
    state = fields.Selection([
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('done', 'Done'),
        ('issue', 'Issue Found'),
    ], default='pending', required=True)
    notes = fields.Text()
    company_id = fields.Many2one(
        'res.company', required=True, default=lambda self: self.env.company)


class SaasRestaurantDemoSeed(models.AbstractModel):
    _inherit = 'saas.demo.seed.sector.operations'

    @api.model
    def seed(self, sector):
        if sector != 'restaurants-cafes':
            return super().seed(sector)
        params = self.env['ir.config_parameter'].sudo()
        key = 'saas.restaurant.demo.seed.version'
        if params.get_param(key) == RESTAURANT_SEED_VERSION:
            raw = params.get_param('saas.restaurant.demo.seed.summary') or '{}'
            try:
                summary = json.loads(raw)
            except (TypeError, ValueError):
                summary = {}
            summary.update({
                'status': 'already_seeded',
                'version': RESTAURANT_SEED_VERSION,
                'sector': sector,
            })
            return summary
        result = self._seed_restaurants_cafes(
            self.env(context=dict(self.env.context, **DEMO_CONTEXT)))
        result.update({
            'status': 'seeded',
            'version': RESTAURANT_SEED_VERSION,
            'sector': sector,
        })
        params.set_param(key, RESTAURANT_SEED_VERSION)
        params.set_param(
            'saas.restaurant.demo.seed.summary',
            json.dumps(result, ensure_ascii=False))
        return result

    @api.model
    def _seed_restaurants_cafes(self, env):
        company = env.company
        today = fields.Date.context_today(self)
        self._configure_company(env)
        analytics = self._create_analytics(env)
        warehouses, locations = self._create_restaurant_warehouses(env)
        vendors = self._create_vendors(env)
        products = self._create_restaurant_products(env)
        boms = self._create_restaurant_boms(env, products)
        lots = self._seed_opening_stock(
            env, products, locations['central_stock'], today)
        purchases = self._create_purchase_cycle(
            env, vendors, products, analytics['purchasing'])
        productions = self._create_production_cycle(
            env, products, boms)
        replenishment = self._create_branch_replenishment(
            env, warehouses, products)
        channels = self._create_channels(env, analytics)
        pos_summary = self._create_restaurant_pos(
            env, warehouses, products)
        employees = self._create_restaurant_people(env, today)
        fleet = self._create_fleet(env)
        orders = self._create_month_orders(
            env, channels, analytics, products, employees, fleet, today)
        settlements = self._create_settlements(env, channels, orders, today)
        waste = self._create_waste(env, products, analytics, today)
        checklists = self._create_checklists(env, analytics, employees, today)
        quality = self._create_quality_and_maintenance(
            env, products, productions, today)
        approvals = self._create_approvals(env)
        support = self._create_customer_service(env)
        self._create_restaurant_analytic_entries(
            env, analytics, orders, waste, today)
        return {
            'company': company.name,
            'enterprise': bool(
                env['ir.module.module'].search_count([
                    ('name', '=', 'web_enterprise'),
                    ('state', '=', 'installed'),
                ])),
            'warehouses': len(warehouses),
            'specialized_locations': len(locations) - 1,
            'vendors': len(vendors),
            'products': len(products),
            'boms': len(boms),
            'tracked_lots': len(lots),
            'purchase_orders': len(purchases),
            'manufacturing_orders': len(productions),
            'branch_transfers': len(replenishment['transfers']),
            'reordering_rules': len(replenishment['orderpoints']),
            'sales_channels': len(channels),
            'month_orders': len(orders),
            'settlements': len(settlements),
            'waste_records': len(waste),
            'employees': len(employees),
            'vehicles': len(fleet),
            'quality_and_maintenance': quality,
            'approval_flows': len(approvals),
            'support_cases': len(support),
            **pos_summary,
            'workflow': (
                'procurement-receipt-lots-fefo-recipes-multi-level-production-'
                'restaurant-pos-aggregators-delivery-settlement-costing-profitability'),
        }

    @api.model
    def _configure_company(self, env):
        company = env.company
        country = env.ref('base.sa', raise_if_not_found=False)
        currency = env.ref('base.SAR', raise_if_not_found=False)
        values = {
            'name': 'مطاعم مذاق نجد (بيانات تجريبية)',
            'phone': '+966 11 000 0000',
            'email': 'demo.restaurant@example.invalid',
            'website': 'https://demo.example.invalid',
        }
        if country:
            values['country_id'] = country.id
        if currency:
            values['currency_id'] = currency.id
        company.write(values)
        partner_values = {
            'street': 'طريق الملك فهد — عنوان تجريبي',
            'street2': 'الرقم الإضافي 0000 — الرمز 0000',
            'city': 'الرياض',
            'zip': '00000',
            'vat': '310000000000003',
            'comment': (
                'جميع الأرقام القانونية والعناوين وبيانات الاتصال في هذه '
                'الشركة تجريبية وغير صالحة للاستخدام القانوني.'),
        }
        if country:
            partner_values['country_id'] = country.id
        company.partner_id.write(partner_values)
        if 'company_registry' in company._fields:
            company.company_registry = '1010000000-DEMO'
        env.user.write({'tz': 'Asia/Riyadh'})
        env['res.partner.bank'].create({
            'acc_number': 'DEMO-SA-NOT-A-REAL-BANK-ACCOUNT',
            'partner_id': company.partner_id.id,
            'company_id': company.id,
        })
        env['ir.config_parameter'].sudo().set_param(
            'saas.restaurant.demo.legal_disclaimer',
            'كل البيانات القانونية والمالية والشخصية في هذا الديمو تجريبية.')

    @api.model
    def _create_analytics(self, env):
        plan = env['account.analytic.plan'].create({
            'name': 'مراكز تكلفة وربحية المطعم (تجريبي)',
        })
        names = {
            'head_office': 'الإدارة العامة (تجريبي)',
            'central_kitchen': 'المطبخ المركزي (تجريبي)',
            'riyadh_main': 'فرع الرياض الرئيسي (تجريبي)',
            'riyadh_north': 'فرع شمال الرياض (تجريبي)',
            'delivery': 'قسم التوصيل (تجريبي)',
            'sales': 'قسم المبيعات (تجريبي)',
            'marketing': 'قسم التسويق (تجريبي)',
            'hr': 'الموارد البشرية (تجريبي)',
            'purchasing': 'قسم المشتريات (تجريبي)',
            'maintenance': 'قسم الصيانة (تجريبي)',
            'dine_in': 'صالة المطعم (تجريبي)',
            'pickup': 'الاستلام من الفرع (تجريبي)',
            'own_delivery': 'التوصيل الخاص (تجريبي)',
            'hungerstation': 'هنقرستيشن (تجريبي)',
            'jahez': 'جاهز (تجريبي)',
            'noon_food': 'نون فود (تجريبي)',
        }
        return {
            key: env['account.analytic.account'].create({
                'name': name,
                'plan_id': plan.id,
                'company_id': env.company.id,
            })
            for key, name in names.items()
        }

    @api.model
    def _create_restaurant_warehouses(self, env):
        company = env.company
        existing = env['stock.warehouse'].search([
            ('company_id', '=', company.id)], limit=1)
        existing.write({
            'name': 'المستودع والمطبخ المركزي (تجريبي)',
            'code': 'DMCTR',
        })
        main = env['stock.warehouse'].create({
            'name': 'مستودع فرع الرياض الرئيسي (تجريبي)',
            'code': 'DMR01',
            'company_id': company.id,
            'partner_id': company.partner_id.id,
        })
        north = env['stock.warehouse'].create({
            'name': 'مستودع فرع شمال الرياض (تجريبي)',
            'code': 'DMR02',
            'company_id': company.id,
            'partner_id': company.partner_id.id,
        })
        locations = {'central_stock': existing.lot_stock_id}
        labels = [
            ('receiving', 'منطقة استلام المواد'),
            ('dry', 'المواد الجافة'),
            ('chilled', 'مخزن التبريد'),
            ('frozen', 'مخزن التجميد'),
            ('preparation', 'منطقة التحضير'),
            ('production', 'منطقة الإنتاج'),
            ('ready', 'الوجبات الجاهزة'),
            ('waste', 'التالف والهدر'),
            ('returns', 'المرتجعات'),
        ]
        for warehouse_key, warehouse in (
                ('central', existing), ('main', main), ('north', north)):
            for key, label in labels:
                locations['%s_%s' % (warehouse_key, key)] = (
                    env['stock.location'].create({
                        'name': '%s — %s (تجريبي)' % (label, warehouse.name),
                        'location_id': warehouse.lot_stock_id.id,
                        'usage': 'internal',
                        'company_id': company.id,
                    }))
        strategy = (
            env['product.removal'].search([
                ('method', '=', 'fefo')], limit=1)
            if 'product.removal' in env else False)
        if strategy:
            for key, location in locations.items():
                if key.endswith(('_chilled', '_frozen', '_dry')):
                    location.removal_strategy_id = strategy
        return existing + main + north, locations

    @api.model
    def _create_vendors(self, env):
        vendors = [
            ('مورد اللحوم السعودية (تجريبي)', 'meat'),
            ('مورد الدواجن الطازجة (تجريبي)', 'poultry'),
            ('مورد خيرات الخضروات (تجريبي)', 'vegetables'),
            ('مورد المشروبات (تجريبي)', 'beverages'),
            ('مورد حلول التغليف (تجريبي)', 'packaging'),
            ('مورد النظافة الاحترافية (تجريبي)', 'cleaning'),
            ('مورد معدات المطابخ (تجريبي)', 'equipment'),
        ]
        return env['res.partner'].create([
            {
                'name': name,
                'company_type': 'company',
                'supplier_rank': 1,
                'email': '%s.vendor@example.invalid' % code,
                'phone': '+966 50 000 %04d' % (300 + index),
                'city': 'الرياض',
                'country_id': env.company.country_id.id,
                'company_id': env.company.id,
                'comment': 'مورد سعودي تجريبي — البيانات غير حقيقية.',
            }
            for index, (name, code) in enumerate(vendors)
        ])

    @api.model
    def _create_restaurant_products(self, env):
        unit = env.ref('uom.product_uom_unit')
        kg = env.ref('uom.product_uom_kgm', raise_if_not_found=False) or unit
        litre = env.ref('uom.product_uom_litre', raise_if_not_found=False) or unit
        categories = {}
        for key, name in (
                ('raw', 'مواد خام للمطعم (تجريبي)'),
                ('semi', 'منتجات نصف مصنعة (تجريبي)'),
                ('meal', 'وجبات نهائية (تجريبي)'),
                ('packaging', 'تغليف ونظافة (تجريبي)')):
            categories[key] = env['product.category'].create({'name': name})
        raw = [
            ('RAW-RICE', 'أرز بسمتي', 8.0, kg),
            ('RAW-CHICKEN', 'دجاج طازج', 18.0, kg),
            ('RAW-MEAT', 'لحم طازج', 42.0, kg),
            ('RAW-OIL', 'زيت نباتي', 9.0, litre),
            ('RAW-TOMATO', 'طماطم', 5.0, kg),
            ('RAW-ONION', 'بصل', 4.0, kg),
            ('RAW-POTATO', 'بطاطس', 5.5, kg),
            ('RAW-BREAD', 'خبز برجر', 1.2, unit),
            ('RAW-CHEESE', 'جبن شرائح', 1.0, unit),
            ('RAW-SPICES', 'بهارات نجد', 32.0, kg),
            ('RAW-VEG', 'خضروات مشكلة', 9.0, kg),
            ('RAW-DRINK', 'مشروب غازي', 2.2, unit),
            ('PACK-BOX', 'علبة تغليف', 1.1, unit),
            ('PACK-BAG', 'كيس توصيل', 0.65, unit),
            ('PACK-CUTLERY', 'أدوات طعام', 0.35, unit),
            ('PACK-TISSUE', 'مناديل', 0.18, unit),
            ('CLEAN-MATERIAL', 'مواد تنظيف', 12.0, litre),
        ]
        semi = [
            ('SEMI-GARLIC', 'صوص الثوم', 14.0, kg),
            ('SEMI-SPECIAL', 'صوص المطعم الخاص', 16.0, kg),
            ('SEMI-SPICE', 'خلطة البهارات', 38.0, kg),
            ('SEMI-RICE', 'الأرز المطبوخ', 10.5, kg),
            ('SEMI-CHICKEN', 'الدجاج المتبل', 22.0, kg),
            ('SEMI-MEAT', 'اللحم المتبل', 48.0, kg),
            ('SEMI-BATTER', 'الخلطة الخاصة', 15.0, kg),
            ('SEMI-POTATO', 'البطاطس المجهزة', 7.0, kg),
        ]
        finals = [
            ('MEAL-CHK-KABSA', 'كبسة دجاج', 34.0, 10.5),
            ('MEAL-MEAT-KABSA', 'كبسة لحم', 49.0, 18.0),
            ('MEAL-CHICKEN', 'وجبة دجاج', 29.0, 9.0),
            ('MEAL-FAMILY', 'وجبة عائلية', 119.0, 42.0),
            ('MEAL-CHK-BURGER', 'برجر دجاج', 22.0, 6.2),
            ('MEAL-MEAT-BURGER', 'برجر لحم', 27.0, 8.5),
            ('MEAL-FRIES', 'بطاطس مقلية', 9.0, 2.2),
            ('MEAL-DRINK', 'مشروب', 5.0, 2.2),
            ('MEAL-DESSERT', 'حلوى نجد', 14.0, 4.5),
            ('MEAL-KIDS', 'وجبة أطفال', 24.0, 7.0),
            ('MEAL-COMBO', 'عرض وجبة مجمعة', 45.0, 14.0),
            ('MEAL-APP', 'وجبة تطبيقات التوصيل', 39.0, 11.0),
        ]
        products = {}
        sale_tax = env['account.tax'].search([
            ('type_tax_use', '=', 'sale'),
            ('amount', '=', 15.0),
            ('company_id', '=', env.company.id),
        ], limit=1)
        purchase_tax = env['account.tax'].search([
            ('type_tax_use', '=', 'purchase'),
            ('amount', '=', 15.0),
            ('company_id', '=', env.company.id),
        ], limit=1)
        for code, name, cost, uom in raw:
            category = (
                categories['packaging']
                if code.startswith(('PACK-', 'CLEAN-')) else categories['raw'])
            values = {
                'name': '%s (تجريبي)' % name,
                'default_code': code,
                'type': 'consu',
                'is_storable': True,
                'sale_ok': False,
                'purchase_ok': True,
                'standard_price': cost,
                'uom_id': uom.id,
                'categ_id': category.id,
                'tracking': 'lot',
                'company_id': env.company.id,
            }
            if purchase_tax:
                values['supplier_taxes_id'] = [(6, 0, purchase_tax.ids)]
            if 'use_expiration_date' in env['product.template']._fields:
                values.update({
                    'use_expiration_date': True,
                    'expiration_time': 30,
                    'use_time': 20,
                    'removal_time': 5,
                    'alert_time': 7,
                })
            template = env['product.template'].create(values)
            products[code] = template.product_variant_id
        for code, name, cost, uom in semi:
            values = {
                'name': '%s (تجريبي)' % name,
                'default_code': code,
                'type': 'consu',
                'is_storable': True,
                'sale_ok': False,
                'purchase_ok': False,
                'standard_price': cost,
                'uom_id': uom.id,
                'categ_id': categories['semi'].id,
                'company_id': env.company.id,
            }
            template = env['product.template'].create(values)
            products[code] = template.product_variant_id
        for code, name, price, cost in finals:
            values = {
                'name': '%s (تجريبي)' % name,
                'default_code': code,
                'type': 'consu',
                'is_storable': True,
                'sale_ok': True,
                'purchase_ok': False,
                'list_price': price,
                'standard_price': cost,
                'uom_id': unit.id,
                'categ_id': categories['meal'].id,
                'company_id': env.company.id,
                'available_in_pos': True,
            }
            if sale_tax:
                values['taxes_id'] = [(6, 0, sale_tax.ids)]
            template = env['product.template'].create(values)
            products[code] = template.product_variant_id
        return products

    @api.model
    def _pos_order(self, env, session, customer, product, quantity=1.0,
                   table=None, paid=False):
        subtotal = product.lst_price * quantity
        taxes = product.taxes_id.filtered(
            lambda tax: tax.company_id == env.company)
        tax_amount = sum(
            subtotal * tax.amount / 100.0
            for tax in taxes.filtered(lambda tax: tax.amount_type == 'percent'))
        total = subtotal + tax_amount
        values = {
            'name': 'طلب نقطة بيع مطعم تجريبي',
            'session_id': session.id,
            'partner_id': customer.id,
            'amount_tax': tax_amount,
            'amount_total': total,
            'amount_paid': 0.0,
            'amount_return': 0.0,
            'lines': [(0, 0, {
                'name': product.display_name,
                'product_id': product.id,
                'qty': quantity,
                'price_unit': product.lst_price,
                'price_subtotal': subtotal,
                'price_subtotal_incl': total,
                'tax_ids': [(6, 0, taxes.ids)],
            })],
        }
        if table:
            values['table_id'] = table.id
        order = env['pos.order'].create(values)
        if paid:
            method = session.config_id.payment_method_ids[:1]
            env['pos.payment'].create({
                'pos_order_id': order.id,
                'payment_method_id': method.id,
                'amount': order.amount_total,
            })
            order._compute_amount_paid()
            if order.amount_paid < order.amount_total:
                order.write({'amount_paid': order.amount_total})
            order.action_pos_order_paid()
        return order

    @api.model
    def _create_restaurant_boms(self, env, products):
        recipes = {
            'SEMI-GARLIC': [('RAW-OIL', .15), ('RAW-SPICES', .03)],
            'SEMI-SPECIAL': [('RAW-TOMATO', .35), ('RAW-SPICES', .04)],
            'SEMI-SPICE': [('RAW-SPICES', 1.0)],
            'SEMI-RICE': [('RAW-RICE', .55), ('RAW-OIL', .05), ('RAW-ONION', .08)],
            'SEMI-CHICKEN': [('RAW-CHICKEN', 1.0), ('SEMI-SPICE', .04)],
            'SEMI-MEAT': [('RAW-MEAT', 1.0), ('SEMI-SPICE', .04)],
            'SEMI-BATTER': [('RAW-SPICES', .12), ('RAW-OIL', .08)],
            'SEMI-POTATO': [('RAW-POTATO', 1.0), ('RAW-OIL', .04)],
            'MEAL-CHK-KABSA': [
                ('SEMI-RICE', .32), ('SEMI-CHICKEN', .25),
                ('SEMI-SPECIAL', .04), ('PACK-BOX', 1),
                ('PACK-BAG', 1), ('PACK-CUTLERY', 1), ('PACK-TISSUE', 2)],
            'MEAL-MEAT-KABSA': [
                ('SEMI-RICE', .32), ('SEMI-MEAT', .22),
                ('SEMI-SPECIAL', .04), ('PACK-BOX', 1),
                ('PACK-BAG', 1), ('PACK-CUTLERY', 1)],
            'MEAL-CHICKEN': [
                ('SEMI-CHICKEN', .3), ('SEMI-POTATO', .15),
                ('SEMI-GARLIC', .03), ('PACK-BOX', 1)],
            'MEAL-CHK-BURGER': [
                ('RAW-BREAD', 1), ('SEMI-CHICKEN', .15),
                ('RAW-CHEESE', 1), ('SEMI-GARLIC', .02), ('PACK-BOX', 1)],
            'MEAL-MEAT-BURGER': [
                ('RAW-BREAD', 1), ('SEMI-MEAT', .15),
                ('RAW-CHEESE', 1), ('SEMI-SPECIAL', .02), ('PACK-BOX', 1)],
            'MEAL-FRIES': [('SEMI-POTATO', .2), ('PACK-BOX', 1)],
            'MEAL-DRINK': [('RAW-DRINK', 1)],
            'MEAL-DESSERT': [('SEMI-BATTER', .15), ('PACK-BOX', 1)],
            'MEAL-KIDS': [
                ('MEAL-CHK-BURGER', 1), ('MEAL-FRIES', 1),
                ('MEAL-DRINK', 1), ('PACK-BAG', 1)],
            'MEAL-COMBO': [
                ('MEAL-CHK-KABSA', 1), ('MEAL-FRIES', 1),
                ('MEAL-DRINK', 1)],
            'MEAL-APP': [
                ('MEAL-CHK-KABSA', 1), ('MEAL-DRINK', 1),
                ('PACK-BAG', 1), ('PACK-CUTLERY', 1)],
            'MEAL-FAMILY': [
                ('MEAL-CHK-KABSA', 2), ('MEAL-DRINK', 4),
                ('MEAL-DESSERT', 1), ('PACK-BAG', 2)],
        }
        boms = env['mrp.bom']
        for output_code, lines in recipes.items():
            output = products[output_code]
            boms |= env['mrp.bom'].create({
                'code': 'DEMO-REST-BOM-%s' % output_code,
                'product_tmpl_id': output.product_tmpl_id.id,
                'product_qty': 1.0,
                'product_uom_id': output.uom_id.id,
                'type': 'normal',
                'company_id': env.company.id,
                'bom_line_ids': [
                    (0, 0, {
                        'product_id': products[component].id,
                        'product_qty': quantity,
                        'product_uom_id': products[component].uom_id.id,
                    })
                    for component, quantity in lines
                ],
            })
        return boms

    @api.model
    def _seed_opening_stock(self, env, products, location, today):
        lots = env['stock.lot']
        for index, product in enumerate(
                product for code, product in products.items()
                if code.startswith(('RAW-', 'PACK-', 'CLEAN-'))):
            values = {
                'name': 'REST-%s-%03d' % (today.strftime('%y%m'), index + 1),
                'product_id': product.id,
                'company_id': env.company.id,
            }
            if 'expiration_date' in env['stock.lot']._fields:
                values['expiration_date'] = datetime.combine(
                    today + timedelta(days=14 + index), time(12, 0))
            lot = env['stock.lot'].create(values)
            lots |= lot
            env['stock.quant']._update_available_quantity(
                product, location, 120.0, lot_id=lot)
        return lots

    @api.model
    def _create_purchase_cycle(self, env, vendors, products, analytic):
        purchase = env['purchase.order'].create({
            'partner_id': vendors[1].id,
            'company_id': env.company.id,
            'origin': 'دورة شراء مواد خام للمطعم (تجريبي)',
            'order_line': [
                (0, 0, self._purchase_values(products[code], qty))
                for code, qty in (
                    ('RAW-CHICKEN', 80), ('RAW-RICE', 120),
                    ('RAW-OIL', 40), ('PACK-BOX', 300))
            ],
        })
        purchase.button_confirm()
        self._complete_tracked_receipts(env, purchase.picking_ids)
        purchase.action_create_invoice()
        bills = purchase.invoice_ids.filtered(lambda move: move.state == 'draft')
        if bills:
            bills.write({'invoice_date': fields.Date.context_today(self)})
            bills.action_post()
            self.env['saas.demo.seed']._register_payments(bills)
        return purchase

    @api.model
    def _complete_tracked_receipts(self, env, pickings):
        for picking in pickings.filtered(
                lambda item: item.state not in ('done', 'cancel')):
            picking.action_assign()
            for move in picking.move_ids.filtered(
                    lambda item: item.state != 'cancel'):
                lot = env['stock.lot'].create({
                    'name': 'REST-PO-%s-%s' % (picking.id, move.product_id.id),
                    'product_id': move.product_id.id,
                    'company_id': env.company.id,
                })
                move.quantity = move.product_uom_qty
                if 'picked' in move._fields:
                    move.picked = True
                move.move_line_ids.write({'lot_id': lot.id})
            result = picking.button_validate()
            if (
                    isinstance(result, dict)
                    and result.get('res_model') == 'stock.backorder.confirmation'):
                env[result['res_model']].with_context(
                    result.get('context') or {}).create(
                        {}).process_cancel_backorder()
        return True

    @api.model
    def _purchase_values(self, product, quantity):
        return {
            'product_id': product.id,
            'name': product.display_name,
            'product_qty': quantity,
            'product_uom_id': product.uom_id.id,
            'price_unit': product.standard_price,
            'date_planned': fields.Datetime.now(),
        }

    @api.model
    def _create_production_cycle(self, env, products, boms):
        productions = env['mrp.production']
        for code, quantity, done in (
                ('SEMI-RICE', 30.0, True),
                ('SEMI-CHICKEN', 20.0, True),
                ('MEAL-CHK-KABSA', 25.0, True),
                ('MEAL-FAMILY', 10.0, False)):
            product = products[code]
            bom = boms.filtered(
                lambda item, product=product:
                item.product_tmpl_id == product.product_tmpl_id)[:1]
            production = env['mrp.production'].create({
                'product_id': product.id,
                'product_qty': quantity,
                'product_uom_id': product.uom_id.id,
                'bom_id': bom.id,
                'company_id': env.company.id,
                'origin': 'دورة إنتاج مطعم متكاملة (تجريبي)',
            })
            productions |= production
            if done:
                env['saas.demo.seed.manufacturing']._complete_mo(production)
            else:
                production.action_confirm()
                production.button_plan()
                production.action_assign()
        return productions

    @api.model
    def _create_branch_replenishment(self, env, warehouses, products):
        central, main, north = warehouses
        product = products['MEAL-CHK-KABSA']
        transfers = env['stock.picking']
        for branch in (main, north):
            picking = env['stock.picking'].create({
                'picking_type_id': central.int_type_id.id,
                'location_id': central.lot_stock_id.id,
                'location_dest_id': branch.lot_stock_id.id,
                'origin': 'تغذية يومية للفروع (تجريبي)',
                'move_ids': [(0, 0, {
                    'product_id': product.id,
                    'product_uom': product.uom_id.id,
                    'product_uom_qty': 5.0,
                    'location_id': central.lot_stock_id.id,
                    'location_dest_id': branch.lot_stock_id.id,
                })],
            })
            transfers |= picking
        env['saas.demo.seed']._complete_pickings(transfers)
        orderpoints = env['stock.warehouse.orderpoint']
        for warehouse in warehouses:
            orderpoints |= env['stock.warehouse.orderpoint'].create({
                'name': 'حد إعادة طلب كبسة الدجاج — %s' % warehouse.name,
                'product_id': product.id,
                'location_id': warehouse.lot_stock_id.id,
                'warehouse_id': warehouse.id,
                'product_min_qty': 8.0,
                'product_max_qty': 30.0,
                'company_id': env.company.id,
            })
        for code in ('RAW-RICE', 'RAW-CHICKEN', 'PACK-BOX'):
            item = products[code]
            orderpoints |= env['stock.warehouse.orderpoint'].create({
                'name': 'حد إعادة طلب %s' % item.display_name,
                'product_id': item.id,
                'location_id': central.lot_stock_id.id,
                'warehouse_id': central.id,
                'product_min_qty': 25.0,
                'product_max_qty': 120.0,
                'company_id': env.company.id,
            })
        return {'transfers': transfers, 'orderpoints': orderpoints}

    @api.model
    def _create_channels(self, env, analytics):
        definitions = [
            ('صالة المطعم', 'DINE', 'dine_in', 0.0, 0.0, 'dine_in'),
            ('استلام من الفرع', 'PICKUP', 'pickup', 0.0, 0.0, 'pickup'),
            ('التوصيل الخاص', 'OWNDEL', 'own_delivery', 0.0, 2.0, 'own_delivery'),
            ('هنقرستيشن', 'HUNGER', 'aggregator', 20.0, 2.2, 'hungerstation'),
            ('جاهز', 'JAHEZ', 'aggregator', 18.0, 2.0, 'jahez'),
            ('نون فود', 'NOON', 'aggregator', 17.0, 2.0, 'noon_food'),
        ]
        channels = env['restaurant.demo.channel']
        for index, (name, code, kind, commission, gateway, analytic_key) in enumerate(
                definitions):
            partner = False
            if kind == 'aggregator':
                partner = env['res.partner'].create({
                    'name': '%s — حساب تسوية (تجريبي)' % name,
                    'company_type': 'company',
                    'customer_rank': 1,
                    'email': '%s@example.invalid' % code.lower(),
                    'company_id': env.company.id,
                })
            channels |= env['restaurant.demo.channel'].create({
                'name': '%s (تجريبي)' % name,
                'code': code,
                'sequence': (index + 1) * 10,
                'channel_type': kind,
                'commission_rate': commission,
                'payment_gateway_rate': gateway,
                'partner_id': partner.id if partner else False,
                'analytic_account_id': analytics[analytic_key].id,
                'company_id': env.company.id,
            })
        return channels

    @api.model
    def _create_restaurant_pos(self, env, warehouses, products):
        configs = env['pos.config']
        floors = env['restaurant.floor']
        tables = env['restaurant.table']
        paid_orders = env['pos.order']
        open_sessions = env['pos.session']
        for branch_index, (warehouse, branch_name) in enumerate((
                (warehouses[1], 'فرع الرياض الرئيسي'),
                (warehouses[2], 'فرع شمال الرياض'))):
            config = self._pos_config(
                env, 'نقطة بيع %s (تجريبي)' % branch_name, restaurant=True)
            config.picking_type_id = warehouse.pos_type_id
            configs |= config
            floor = env['restaurant.floor'].create({
                'name': 'صالة %s (تجريبي)' % branch_name,
                'pos_config_ids': [(6, 0, config.ids)],
            })
            floors |= floor
            branch_tables = env['restaurant.table'].create([
                {
                    'table_number': branch_index * 10 + number,
                    'identifier': 'REST-%s-T%s' % (branch_index + 1, number),
                    'shape': 'square' if number % 2 else 'round',
                    'seats': 4,
                    'floor_id': floor.id,
                }
                for number in range(1, 7)
            ])
            tables |= branch_tables
            session = env['pos.session'].create({
                'config_id': config.id,
                'user_id': env.user.id,
            })
            session.action_pos_session_open()
            if session.state == 'opening_control':
                session.set_opening_control(500.0, 'عهدة افتتاحية تجريبية')
            paid_orders |= self._pos_order(
                env, session, env.company.partner_id,
                products['MEAL-CHK-KABSA'], quantity=2,
                table=branch_tables[0], paid=True)
            self._pos_order(
                env, session, env.company.partner_id,
                products['MEAL-FAMILY'], quantity=1,
                table=branch_tables[1], paid=False)
            open_sessions |= session
        return {
            'restaurant_pos_configurations': len(configs),
            'restaurant_floors': len(floors),
            'restaurant_tables': len(tables),
            'open_restaurant_sessions': len(open_sessions),
            'paid_table_orders': len(paid_orders),
        }

    @api.model
    def _create_restaurant_people(self, env, today):
        departments = {}
        for key, name in (
                ('operations', 'العمليات والفروع'),
                ('kitchen', 'المطبخ'),
                ('finance', 'المالية'),
                ('hr', 'الموارد البشرية'),
                ('purchase', 'المشتريات والمخزون'),
                ('delivery', 'التوصيل'),
                ('maintenance', 'الصيانة'),
                ('marketing', 'التسويق وخدمة العملاء')):
            departments[key] = env['hr.department'].create({
                'name': '%s (تجريبي)' % name,
                'company_id': env.company.id,
            })
        definitions = [
            ('سلمان العتيبي', 'مدير المطعم', 'operations'),
            ('نورة القحطاني', 'مدير فرع الرياض', 'operations'),
            ('محمد الحربي', 'مشرف الوردية', 'operations'),
            ('ريم الدوسري', 'كاشير', 'operations'),
            ('أحمد علي', 'شيف رئيسي', 'kitchen'),
            ('خالد حسن', 'طباخ', 'kitchen'),
            ('فهد المطيري', 'مسؤول المخزون', 'purchase'),
            ('سارة الشهري', 'مسؤول المشتريات', 'purchase'),
            ('هدى الغامدي', 'محاسب', 'finance'),
            ('عمر يوسف', 'مندوب توصيل', 'delivery'),
            ('ليان أحمد', 'مسؤول الموارد البشرية', 'hr'),
            ('تركي ناصر', 'فني صيانة', 'maintenance'),
        ]
        employees = env['hr.employee']
        for index, (name, job, department) in enumerate(definitions):
            employee = env['hr.employee'].create({
                'name': '%s (تجريبي)' % name,
                'job_title': job,
                'department_id': departments[department].id,
                'company_id': env.company.id,
                'work_email': 'employee%02d@example.invalid' % (index + 1),
                'work_phone': '+966 50 100 %04d' % (index + 1),
            })
            employees |= employee
            if index < 6:
                for day_offset in range(1, 8):
                    check_in = datetime.combine(
                        today - timedelta(days=day_offset), time(8, 0))
                    if index == 2 and day_offset == 2:
                        check_in += timedelta(minutes=25)
                    env['hr.attendance'].create({
                        'employee_id': employee.id,
                        'check_in': check_in,
                        'check_out': check_in + timedelta(hours=8),
                    })
        return employees

    @api.model
    def _create_fleet(self, env):
        model = env['fleet.vehicle.model'].search([], limit=1)
        if not model:
            brand = env['fleet.vehicle.model.brand'].create({
                'name': 'مركبات توصيل تجريبية'})
            model = env['fleet.vehicle.model'].create({
                'name': 'دراجة توصيل', 'brand_id': brand.id})
        return env['fleet.vehicle'].create([
            {
                'license_plate': 'ديمو 1001',
                'model_id': model.id,
                'company_id': env.company.id,
            },
            {
                'license_plate': 'ديمو 1002',
                'model_id': model.id,
                'company_id': env.company.id,
            },
        ])

    @api.model
    def _create_month_orders(
            self, env, channels, analytics, products, employees, fleet, today):
        meals = [
            products['MEAL-CHK-KABSA'], products['MEAL-MEAT-KABSA'],
            products['MEAL-CHK-BURGER'], products['MEAL-FAMILY'],
            products['MEAL-APP'], products['MEAL-COMBO']]
        branches = [analytics['riyadh_main'], analytics['riyadh_north']]
        driver = employees.filtered(
            lambda employee: employee.job_title == 'مندوب توصيل')[:1]
        orders = env['restaurant.demo.order']
        for day_offset in range(30):
            order_day = today - timedelta(days=day_offset)
            for sequence, channel in enumerate(channels):
                product = meals[(day_offset + sequence) % len(meals)]
                quantity = 1 + ((day_offset + sequence) % 3)
                food_amount = product.lst_price * quantity
                discount = 5.0 if (day_offset + sequence) % 9 == 0 else 0.0
                state = 'delivered'
                if (day_offset + sequence) % 37 == 0:
                    state = 'cancelled'
                elif (day_offset + sequence) % 41 == 0:
                    state = 'refunded'
                values = {
                    'name': 'طلب %s — %s' % (
                        channel.code, order_day.strftime('%Y%m%d')),
                    'external_reference': 'DEMO-%s-%s-%02d' % (
                        channel.code, order_day.strftime('%Y%m%d'), sequence),
                    'order_datetime': datetime.combine(
                        order_day, time(12 + sequence % 8, sequence * 7 % 60)),
                    'channel_id': channel.id,
                    'partner_id': (
                        channel.partner_id.id or env.company.partner_id.id),
                    'product_id': product.id,
                    'quantity': quantity,
                    'branch_id': branches[(day_offset + sequence) % 2].id,
                    'food_amount': food_amount,
                    'vat_amount': food_amount * .15,
                    'delivery_fee': (
                        8.0 if channel.channel_type == 'own_delivery' else 0.0),
                    'discount_amount': discount,
                    'platform_discount_share': (
                        discount * .5
                        if channel.channel_type == 'aggregator' else 0.0),
                    'cost_amount': product.standard_price * quantity,
                    'preparation_minutes': 14 + (day_offset + sequence) % 13,
                    'delivery_minutes': (
                        24 + (day_offset + sequence) % 21
                        if channel.channel_type in ('aggregator', 'own_delivery')
                        else 0),
                    'state': state,
                    'company_id': env.company.id,
                }
                if channel.channel_type == 'own_delivery':
                    values.update({
                        'driver_id': driver.id,
                        'vehicle_id': fleet[(day_offset + sequence) % len(fleet)].id,
                    })
                orders |= env['restaurant.demo.order'].create(values)
        return orders

    @api.model
    def _create_settlements(self, env, channels, orders, today):
        settlements = env['restaurant.demo.settlement']
        for index, channel in enumerate(
                channels.filtered(lambda item: item.channel_type == 'aggregator')):
            channel_orders = orders.filtered(
                lambda order, channel=channel:
                order.channel_id == channel and order.state == 'delivered')
            gross = sum(
                order.food_amount + order.vat_amount for order in channel_orders)
            commission = sum(order.commission_amount for order in channel_orders)
            gateway = sum(order.gateway_fee for order in channel_orders)
            discounts = sum(
                order.discount_amount - order.platform_discount_share
                for order in channel_orders)
            expected = gross - commission - gateway - discounts
            received = expected if index != 1 else expected - 12.50
            settlements |= env['restaurant.demo.settlement'].create({
                'name': 'تسوية %s — آخر 30 يومًا (تجريبي)' % channel.name,
                'channel_id': channel.id,
                'date_from': today - timedelta(days=29),
                'date_to': today,
                'order_count': len(channel_orders),
                'gross_amount': gross,
                'commission_amount': commission,
                'gateway_fees': gateway,
                'discounts': discounts,
                'received_amount': received,
                'state': 'matched' if index != 1 else 'difference',
                'note': (
                    'تسوية تجريبية؛ الفارق المتعمد يوضح شاشة مطابقة '
                    'كشف منصة التوصيل.'),
                'company_id': env.company.id,
            })
        return settlements

    @api.model
    def _create_waste(self, env, products, analytics, today):
        definitions = [
            ('انتهاء صلاحية دفعة خضروات', 'RAW-VEG', 3.0, 'expired'),
            ('سوء تخزين دجاج', 'RAW-CHICKEN', 2.0, 'storage'),
            ('خطأ تحضير أرز', 'SEMI-RICE', 4.0, 'preparation'),
            ('إلغاء طلب كبسة', 'MEAL-CHK-KABSA', 2.0, 'cancelled'),
            ('مرتجع عميل', 'MEAL-MEAT-BURGER', 1.0, 'return'),
            ('تلف أثناء النقل', 'RAW-DRINK', 8.0, 'transport'),
            ('زيادة إنتاج', 'SEMI-POTATO', 5.0, 'overproduction'),
            ('وجبات موظفين', 'MEAL-CHICKEN', 4.0, 'employee_meal'),
            ('عينات تسويق', 'MEAL-DESSERT', 6.0, 'sample'),
        ]
        waste = env['restaurant.demo.waste']
        for index, (name, code, quantity, reason) in enumerate(definitions):
            product = products[code]
            waste |= env['restaurant.demo.waste'].create({
                'name': '%s (تجريبي)' % name,
                'date': today - timedelta(days=index * 2),
                'product_id': product.id,
                'quantity': quantity,
                'unit_cost': product.standard_price,
                'reason': reason,
                'branch_id': (
                    analytics['riyadh_main'].id
                    if index % 2 else analytics['riyadh_north'].id),
                'company_id': env.company.id,
            })
        return waste

    @api.model
    def _create_checklists(self, env, analytics, employees, today):
        manager = employees.filtered(
            lambda item: item.job_title == 'مدير فرع الرياض')[:1]
        common = (
            'فحص النظافة\nقياس درجات التبريد والتجميد\n'
            'مطابقة عهدة الصندوق\nتأكيد جاهزية المطبخ والطابعات\n'
            'فحص تواريخ الصلاحية والمواد الحرجة')
        records = env['restaurant.demo.checklist']
        for index, checklist_type in enumerate(
                ('opening', 'closing', 'food_safety', 'cleaning')):
            records |= env['restaurant.demo.checklist'].create({
                'name': 'قائمة %s اليومية (تجريبي)' % checklist_type,
                'date': today,
                'checklist_type': checklist_type,
                'branch_id': analytics['riyadh_main'].id,
                'responsible_id': manager.id,
                'items': common,
                'state': 'done' if index < 2 else 'in_progress',
                'company_id': env.company.id,
            })
        return records

    @api.model
    def _create_quality_and_maintenance(
            self, env, products, productions, today):
        quality_team = env['quality.alert.team'].search([], limit=1)
        test_type = env['quality.point.test_type'].search([], limit=1)
        receipt_type = env['stock.picking.type'].search([
            ('code', '=', 'incoming'),
            ('company_id', 'in', (False, env.company.id)),
        ], limit=1)
        points = env['quality.point'].create([
            {
                'name': 'فحص حرارة الدجاج المبرد عند الاستلام (تجريبي)',
                'team_id': quality_team.id,
                'test_type_id': test_type.id,
                'company_id': env.company.id,
                'product_ids': [(6, 0, products['RAW-CHICKEN'].ids)],
                'picking_type_ids': [(6, 0, receipt_type.ids)],
                'note': 'الحد التجريبي المقبول من 0 إلى 5 درجات مئوية.',
            },
            {
                'name': 'فحص صلاحية اللحوم عند الاستلام (تجريبي)',
                'team_id': quality_team.id,
                'test_type_id': test_type.id,
                'company_id': env.company.id,
                'product_ids': [(6, 0, products['RAW-MEAT'].ids)],
                'picking_type_ids': [(6, 0, receipt_type.ids)],
                'note': 'فحص العبوة والدفعة وتاريخ الانتهاء.',
            },
        ])
        category = env['maintenance.equipment.category'].create({
            'name': 'معدات مطاعم (تجريبي)'})
        team = env['maintenance.team'].search([], limit=1)
        equipment = env['maintenance.equipment'].create([
            {
                'name': '%s (تجريبي)' % name,
                'category_id': category.id,
                'maintenance_team_id': team.id,
                'company_id': env.company.id,
                'serial_no': 'REST-EQ-%03d' % (index + 1),
            }
            for index, name in enumerate([
                'فرن المطبخ المركزي', 'ثلاجة المواد الطازجة',
                'فريزر الفرع الرئيسي', 'شفاط المطبخ', 'قلاية البطاطس',
                'شواية البرجر', 'ماكينة التغليف', 'شاشة نقطة البيع',
                'طابعة المطبخ'])
        ])
        requests = env['maintenance.request'].create([
            {
                'name': 'صيانة وقائية للفرن (تجريبي)',
                'equipment_id': equipment[0].id,
                'maintenance_type': 'preventive',
                'maintenance_team_id': team.id,
                'company_id': env.company.id,
                'schedule_date': fields.Datetime.now() + timedelta(days=5),
                'duration': 2.0,
            },
            {
                'name': 'معالجة ضعف تبريد الثلاجة (تجريبي)',
                'equipment_id': equipment[1].id,
                'maintenance_type': 'corrective',
                'maintenance_team_id': team.id,
                'company_id': env.company.id,
                'schedule_date': fields.Datetime.now(),
                'duration': 1.5,
            },
        ])
        return {
            'quality_points': len(points),
            'equipment': len(equipment),
            'maintenance_requests': len(requests),
        }

    @api.model
    def _create_approvals(self, env):
        categories = env['approval.category']
        for name in (
                'طلب شراء مرتفع القيمة', 'خصم كبير على طلب',
                'إلغاء طلب بعد الدفع', 'هدر يتجاوز الحد',
                'مصروف فرع', 'صيانة مرتفعة التكلفة',
                'تعديل سعر منتج', 'تحويل مخزون بين الفروع'):
            categories |= env['approval.category'].create({
                'name': '%s (تجريبي)' % name,
                'company_id': env.company.id,
            })
        return categories

    @api.model
    def _create_customer_service(self, env):
        customer = env['res.partner'].create({
            'name': 'عميل ولاء للمطعم (تجريبي)',
            'customer_rank': 1,
            'phone': '+966 50 000 9090',
            'email': 'loyal.customer@example.invalid',
            'company_id': env.company.id,
        })
        return env['helpdesk.ticket'].create([
            {
                'name': 'شكوى تأخر طلب توصيل (تجريبي)',
                'partner_id': customer.id,
                'company_id': env.company.id,
                'description': 'بلاغ تجريبي لقياس وقت معالجة شكاوى التوصيل.',
            },
            {
                'name': 'ملاحظة جودة وجبة (تجريبي)',
                'partner_id': customer.id,
                'company_id': env.company.id,
                'description': 'بلاغ تجريبي مع تعويض العميل بقسيمة.',
            },
        ])

    @api.model
    def _create_restaurant_analytic_entries(
            self, env, analytics, orders, waste, today):
        values = []
        for order in orders.filtered(lambda item: item.state == 'delivered'):
            values.append({
                'name': 'هامش طلب %s' % order.external_reference,
                'date': order.order_datetime.date(),
                'amount': order.margin_amount,
                'account_id': order.branch_id.id,
                'company_id': env.company.id,
            })
            values.append({
                'name': 'عمولة قناة %s' % order.external_reference,
                'date': order.order_datetime.date(),
                'amount': -order.commission_amount,
                'account_id': order.channel_id.analytic_account_id.id,
                'company_id': env.company.id,
            })
        for item in waste:
            values.append({
                'name': 'تكلفة هدر — %s' % item.name,
                'date': item.date,
                'amount': -item.total_cost,
                'account_id': item.branch_id.id,
                'company_id': env.company.id,
            })
        if values:
            env['account.analytic.line'].create(values)
