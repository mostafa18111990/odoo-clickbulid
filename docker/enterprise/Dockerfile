# ClickBuild — Odoo 19 Enterprise image
#
# Strategy: extend the official odoo:19 base image and overlay the proprietary
# Enterprise addons we receive as a Partner. The enterprise tree is brought in
# at BUILD time via the `ENTERPRISE_SRC` build arg (a directory the build
# context has access to) so the source never leaves our repo.
#
# Build:
#   cd /opt/odoo-saas
#   docker build \
#     -f docker/enterprise/Dockerfile \
#     -t clickbuild/odoo-enterprise:19 \
#     --build-arg ENTERPRISE_SRC=./enterprise \
#     .
#
# The resulting image is identical to odoo:19 except for an extra addons path
# (/mnt/enterprise) that the container's odoo.conf will include.
FROM odoo:19

# ─── Image metadata ────────────────────────────────────────────────────────
LABEL org.opencontainers.image.title="ClickBuild Odoo 19 Enterprise"
LABEL org.opencontainers.image.vendor="ClickBuild"
LABEL org.opencontainers.image.licenses="Proprietary (Odoo Enterprise Subscription)"
LABEL org.opencontainers.image.source="github.com/clickbuild/odoo-saas"

# ─── Build args ────────────────────────────────────────────────────────────
# Path inside the build context that contains the enterprise tree. If you
# build from a private fork or a tarball, this is where you point it.
ARG ENTERPRISE_SRC=./enterprise

USER root

# Copy the enterprise addons. The COPY is conditional on the path existing;
# if you want to build without enterprise (smoke test), set ENTERPRISE_SRC
# to ./docker/enterprise/empty (an empty placeholder dir).
COPY ${ENTERPRISE_SRC} /mnt/enterprise

# Make sure odoo can read the files even after volume mounts.
RUN chown -R odoo:odoo /mnt/enterprise \
 && chmod -R u+rX /mnt/enterprise

# Extra Python packages that enterprise modules need but aren't in base image.
# Keep this list short — install only what's strictly required so the image
# stays lean. Add more on demand.
RUN pip install --no-cache-dir --break-system-packages \
        phonenumbers \
        ofxparse \
        qifparse \
        cryptography \
        firebase-admin \
        google-auth \
    || true

USER odoo

# The conf file we mount at runtime declares the multi-path addons_path:
#   /usr/lib/python3/dist-packages/odoo/addons     (Community core)
#   /mnt/enterprise                                (Odoo Enterprise)
#   /mnt/extra-addons                              (our saas_* + tenant addons)
# So nothing else is needed in the Dockerfile.
