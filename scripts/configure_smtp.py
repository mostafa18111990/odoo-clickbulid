"""Configure the Odoo outgoing mail server.

Usage (inside the odoo_saas_app container):
    python3 /tmp/configure_smtp.py \\
        --smtp-host smtp.gmail.com \\
        --smtp-port 587 \\
        --smtp-user me@gmail.com \\
        --smtp-pass "app-password-here" \\
        --smtp-encryption starttls \\
        --from-email "no-reply@clickbulid.com"

Provider quick-reference:
    Gmail:    smtp.gmail.com:587 starttls (use an App Password, not your login)
    Brevo:    smtp-relay.brevo.com:587 starttls
    SendGrid: smtp.sendgrid.net:587 starttls (user "apikey", pass = the API key)
    Mailgun:  smtp.mailgun.org:587 starttls
"""
import argparse
import sys


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--smtp-host', required=True)
    p.add_argument('--smtp-port', type=int, default=587)
    p.add_argument('--smtp-user', required=True)
    p.add_argument('--smtp-pass', required=True)
    p.add_argument('--smtp-encryption', choices=['none', 'starttls', 'ssl'],
                   default='starttls')
    p.add_argument('--from-email', required=True)
    p.add_argument('--config', default='/etc/odoo/odoo.conf')
    p.add_argument('--db', default='odoo')
    p.add_argument('--test-recipient', help='Send a test message to this address',
                   default=None)
    args = p.parse_args()

    import odoo
    from odoo.tools import config
    config.parse_config(['-c', args.config])
    reg = odoo.modules.registry.Registry(args.db)
    with reg.cursor() as cr:
        env = odoo.api.Environment(cr, 1, {})

        # 1) Upsert the outgoing mail server.
        Server = env['ir.mail_server'].sudo()
        existing = Server.search([('smtp_host', '=', args.smtp_host),
                                  ('smtp_user', '=', args.smtp_user)], limit=1)
        vals = {
            'name': f'ClickBuild SMTP ({args.smtp_host})',
            'smtp_host': args.smtp_host,
            'smtp_port': args.smtp_port,
            'smtp_user': args.smtp_user,
            'smtp_pass': args.smtp_pass,
            'smtp_encryption': args.smtp_encryption,
            'smtp_authentication': 'login',
            'active': True,
            'sequence': 10,
        }
        if existing:
            existing.write(vals)
            mail_server = existing
            print(f'updated existing mail server id={existing.id}')
        else:
            mail_server = Server.create(vals)
            print(f'created mail server id={mail_server.id}')

        # 2) Set the default From address.
        env['ir.config_parameter'].sudo().set_param(
            'mail.default.from', args.from_email)
        env['ir.config_parameter'].sudo().set_param(
            'mail.bounce.alias', f'bounce@{args.from_email.split("@", 1)[1]}')

        # 3) Update saas.config from_email.
        cfg = env['saas.config'].sudo()._get_config()
        cfg.write({'from_email': args.from_email})

        cr.commit()
        print(f'default From: {args.from_email}')

        # 4) Optional test send — verifies the connection end-to-end.
        if args.test_recipient:
            print(f'sending test message to {args.test_recipient}...')
            try:
                msg = env['ir.mail_server'].build_email(
                    email_from=args.from_email,
                    email_to=[args.test_recipient],
                    subject='ClickBuild SMTP test',
                    body='If you can read this, SMTP works.\n',
                    subtype='plain')
                env['ir.mail_server'].send_email(
                    message=msg, mail_server_id=mail_server.id)
                print('test sent OK')
            except Exception as e:
                print(f'test FAILED: {e}')
                sys.exit(2)


if __name__ == '__main__':
    main()
