"""
Email Service - إرسال الإيميلات بالعربي والإنجليزي
"""
import aiosmtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from jinja2 import Environment, BaseLoader
from datetime import datetime
from app.core.config import settings


TEMPLATES = {
    "verification": {
        "ar": {
            "subject": "كود تأكيد ClickBuild",
            "body": """
<div dir="rtl" style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
  <div style="background: #7C3AED; padding: 30px; text-align: center;">
    <h1 style="color: white; margin: 0;">ClickBuild</h1>
  </div>
  <div style="padding: 30px; background: #f9f9f9;">
    <h2>مرحباً {{ name }}!</h2>
    <p>شكراً لتسجيلك في ClickBuild. استخدم الكود التالي لتأكيد بريدك الإلكتروني:</p>
    <div style="text-align: center; margin: 30px 0;">
      <span style="font-size: 36px; font-weight: bold; letter-spacing: 10px; color: #7C3AED; background: #EDE9FE; padding: 15px 30px; border-radius: 8px;">{{ code }}</span>
    </div>
    <p style="color: #666;">الكود صالح لمدة 24 ساعة</p>
  </div>
</div>
"""
        },
        "en": {
            "subject": "ClickBuild Email Verification",
            "body": """
<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
  <div style="background: #7C3AED; padding: 30px; text-align: center;">
    <h1 style="color: white; margin: 0;">ClickBuild</h1>
  </div>
  <div style="padding: 30px; background: #f9f9f9;">
    <h2>Welcome {{ name }}!</h2>
    <p>Thank you for signing up. Use the code below to verify your email:</p>
    <div style="text-align: center; margin: 30px 0;">
      <span style="font-size: 36px; font-weight: bold; letter-spacing: 10px; color: #7C3AED; background: #EDE9FE; padding: 15px 30px; border-radius: 8px;">{{ code }}</span>
    </div>
    <p style="color: #666;">Code expires in 24 hours</p>
  </div>
</div>
"""
        }
    },
    "instance_ready": {
        "ar": {
            "subject": "🎉 بيئتك جاهزة على ClickBuild",
            "body": """
<div dir="rtl" style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
  <div style="background: #7C3AED; padding: 30px; text-align: center;">
    <h1 style="color: white;">ClickBuild 🚀</h1>
  </div>
  <div style="padding: 30px;">
    <h2>مرحباً {{ name }}!</h2>
    <p>بيئتك جاهزة! يمكنك الدخول الآن على:</p>
    <div style="text-align: center; margin: 20px 0;">
      <a href="{{ url }}" style="background: #7C3AED; color: white; padding: 15px 30px; border-radius: 8px; text-decoration: none; font-size: 18px;">
        {{ url }}
      </a>
    </div>
    <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
      <tr style="background: #f3f4f6;">
        <td style="padding: 10px; border: 1px solid #ddd;"><strong>البريد الإلكتروني</strong></td>
        <td style="padding: 10px; border: 1px solid #ddd;">{{ admin_email }}</td>
      </tr>
      <tr>
        <td style="padding: 10px; border: 1px solid #ddd;"><strong>كلمة المرور</strong></td>
        <td style="padding: 10px; border: 1px solid #ddd; font-family: monospace;">{{ admin_pass }}</td>
      </tr>
      <tr style="background: #f3f4f6;">
        <td style="padding: 10px; border: 1px solid #ddd;"><strong>ينتهي في</strong></td>
        <td style="padding: 10px; border: 1px solid #ddd;">{{ expires_at }}</td>
      </tr>
    </table>
    <p style="color: #EF4444; font-weight: bold;">⚠️ غيّر كلمة المرور فور دخولك</p>
    <p style="color: #666;">تجربتك المجانية تنتهي في {{ expires_at }} - <a href="https://clickbuild.com/upgrade">اشترك الآن</a></p>
  </div>
</div>
"""
        },
        "en": {
            "subject": "🎉 Your ClickBuild environment is ready!",
            "body": """
<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
  <div style="background: #7C3AED; padding: 30px; text-align: center;">
    <h1 style="color: white;">ClickBuild 🚀</h1>
  </div>
  <div style="padding: 30px;">
    <h2>Hello {{ name }}!</h2>
    <p>Your Odoo environment is ready! Access it now at:</p>
    <div style="text-align: center; margin: 20px 0;">
      <a href="{{ url }}" style="background: #7C3AED; color: white; padding: 15px 30px; border-radius: 8px; text-decoration: none; font-size: 18px;">
        {{ url }}
      </a>
    </div>
    <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
      <tr style="background: #f3f4f6;">
        <td style="padding: 10px; border: 1px solid #ddd;"><strong>Email</strong></td>
        <td style="padding: 10px; border: 1px solid #ddd;">{{ admin_email }}</td>
      </tr>
      <tr>
        <td style="padding: 10px; border: 1px solid #ddd;"><strong>Password</strong></td>
        <td style="padding: 10px; border: 1px solid #ddd; font-family: monospace;">{{ admin_pass }}</td>
      </tr>
      <tr style="background: #f3f4f6;">
        <td style="padding: 10px; border: 1px solid #ddd;"><strong>Trial expires</strong></td>
        <td style="padding: 10px; border: 1px solid #ddd;">{{ expires_at }}</td>
      </tr>
    </table>
    <p style="color: #EF4444; font-weight: bold;">⚠️ Change your password immediately after login</p>
  </div>
</div>
"""
        }
    },
    "trial_reminder": {
        "ar": {
            "subject": "⏰ تجربتك تنتهي خلال {{ days_left }} أيام",
            "body": """
<div dir="rtl" style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
  <div style="padding: 30px;">
    <h2>مرحباً {{ name }}!</h2>
    <p>تجربتك المجانية على ClickBuild ستنتهي خلال <strong>{{ days_left }} أيام</strong>.</p>
    <p>اشترك الآن للاستمرار وعدم فقدان بياناتك.</p>
    <div style="text-align: center; margin: 20px 0;">
      <a href="https://clickbuild.com/upgrade" style="background: #7C3AED; color: white; padding: 15px 30px; border-radius: 8px; text-decoration: none;">
        اشترك الآن
      </a>
    </div>
  </div>
</div>
"""
        },
        "en": {
            "subject": "⏰ Your trial expires in {{ days_left }} days",
            "body": """
<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
  <div style="padding: 30px;">
    <h2>Hello {{ name }}!</h2>
    <p>Your ClickBuild free trial expires in <strong>{{ days_left }} days</strong>.</p>
    <p>Subscribe now to keep your data and continue using Odoo.</p>
    <div style="text-align: center; margin: 20px 0;">
      <a href="https://clickbuild.com/upgrade" style="background: #7C3AED; color: white; padding: 15px 30px; border-radius: 8px; text-decoration: none;">
        Subscribe Now
      </a>
    </div>
  </div>
</div>
"""
        }
    }
}


class EmailService:
    env = Environment(loader=BaseLoader())

    @classmethod
    async def _send(cls, to: str, subject: str, html: str):
        msg = MIMEMultipart("alternative")
        msg["From"]    = f"{settings.EMAIL_FROM_NAME} <{settings.EMAIL_FROM}>"
        msg["To"]      = to
        msg["Subject"] = subject
        msg.attach(MIMEText(html, "html", "utf-8"))

        await aiosmtplib.send(
            msg,
            hostname  = settings.SMTP_HOST,
            port      = settings.SMTP_PORT,
            username  = settings.SMTP_USER,
            password  = settings.SMTP_PASSWORD,
            use_tls   = False,
            start_tls = True,
        )

    @classmethod
    async def send_verification(cls, email: str, name: str, code: str, language: str = "ar"):
        lang = language if language in ("ar", "en") else "ar"
        tmpl = TEMPLATES["verification"][lang]
        html = cls.env.from_string(tmpl["body"]).render(name=name, code=code)
        await cls._send(email, tmpl["subject"], html)

    @classmethod
    async def send_instance_ready(cls, email: str, name: str, subdomain: str,
                                   admin_pass: str, expires_at, language: str = "ar"):
        lang = language if language in ("ar", "en") else "ar"
        tmpl = TEMPLATES["instance_ready"][lang]
        url  = f"https://{subdomain}.clickbuild.com"
        expires_str = expires_at.strftime("%Y-%m-%d") if expires_at else "—"

        html = cls.env.from_string(tmpl["body"]).render(
            name=name, url=url, admin_email=email,
            admin_pass=admin_pass, expires_at=expires_str
        )
        await cls._send(email, tmpl["subject"], html)

    @classmethod
    async def send_password_reset(cls, email: str, name: str, token: str, language: str = "ar"):
        lang = language if language in ("ar", "en") else "ar"
        reset_url = f"https://clickbuild.com/reset-password?token={token}"
        subject   = "إعادة تعيين كلمة المرور" if lang == "ar" else "Password Reset"
        body = f"""<p>{'انقر الرابط التالي' if lang == 'ar' else 'Click to reset'}:
                   <a href="{reset_url}">{reset_url}</a></p>"""
        await cls._send(email, subject, body)

    @classmethod
    def send_trial_reminder_sync(cls, instance_id: str, days_left: int):
        """نسخة synchronous للـ Celery tasks"""
        import asyncio
        asyncio.run(cls._send_reminder_async(instance_id, days_left))

    @classmethod
    async def _send_reminder_async(cls, instance_id: str, days_left: int):
        from app.core.database import AsyncSessionLocal
        from app.models.instance import Instance
        from app.models.user import User
        from sqlalchemy import select

        async with AsyncSessionLocal() as db:
            inst = await db.get(Instance, instance_id)
            if not inst:
                return
            user = await db.get(User, inst.user_id)
            if not user:
                return

            lang = user.language.value
            tmpl = TEMPLATES["trial_reminder"][lang]
            subject = cls.env.from_string(tmpl["subject"]).render(days_left=days_left)
            html    = cls.env.from_string(tmpl["body"]).render(name=user.name, days_left=days_left)
            await cls._send(user.email, subject, html)

    @classmethod
    def send_trial_expired_sync(cls, user, instance):
        pass   # يمكن إضافة template لاحقاً
