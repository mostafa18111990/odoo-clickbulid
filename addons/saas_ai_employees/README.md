# ClickBuild AI Employees

This Odoo 19 addon introduces four Claude-powered roles: sales, marketing,
community management, and analytics. Work is queued as auditable tasks and
sensitive actions stay behind a human approval gate by default.

## Runtime configuration

Provide the Claude credential to the Odoo runtime as an environment variable:

```text
ANTHROPIC_API_KEY=<secret managed by the deployment platform>
```

`ANTHROPIC_API_VERSION` is optional and defaults to `2026-10-21`. Social credentials are never stored in
Odoo; each channel stores only the name of an environment variable managed by
the deployment platform.

## Supported channel catalog

The channel model covers WhatsApp, Instagram, Facebook, TikTok, LinkedIn, X,
YouTube, and Telegram. This first release supplies the employee/task engine,
Claude execution, approval workflow, audit trail, retry policy, company
isolation, and secure credential references. Publishing adapters require each
platform's developer app, OAuth approval, scopes, webhooks, and media workflow
before a channel can be marked connected.

TikTok and YouTube primarily require media upload workflows. WhatsApp is a
messaging channel rather than a public-post feed. These differences are kept in
the channel capability flags instead of being hidden behind a misleading
one-size-fits-all publish action.
