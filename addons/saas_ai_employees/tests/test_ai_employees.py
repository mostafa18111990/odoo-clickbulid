import json

from odoo.exceptions import AccessError, ValidationError
from odoo.tests.common import TransactionCase


class TestAiEmployees(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.provider = cls.env.ref('saas_ai.provider_anthropic')
        cls.employee = cls.env['saas.ai.employee'].create({
            'name': 'Approval Sales Agent',
            'role': 'sales',
            'provider_id': cls.provider.id,
            'system_prompt': 'Be accurate and escalate commitments.',
            'autonomy': 'approval',
        })

    def test_sensitive_action_requires_approval(self):
        task = self.env['saas.ai.task'].create({
            'name': 'Prepare quote',
            'employee_id': self.employee.id,
            'task_type': 'create_quote',
            'input_text': 'Prepare a quote draft.',
        })
        self.assertTrue(task._approval_required())

    def test_non_sensitive_action_can_finish_automatically(self):
        task = self.env['saas.ai.task'].create({
            'name': 'Qualify lead',
            'employee_id': self.employee.id,
            'task_type': 'qualify_lead',
            'input_text': 'Qualify the supplied lead.',
            'context_json': json.dumps({'company_size': 20}),
        })
        self.assertFalse(task._approval_required())
        payload = json.loads(task._build_prompt())
        self.assertEqual(payload['task_type'], 'qualify_lead')
        self.assertEqual(payload['context']['company_size'], 20)

    def test_credentials_are_environment_references(self):
        channel = self.env['saas.ai.social.channel'].create({
            'name': 'Company Facebook',
            'platform': 'facebook',
            'account_name': 'ClickBuild',
            'account_id': 'page-reference',
            'credential_env_var': 'META_ACCESS_TOKEN',
        })
        self.assertEqual(channel.credential_env_var, 'META_ACCESS_TOKEN')
        with self.assertRaises(ValidationError):
            channel.credential_env_var = 'plaintext-token-value'

    def test_context_must_be_json_object(self):
        with self.assertRaises(ValidationError):
            self.env['saas.ai.task'].create({
                'name': 'Invalid context',
                'employee_id': self.employee.id,
                'task_type': 'analytics',
                'input_text': 'Summarize.',
                'context_json': '[]',
            })

    def test_user_cannot_bypass_task_transitions(self):
        user = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'AI Task User',
            'login': 'ai-task-user@example.invalid',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id])],
        })
        task = self.env['saas.ai.task'].with_user(user).create({
            'name': 'User task',
            'employee_id': self.employee.id,
            'task_type': 'draft_post',
            'input_text': 'Draft a post.',
        })
        task.with_user(user).action_queue()
        self.assertEqual(task.state, 'pending')
        with self.assertRaises(AccessError):
            task.with_user(user).write({'state': 'done'})
