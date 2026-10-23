# ClickBuild - Custom Odoo 20 Image
# Base: Official Odoo 20 + تحسينات للـ SaaS

FROM odoo:20.0

USER root

# ─── System Dependencies ──────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    curl wget gettext-base \
    fonts-noto-cjk \
    fonts-noto \
    && rm -rf /var/lib/apt/lists/*

# ─── Arabic Fonts ─────────────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-arabeyes \
    fonts-farsiweb \
    fonts-hosny-amiri \
    && rm -rf /var/lib/apt/lists/* \
    && fc-cache -fv

# ─── Python Extra Packages ────────────────────────────────────────────────────
RUN pip3 install --break-system-packages --no-cache-dir \
    phonenumbers \
    vobject \
    pyldap \
    qrcode \
    Pillow \
    suds-py3 \
    qifparse \
    ofxparse \
    python-barcode \
    paramiko

# ─── Odoo Config Template ─────────────────────────────────────────────────────
COPY docker/odoo20/odoo.conf.template /etc/odoo/odoo.conf.template
COPY docker/odoo20/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# ─── Custom Addons Directory ──────────────────────────────────────────────────
RUN mkdir -p /mnt/extra-addons /mnt/enterprise \
    && chown odoo:odoo /mnt/extra-addons /mnt/enterprise

# ─── Healthcheck ──────────────────────────────────────────────────────────────
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8069/web/health || exit 1

USER odoo

EXPOSE 8069 8072

ENTRYPOINT ["/entrypoint.sh"]
CMD ["odoo"]
