import logging

_logger = logging.getLogger(__name__)
RESOLVERS = ['8.8.8.8', '1.1.1.1']
DNS_TIMEOUT = 5.0


class DnsVerificationService:
    def __init__(self, env):
        self.env = env

    def _get_resolver(self):
        try:
            import dns.resolver
            resolver = dns.resolver.Resolver(configure=False)
            resolver.nameservers = RESOLVERS
            resolver.timeout = DNS_TIMEOUT
            resolver.lifetime = DNS_TIMEOUT * 2
            return resolver
        except ImportError:
            _logger.error('dnspython not installed')
            return None

    def check_txt(self, fqdn, expected_value):
        resolver = self._get_resolver()
        if not resolver:
            return {'found': False, 'values': [], 'error': 'DNS library unavailable'}
        try:
            import dns.resolver
            answers = resolver.resolve(fqdn, 'TXT')
            values = [b''.join(r.strings).decode('utf-8', errors='ignore') for r in answers]
            return {'found': any(expected_value in v for v in values), 'values': values, 'error': None}
        except dns.resolver.NXDOMAIN:
            return {'found': False, 'values': [], 'error': 'NXDOMAIN'}
        except dns.resolver.NoAnswer:
            return {'found': False, 'values': [], 'error': 'No TXT record'}
        except Exception as e:
            return {'found': False, 'values': [], 'error': str(e)}

    def check_cname(self, fqdn, expected_target):
        resolver = self._get_resolver()
        if not resolver:
            return {'found': False, 'target': None, 'error': 'DNS library unavailable'}
        try:
            import dns.resolver
            answers = resolver.resolve(fqdn, 'CNAME')
            targets = [str(r.target).rstrip('.') for r in answers]
            return {'found': any(t == expected_target.rstrip('.') for t in targets),
                    'target': targets[0] if targets else None, 'error': None}
        except dns.resolver.NXDOMAIN:
            return {'found': False, 'target': None, 'error': 'NXDOMAIN'}
        except dns.resolver.NoAnswer:
            return {'found': False, 'target': None, 'error': 'No CNAME record'}
        except Exception as e:
            return {'found': False, 'target': None, 'error': str(e)}

    def check_a(self, fqdn, expected_ip):
        resolver = self._get_resolver()
        if not resolver:
            return {'found': False, 'ips': [], 'error': 'DNS library unavailable'}
        try:
            import dns.resolver
            answers = resolver.resolve(fqdn, 'A')
            ips = [str(r) for r in answers]
            return {'found': expected_ip in ips, 'ips': ips, 'error': None}
        except dns.resolver.NXDOMAIN:
            return {'found': False, 'ips': [], 'error': 'NXDOMAIN'}
        except dns.resolver.NoAnswer:
            return {'found': False, 'ips': [], 'error': 'No A record'}
        except Exception as e:
            return {'found': False, 'ips': [], 'error': str(e)}
