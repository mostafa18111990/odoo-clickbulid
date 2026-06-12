from odoo import models, fields, api

CHECK_TYPES = [('txt', 'TXT Record'), ('cname', 'CNAME Record'), ('a', 'A Record'), ('ssl', 'SSL Issuance')]
CHECK_RESULTS = [('success', 'Success'), ('not_found', 'Record Not Found'),
                 ('mismatch', 'Value Mismatch'), ('error', 'Lookup Error')]


class SaasDomainVerification(models.Model):
    _name = 'saas.domain.verification'
    _description = 'Domain Verification Attempt'
    _order = 'create_date desc'
    _rec_name = 'check_type'

    domain_id = fields.Many2one('saas.domain', string='Domain', required=True, ondelete='cascade', index=True)
    check_type = fields.Selection(selection=CHECK_TYPES, string='Check Type', required=True)
    result = fields.Selection(selection=CHECK_RESULTS, string='Result', required=True)
    expected_value = fields.Char(string='Expected')
    found_value = fields.Char(string='Found')
    details = fields.Text(string='Details')

    @api.model
    def log(self, domain, check_type, result, expected=None, found=None, details=None):
        return self.sudo().create({'domain_id': domain.id, 'check_type': check_type, 'result': result,
                                   'expected_value': expected, 'found_value': found, 'details': details})
