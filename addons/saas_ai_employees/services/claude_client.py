import json
import os
import time
import urllib.error
import urllib.request


class ClaudeApiError(RuntimeError):
    pass


class ClaudeClient:
    def __init__(self, api_key, base_url='https://api.anthropic.com/v1', timeout=30):
        if not api_key:
            raise ClaudeApiError('ANTHROPIC_API_KEY is not configured in the runtime environment.')
        self.api_key = api_key
        self.base_url = (base_url or 'https://api.anthropic.com/v1').rstrip('/')
        self.timeout = max(5, min(int(timeout or 30), 120))

    @classmethod
    def from_provider(cls, provider):
        return cls(
            api_key=os.environ.get('ANTHROPIC_API_KEY'),
            base_url=provider.base_url,
            timeout=provider.timeout_seconds,
        )

    def create_message(self, system, prompt, model, max_tokens=2048, temperature=0.7):
        if not model:
            raise ClaudeApiError('No Claude model is configured.')
        api_version = os.environ.get('ANTHROPIC_API_VERSION', '2026-10-21')
        payload = {
            'model': model,
            'max_tokens': max(1, min(int(max_tokens or 2048), 32768)),
            'system': system or '',
            'messages': [{'role': 'user', 'content': prompt}],
        }
        # The 2026-10-21 API removed temperature/top_p/top_k. Keep the
        # legacy option only when an older version is selected explicitly.
        if api_version < '2026-10-21':
            payload['temperature'] = max(
                0.0, min(float(temperature or 0.0), 1.0))
        request = urllib.request.Request(
            f'{self.base_url}/messages',
            data=json.dumps(payload).encode('utf-8'),
            headers={
                'content-type': 'application/json',
                'x-api-key': self.api_key,
                'anthropic-version': api_version,
                'user-agent': 'ClickBuild-AI-Employees/1.0',
            },
            method='POST',
        )
        started = time.monotonic()
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                data = json.loads(response.read().decode('utf-8'))
        except urllib.error.HTTPError as exc:
            raise ClaudeApiError(f'Claude API rejected the request (HTTP {exc.code}).') from exc
        except urllib.error.URLError as exc:
            raise ClaudeApiError('Claude API is unavailable.') from exc
        except (ValueError, UnicodeDecodeError) as exc:
            raise ClaudeApiError('Claude API returned an invalid response.') from exc

        text = ''.join(
            block.get('text', '') for block in data.get('content', [])
            if block.get('type') == 'text'
        ).strip()
        if not text:
            raise ClaudeApiError('Claude API returned no text output.')
        usage = data.get('usage') or {}
        return {
            'text': text,
            'model': data.get('model') or model,
            'input_tokens': int(usage.get('input_tokens') or 0),
            'output_tokens': int(usage.get('output_tokens') or 0),
            'response_time_ms': int((time.monotonic() - started) * 1000),
        }
