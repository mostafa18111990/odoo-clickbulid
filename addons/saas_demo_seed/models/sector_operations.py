import base64
from datetime import timedelta

from odoo import api, fields, models

from .seed_service import DEMO_CONTEXT


SECTOR_PACK_VERSION = '1.0'


class SaasDemoSeedSectorOperations(models.AbstractModel):
    _name = 'saas.demo.seed.sector.operations'
    _description = 'Enterprise Demo Sector Operations'

    @api.model
    def seed(self, sector):
        method = getattr(self, '_seed_%s' % sector.replace('-', '_'), None)
        if not method:
            return {'status': 'not_applicable', 'version': SECTOR_PACK_VERSION}
        params = self.env['ir.config_parameter'].sudo()
        key = 'saas.demo.seed.sector.%s.version' % sector
        if params.get_param(key) == SECTOR_PACK_VERSION:
            return {
                'status': 'already_seeded',
                'version': SECTOR_PACK_VERSION,
                'sector': sector,
            }
        result = method(self.env(context=dict(self.env.context, **DEMO_CONTEXT)))
        result.update({
            'status': 'seeded',
            'version': SECTOR_PACK_VERSION,
            'sector': sector,
        })
        params.set_param(key, SECTOR_PACK_VERSION)
        return result

    @api.model
    def _base_records(self, env):
        customer = env['res.partner'].search([
            ('email', '=', 'customer.demo@example.invalid')], limit=1)
        vendor = env['res.partner'].search([
            ('email', '=', 'vendor.demo@example.invalid')], limit=1)
        products = env['product.product'].search([
            ('is_storable', '=', True),
            ('company_id', 'in', (False, env.company.id)),
        ], limit=2)
        return customer, vendor, products

    @api.model
    def _project_cycle(self, env, name, customer, task_names):
        project = env['project.project'].create({
            'name': name,
            'partner_id': customer.id,
            'company_id': env.company.id,
        })
        milestones = env['project.milestone']
        if 'project.milestone' in env:
            milestones = env['project.milestone'].create([
                {'name': 'اعتماد النطاق (تجريبي)', 'project_id': project.id},
                {'name': 'إنجاز 50% (تجريبي)', 'project_id': project.id},
                {'name': 'الاستلام النهائي (تجريبي)', 'project_id': project.id},
            ])
        tasks = env['project.task'].create([
            {
                'name': task_name,
                'project_id': project.id,
                'partner_id': customer.id,
                'allocated_hours': 24.0 + index * 16.0,
            }
            for index, task_name in enumerate(task_names)
        ])
        if tasks:
            tasks[0].write({'state': '1_done'})
        if len(tasks) > 1:
            tasks[1].write({'state': '01_in_progress'})
        return project, milestones, tasks

    @api.model
    def _timesheets(self, env, project, tasks, labels):
        if 'account.analytic.line' not in env or 'employee_id' not in env['account.analytic.line']._fields:
            return env['account.analytic.line']
        employee = env['hr.employee'].search([
            ('company_id', '=', env.company.id)], limit=1)
        if not employee:
            employee = env['hr.employee'].create({
                'name': 'استشاري تنفيذ (تجريبي)',
                'company_id': env.company.id,
            })
        values = []
        for index, label in enumerate(labels):
            values.append({
                'name': label,
                'date': fields.Date.context_today(self) - timedelta(days=index),
                'amount': 0.0,
                'unit_amount': 4.0 + index,
                'employee_id': employee.id,
                'project_id': project.id,
                'task_id': tasks[min(index, len(tasks) - 1)].id,
                'company_id': env.company.id,
            })
        return env['account.analytic.line'].create(values)

    @api.model
    def _demo_employee(self, env):
        employee = env['hr.employee'].search([
            ('name', '=', 'استشاري تنفيذ (تجريبي)'),
            ('company_id', '=', env.company.id),
        ], limit=1)
        if not employee:
            employee = env['hr.employee'].create({
                'name': 'استشاري تنفيذ (تجريبي)',
                'company_id': env.company.id,
            })
        return employee

    @api.model
    def _seed_construction(self, env):
        customer, vendor, products = self._base_records(env)
        project, milestones, tasks = self._project_cycle(
            env,
            'مشروع إنشاء مبنى إداري — الرياض (تجريبي)',
            customer,
            [
                'التصميم والمخططات التنفيذية (تجريبي)',
                'أعمال الحفر والأساسات (تجريبي)',
                'الهيكل الخرساني (تجريبي)',
                'الأعمال الكهروميكانيكية (تجريبي)',
                'التشطيبات والفحص والتسليم (تجريبي)',
            ],
        )
        costs = env['account.analytic.line']
        if 'account.analytic.line' in env:
            analytic_account = project.account_id
            if not analytic_account:
                analytic_plan = env['account.analytic.plan'].search([], limit=1)
                analytic_account = env['account.analytic.account'].create({
                    'name': 'تكاليف مشروع المبنى الإداري (تجريبي)',
                    'plan_id': analytic_plan.id,
                    'company_id': env.company.id,
                    'partner_id': customer.id,
                })
                project.account_id = analytic_account
            cost_values = [
                {
                    'name': 'تكلفة مقاول باطن — أعمال الأساسات (تجريبي)',
                    'date': fields.Date.context_today(self),
                    'amount': -38000.0,
                    'account_id': analytic_account.id,
                    'company_id': env.company.id,
                },
                {
                    'name': 'تكلفة مواد موقع — خرسانة وحديد (تجريبي)',
                    'date': fields.Date.context_today(self),
                    'amount': -24500.0,
                    'account_id': analytic_account.id,
                    'company_id': env.company.id,
                },
            ]
            if (
                'employee_id' in env['account.analytic.line']._fields
                and 'hr.employee' in env
            ):
                employee = self._demo_employee(env)
                for values in cost_values:
                    values['employee_id'] = employee.id
                    if 'project_id' in env['account.analytic.line']._fields:
                        values['project_id'] = project.id
            costs = env['account.analytic.line'].create(cost_values)
        return {
            'projects': len(project),
            'milestones': len(milestones),
            'project_tasks': len(tasks),
            'project_cost_entries': len(costs),
            'workflow': 'contract-planning-procurement-execution-inspection-handover',
        }

    @api.model
    def _seed_trading_distribution(self, env):
        customer, vendor, products = self._base_records(env)
        company = env.company
        warehouse = env['stock.warehouse'].create({
            'name': 'مستودع فرع جدة (تجريبي)',
            'code': 'DMJED',
            'company_id': company.id,
            'partner_id': company.partner_id.id,
        })
        orderpoints = env['stock.warehouse.orderpoint']
        if products:
            orderpoints = env['stock.warehouse.orderpoint'].create([
                {
                    'name': 'إعادة طلب تلقائية — %s' % product.display_name,
                    'product_id': product.id,
                    'location_id': warehouse.lot_stock_id.id,
                    'warehouse_id': warehouse.id,
                    'product_min_qty': 10.0,
                    'product_max_qty': 60.0,
                    'company_id': company.id,
                }
                for product in products
            ])
        main = env['stock.warehouse'].search([
            ('company_id', '=', company.id),
            ('id', '!=', warehouse.id),
        ], limit=1)
        transfer = env['stock.picking']
        if main and products:
            transfer = env['stock.picking'].create({
                'partner_id': customer.id,
                'picking_type_id': main.int_type_id.id,
                'location_id': main.lot_stock_id.id,
                'location_dest_id': warehouse.lot_stock_id.id,
                'origin': 'تغذية فرع جدة (تجريبي)',
                'move_ids': [
                    (0, 0, {
                        'product_id': product.id,
                        'product_uom': product.uom_id.id,
                        'product_uom_qty': 5.0,
                        'location_id': main.lot_stock_id.id,
                        'location_dest_id': warehouse.lot_stock_id.id,
                    })
                    for product in products
                ],
            })
            env['saas.demo.seed']._complete_pickings(transfer)
        return {
            'branch_warehouses': len(warehouse),
            'reordering_rules': len(orderpoints),
            'internal_transfers': len(transfer),
            'workflow': 'purchase-receipt-replenishment-transfer-sale-delivery-collection',
        }

    @api.model
    def _pos_config(self, env, name, restaurant=False):
        warehouse = env['stock.warehouse'].search([
            ('company_id', '=', env.company.id)], limit=1)
        values = {
            'name': name,
            'company_id': env.company.id,
            'picking_type_id': warehouse.pos_type_id.id,
        }
        if restaurant and 'module_pos_restaurant' in env['pos.config']._fields:
            values['module_pos_restaurant'] = True
        return env['pos.config'].create(values)

    @api.model
    def _pos_order(self, env, session, customer, product, quantity=1.0,
                   table=None, paid=False):
        subtotal = product.lst_price * quantity
        values = {
            'name': 'طلب نقطة بيع تجريبي',
            'session_id': session.id,
            'partner_id': customer.id,
            'amount_tax': 0.0,
            'amount_total': subtotal,
            'amount_paid': 0.0,
            'amount_return': 0.0,
            'lines': [(0, 0, {
                'name': product.display_name,
                'product_id': product.id,
                'qty': quantity,
                'price_unit': product.lst_price,
                'price_subtotal': subtotal,
                'price_subtotal_incl': subtotal,
                'tax_ids': [(6, 0, [])],
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
    def _seed_retail(self, env):
        customer, vendor, products = self._base_records(env)
        config = self._pos_config(env, 'نقطة بيع فرع الرياض (تجريبي)')
        closed_session = env['pos.session'].create({
            'config_id': config.id,
            'user_id': env.user.id,
        })
        closed_session.action_pos_session_open()
        if closed_session.state == 'opening_control':
            closed_session.set_opening_control(
                0.0, 'رصيد افتتاحي تجريبي')
        paid_order = self._pos_order(
            env, closed_session, customer, products[0], quantity=2.0, paid=True)
        closed_session.action_pos_session_closing_control()
        if closed_session.state != 'closed':
            closed_session.action_pos_session_close()
        open_session = env['pos.session'].create({
            'config_id': config.id,
            'user_id': env.user.id,
        })
        open_session.action_pos_session_open()
        if open_session.state == 'opening_control':
            open_session.set_opening_control(
                0.0, 'رصيد افتتاحي تجريبي')
        draft_order = self._pos_order(
            env, open_session, customer, products[-1], quantity=1.0)
        return {
            'pos_configurations': len(config),
            'closed_pos_sessions': len(closed_session.filtered(
                lambda record: record.state == 'closed')),
            'open_pos_sessions': len(open_session),
            'paid_pos_orders': len(paid_order.filtered(
                lambda record: record.state in ('paid', 'done'))),
            'draft_pos_orders': len(draft_order),
            'retail_products': len(products),
            'workflow': 'branch-replenishment-pos-sale-payment-closing-accounting',
        }

    @api.model
    def _seed_restaurants_cafes(self, env):
        customer, vendor, products = self._base_records(env)
        config = self._pos_config(env, 'نقطة بيع مطعم الرياض (تجريبي)', restaurant=True)
        floor = env['restaurant.floor'].create({
            'name': 'الصالة الرئيسية (تجريبي)',
            'pos_config_ids': [(6, 0, config.ids)],
        })
        tables = env['restaurant.table'].create([
            {
                'table_number': number,
                'identifier': 'DEMO-T%s' % number,
                'shape': 'square' if number % 2 else 'round',
                'seats': 4 if 'seats' in env['restaurant.table']._fields else False,
                'floor_id': floor.id,
            }
            for number in range(1, 7)
        ])
        session = env['pos.session'].create({
            'config_id': config.id,
            'user_id': env.user.id,
        })
        session.action_pos_session_open()
        if session.state == 'opening_control':
            session.set_opening_control(
                0.0, 'رصيد افتتاحي تجريبي')
        paid_order = self._pos_order(
            env, session, customer, products[0], quantity=2.0,
            table=tables[0], paid=True)
        kitchen_order = self._pos_order(
            env, session, customer, products[-1], quantity=1.0,
            table=tables[1])
        return {
            'restaurant_pos_configurations': len(config),
            'restaurant_floors': len(floor),
            'restaurant_tables': len(tables),
            'open_restaurant_sessions': len(session),
            'paid_table_orders': len(paid_order.filtered(
                lambda record: record.state in ('paid', 'done'))),
            'kitchen_orders_in_progress': len(kitchen_order),
            'workflow': 'ingredients-purchase-table-order-kitchen-payment-closing',
        }

    @api.model
    def _seed_professional_services(self, env):
        customer, vendor, products = self._base_records(env)
        project, milestones, tasks = self._project_cycle(
            env,
            'مشروع التحول الرقمي للعميل (تجريبي)',
            customer,
            [
                'ورش تحليل المتطلبات (تجريبي)',
                'تصميم الحل واعتماده (تجريبي)',
                'الإعداد والترحيل (تجريبي)',
                'اختبار القبول والتدريب (تجريبي)',
            ],
        )
        timesheets = self._timesheets(
            env, project, tasks,
            ['تحليل العمليات', 'تصميم الحل', 'تهيئة النظام', 'جلسة تدريب'])
        tickets = env['helpdesk.ticket'].create([
            {
                'name': 'طلب دعم — صلاحيات تقرير الإدارة (تجريبي)',
                'partner_id': customer.id,
                'company_id': env.company.id,
                'description': 'بلاغ دعم تجريبي مفتوح لشرح دورة ما بعد الإطلاق.',
            },
            {
                'name': 'طلب تطوير — إضافة مؤشر أداء (تجريبي)',
                'partner_id': customer.id,
                'company_id': env.company.id,
                'description': 'طلب تحسين تجريبي ضمن عقد الدعم.',
            },
        ])
        return {
            'delivery_projects': len(project),
            'milestones': len(milestones),
            'delivery_tasks': len(tasks),
            'timesheet_entries': len(timesheets),
            'support_tickets': len(tickets),
            'workflow': 'opportunity-proposal-project-timesheets-invoice-support',
        }

    @api.model
    def _seed_real_estate(self, env):
        customer, vendor, products = self._base_records(env)
        properties = env['product.template'].create([
            {
                'name': 'وحدة A-101 — مجمع الأعمال (تجريبي)',
                'type': 'service',
                'sale_ok': True,
                'purchase_ok': False,
                'list_price': 780000.0,
                'company_id': env.company.id,
            },
            {
                'name': 'وحدة B-205 — مجمع الأعمال (تجريبي)',
                'type': 'service',
                'sale_ok': True,
                'purchase_ok': False,
                'list_price': 925000.0,
                'company_id': env.company.id,
            },
        ])
        folder = env['documents.document'].create({
            'name': 'ملفات الوحدات العقارية (تجريبي)',
            'type': 'folder',
            'company_id': env.company.id,
        })
        documents = env['documents.document'].create([
            {
                'name': 'مخطط الوحدة A-101.txt',
                'type': 'binary',
                'folder_id': folder.id,
                'datas': base64.b64encode(
                    'ملف تجريبي آمن لمخطط الوحدة A-101'.encode('utf-8')),
                'mimetype': 'text/plain',
                'company_id': env.company.id,
            },
            {
                'name': 'نموذج عرض الوحدة B-205.txt',
                'type': 'binary',
                'folder_id': folder.id,
                'datas': base64.b64encode(
                    'ملف تجريبي آمن لعرض الوحدة B-205'.encode('utf-8')),
                'mimetype': 'text/plain',
                'company_id': env.company.id,
            },
        ])
        category = env['maintenance.equipment.category'].create({
            'name': 'وحدات عقارية مؤجرة (تجريبي)',
        })
        equipment = env['maintenance.equipment'].create({
            'name': 'وحدة A-101 — أصل مؤجر (تجريبي)',
            'equipment_assign_to': 'other',
            'category_id': category.id,
            'company_id': env.company.id,
        })
        request = env['maintenance.request'].create({
            'name': 'بلاغ تكييف — وحدة A-101 (تجريبي)',
            'equipment_id': equipment.id,
            'maintenance_type': 'corrective',
            'company_id': env.company.id,
        })
        return {
            'property_units': len(properties),
            'document_folders': len(folder),
            'property_documents': len(documents),
            'property_assets': len(equipment),
            'maintenance_requests': len(request),
            'workflow': 'lead-unit-file-offer-contract-collection-maintenance',
        }

    @api.model
    def _seed_ecommerce(self, env):
        customer, vendor, products = self._base_records(env)
        published = products
        for product in published:
            template = product.product_tmpl_id
            if 'is_published' in template._fields:
                template.is_published = True
            elif 'website_published' in template._fields:
                template.website_published = True
        orders = env['sale.order'].create([
            {
                'partner_id': customer.id,
                'company_id': env.company.id,
                'client_order_ref': 'سلة متجر قيد المراجعة (تجريبي)',
                'order_line': [(0, 0, {
                    'product_id': products[0].id,
                    'name': products[0].display_name,
                    'product_uom_id': products[0].uom_id.id,
                    'product_uom_qty': 1.0,
                    'price_unit': products[0].list_price,
                })],
            },
            {
                'partner_id': customer.id,
                'company_id': env.company.id,
                'client_order_ref': 'طلب متجر جاهز للشحن (تجريبي)',
                'order_line': [(0, 0, {
                    'product_id': products[-1].id,
                    'name': products[-1].display_name,
                    'product_uom_id': products[-1].uom_id.id,
                    'product_uom_qty': 2.0,
                    'price_unit': products[-1].list_price,
                })],
            },
        ])
        orders[1].action_confirm()
        return {
            'published_products': len(published),
            'online_cart_orders': 1,
            'online_confirmed_orders': 1,
            'workflow': 'catalog-cart-checkout-payment-sandbox-fulfillment-followup',
        }

    @api.model
    def _seed_field_services(self, env):
        customer, vendor, products = self._base_records(env)
        project = env['project.project'].create({
            'name': 'الخدمات الميدانية — الرياض (تجريبي)',
            'partner_id': customer.id,
            'company_id': env.company.id,
            'is_fsm': True,
        })
        tasks = env['project.task'].create([
            {
                'name': 'زيارة فحص دورية — جهاز التبريد (مكتملة تجريبيًا)',
                'project_id': project.id,
                'partner_id': customer.id,
                'allocated_hours': 2.0,
                'state': '1_done',
            },
            {
                'name': 'زيارة إصلاح عاجلة — المضخة الرئيسية (قيد التنفيذ تجريبيًا)',
                'project_id': project.id,
                'partner_id': customer.id,
                'allocated_hours': 4.0,
                'state': '01_in_progress',
            },
            {
                'name': 'تركيب قطعة غيار — موعد قادم (تجريبي)',
                'project_id': project.id,
                'partner_id': customer.id,
                'allocated_hours': 3.0,
            },
        ])
        category = env['maintenance.equipment.category'].create({
            'name': 'معدات عملاء بعقود صيانة (تجريبي)',
        })
        equipment = env['maintenance.equipment'].create([
            {
                'name': 'وحدة تبريد العميل CB-01 (تجريبي)',
                'equipment_assign_to': 'other',
                'category_id': category.id,
                'partner_id': customer.id,
                'company_id': env.company.id,
            },
            {
                'name': 'مضخة العميل CB-02 (تجريبي)',
                'equipment_assign_to': 'other',
                'category_id': category.id,
                'partner_id': customer.id,
                'company_id': env.company.id,
            },
        ])
        requests = env['maintenance.request'].create([
            {
                'name': 'صيانة وقائية لوحدة التبريد (تجريبي)',
                'equipment_id': equipment[0].id,
                'maintenance_type': 'preventive',
                'company_id': env.company.id,
            },
            {
                'name': 'إصلاح تسريب بالمضخة (تجريبي)',
                'equipment_id': equipment[1].id,
                'maintenance_type': 'corrective',
                'company_id': env.company.id,
            },
        ])
        ticket = env['helpdesk.ticket'].create({
            'name': 'بلاغ عميل — توقف المضخة الرئيسية (تجريبي)',
            'partner_id': customer.id,
            'company_id': env.company.id,
        })
        return {
            'fsm_projects': len(project),
            'field_visits': len(tasks),
            'customer_equipment': len(equipment),
            'maintenance_requests': len(requests),
            'service_tickets': len(ticket),
            'workflow': 'ticket-dispatch-visit-parts-signature-invoice',
        }

    @api.model
    def _seed_education(self, env):
        customer, vendor, products = self._base_records(env)
        training = env['product.template'].create({
            'name': 'برنامج إدارة المشاريع الاحترافي (تجريبي)',
            'type': 'service',
            'sale_ok': True,
            'list_price': 2400.0,
            'company_id': env.company.id,
        }).product_variant_id
        event = env['event.event'].create({
            'name': 'الدفعة التجريبية — إدارة المشاريع الاحترافية',
            'date_begin': fields.Datetime.now() + timedelta(days=10),
            'date_end': fields.Datetime.now() + timedelta(days=12),
            'date_tz': env.user.tz or 'Asia/Riyadh',
            'seats_limited': True,
            'seats_max': 30,
            'company_id': env.company.id,
        })
        ticket = env['event.event.ticket'].create({
            'name': 'مقعد البرنامج التدريبي (تجريبي)',
            'event_id': event.id,
            'product_id': training.id,
            'seats_limited': True,
            'seats_max': 30,
        })
        registrations = env['event.registration'].create([
            {
                'event_id': event.id,
                'event_ticket_id': ticket.id,
                'name': 'أحمد المتدرب (تجريبي)',
                'email': 'trainee1.demo@example.invalid',
                'phone': '+966500001111',
            },
            {
                'event_id': event.id,
                'event_ticket_id': ticket.id,
                'name': 'سارة المتدربة (تجريبي)',
                'email': 'trainee2.demo@example.invalid',
                'phone': '+966500002222',
            },
            {
                'event_id': event.id,
                'event_ticket_id': ticket.id,
                'name': 'محمد المتدرب (تجريبي)',
                'email': 'trainee3.demo@example.invalid',
                'phone': '+966500003333',
            },
        ])
        registrations[:2].action_confirm()
        registrations[:1].action_set_done()
        return {
            'training_programs': 1,
            'published_events': len(event),
            'event_tickets': len(ticket),
            'registrations': len(registrations),
            'attended_registrations': 1,
            'workflow': 'program-publishing-registration-payment-delivery-attendance-followup',
        }

    @api.model
    def _seed_startups_smes(self, env):
        customer, vendor, products = self._base_records(env)
        project, milestones, tasks = self._project_cycle(
            env,
            'خطة نمو المنشأة — 90 يومًا (تجريبي)',
            customer,
            [
                'تحديد أهداف المبيعات (تجريبي)',
                'تحسين دورة المشتريات والمخزون (تجريبي)',
                'إقفال الشهر ومراجعة السيولة (تجريبي)',
                'لوحة مؤشرات الإدارة (تجريبي)',
            ],
        )
        orderpoints = env['stock.warehouse.orderpoint']
        warehouse = env['stock.warehouse'].search([
            ('company_id', '=', env.company.id)], limit=1)
        if products and warehouse:
            orderpoints = env['stock.warehouse.orderpoint'].create([
                {
                    'name': 'حد مخزون المنشأة — %s' % product.display_name,
                    'product_id': product.id,
                    'location_id': warehouse.lot_stock_id.id,
                    'warehouse_id': warehouse.id,
                    'product_min_qty': 5.0,
                    'product_max_qty': 25.0,
                    'company_id': env.company.id,
                }
                for product in products
            ])
        return {
            'growth_projects': len(project),
            'management_milestones': len(milestones),
            'management_tasks': len(tasks),
            'reordering_rules': len(orderpoints),
            'workflow': 'lead-sale-procurement-delivery-accounting-management-dashboard',
        }
