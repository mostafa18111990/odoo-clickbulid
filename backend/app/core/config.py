from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # ─── App ──────────────────────────────────────────────────────────────────
    APP_NAME: str = "ClickBuild API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    DOMAIN: str = "clickbuild.com"

    # ─── Security ─────────────────────────────────────────────────────────────
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # ─── Database ─────────────────────────────────────────────────────────────
    DATABASE_URL: str
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "clickbuild"
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str = "clickbuild_platform"

    # ─── Redis ────────────────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379"
    REDIS_PASSWORD: str = ""

    # ─── Email ────────────────────────────────────────────────────────────────
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str
    SMTP_PASSWORD: str
    EMAIL_FROM: str = "noreply@clickbuild.com"
    EMAIL_FROM_NAME: str = "ClickBuild"

    # ─── Odoo ─────────────────────────────────────────────────────────────────
    ODOO_MASTER_PASSWORD: str
    ODOO_PORT_START: int = 8100
    ODOO_PORT_END: int = 9000
    ODOO_VERSIONS: List[str] = ["19"]
    ODOO_DEFAULT_VERSION: str = "19"

    # ─── Payment: PayMob (Egypt) ──────────────────────────────────────────────
    PAYMOB_API_KEY: str = ""
    PAYMOB_HMAC_SECRET: str = ""
    PAYMOB_CARD_INTEGRATION_ID: int = 0
    PAYMOB_WALLET_INTEGRATION_ID: int = 0
    PAYMOB_FAWRY_INTEGRATION_ID: int = 0

    # ─── Payment: PayTabs (Arabic) ────────────────────────────────────────────
    PAYTABS_PROFILE_ID: str = ""
    PAYTABS_SERVER_KEY: str = ""
    PAYTABS_REGION: str = "EGY"  # EGY, SAU, ARE, ...

    # ─── Odoo Bridge (shared secrets with saas_core) ──────────────────────────
    INTERNAL_API_TOKEN: str = ""          # == saas.config.api_internal_token
    ODOO_WEBHOOK_SECRET: str = ""         # == saas.config.webhook_secret
    ODOO_WEBHOOK_URL: str = "http://127.0.0.1:8069/saas/core/webhook/provisioning"

    # ─── Trial ────────────────────────────────────────────────────────────────
    TRIAL_DAYS: int = 14
    TRIAL_MAX_USERS: int = 3
    TRIAL_STORAGE_GB: float = 1.0

    # ─── Frontend ─────────────────────────────────────────────────────────────
    FRONTEND_URL: str = "https://clickbuild.com"
    ALLOWED_ORIGINS: List[str] = ["https://clickbuild.com", "https://www.clickbuild.com"]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
