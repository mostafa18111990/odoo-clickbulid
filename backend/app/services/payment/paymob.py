"""
PayMob Integration - بوابة دفع مصر
يدعم: بطاقة ائتمان / فودافون كاش / فوري
"""
import httpx
import hashlib
import hmac
from typing import Optional
from app.core.config import settings


class PayMobService:
    BASE_URL = "https://accept.paymob.com/api"

    async def create_payment_order(
        self,
        amount_egp: float,
        order_id: str,
        user_email: str,
        user_name: str,
        user_phone: str,
        method: str = "card"  # card | wallet | fawry
    ) -> dict:
        """إنشاء أمر دفع وإرجاع رابط الدفع"""

        async with httpx.AsyncClient() as client:
            # 1. Auth Token
            auth_resp = await client.post(f"{self.BASE_URL}/auth/tokens", json={
                "api_key": settings.PAYMOB_API_KEY
            })
            auth_resp.raise_for_status()
            auth_token = auth_resp.json()["token"]

            # 2. إنشاء Order
            amount_cents = int(amount_egp * 100)
            order_resp = await client.post(
                f"{self.BASE_URL}/ecommerce/orders",
                headers={"Authorization": f"Bearer {auth_token}"},
                json={
                    "amount_cents": amount_cents,
                    "currency": "EGP",
                    "merchant_order_id": order_id,
                    "items": [],
                }
            )
            order_resp.raise_for_status()
            paymob_order_id = order_resp.json()["id"]

            # 3. Payment Key
            billing_data = {
                "apartment": "NA", "email": user_email,
                "floor": "NA", "first_name": user_name.split()[0],
                "street": "NA", "building": "NA",
                "phone_number": user_phone or "+201000000000",
                "shipping_method": "NA", "postal_code": "NA",
                "city": "Cairo", "country": "EG",
                "last_name": user_name.split()[-1] if " " in user_name else "NA",
                "state": "NA"
            }

            integration_id = {
                "card":   settings.PAYMOB_CARD_INTEGRATION_ID,
                "wallet": settings.PAYMOB_WALLET_INTEGRATION_ID,
                "fawry":  settings.PAYMOB_FAWRY_INTEGRATION_ID,
            }[method]

            key_resp = await client.post(
                f"{self.BASE_URL}/acceptance/payment_keys",
                headers={"Authorization": f"Bearer {auth_token}"},
                json={
                    "amount_cents":     amount_cents,
                    "expiration":       3600,
                    "order_id":         paymob_order_id,
                    "billing_data":     billing_data,
                    "currency":         "EGP",
                    "integration_id":   integration_id,
                    "lock_order_when_paid": True,
                }
            )
            key_resp.raise_for_status()
            payment_key = key_resp.json()["token"]

            # 4. رابط الدفع
            if method == "card":
                payment_url = f"https://accept.paymob.com/api/acceptance/iframes/{settings.PAYMOB_CARD_INTEGRATION_ID}?payment_token={payment_key}"
            elif method == "wallet":
                payment_url = f"https://accept.paymob.com/api/acceptance/iframes/{settings.PAYMOB_WALLET_INTEGRATION_ID}?payment_token={payment_key}"
            else:
                payment_url = f"https://accept.paymob.com/api/acceptance/iframes/{settings.PAYMOB_FAWRY_INTEGRATION_ID}?payment_token={payment_key}"

            return {
                "payment_url":      payment_url,
                "payment_key":      payment_key,
                "paymob_order_id":  str(paymob_order_id),
                "amount_cents":     amount_cents,
                "method":           method,
            }

    def verify_callback(self, data: dict) -> bool:
        """التحقق من صحة callback PayMob (HMAC)"""
        hmac_secret = settings.PAYMOB_HMAC_SECRET

        string_to_hash = "".join([
            str(data.get("amount_cents", "")),
            str(data.get("created_at", "")),
            str(data.get("currency", "")),
            str(data.get("error_occured", "")),
            str(data.get("has_parent_transaction", "")),
            str(data.get("id", "")),
            str(data.get("integration_id", "")),
            str(data.get("is_3d_secure", "")),
            str(data.get("is_auth", "")),
            str(data.get("is_capture", "")),
            str(data.get("is_refunded", "")),
            str(data.get("is_standalone_payment", "")),
            str(data.get("is_voided", "")),
            str(data.get("order", {}).get("id", "")),
            str(data.get("owner", "")),
            str(data.get("pending", "")),
            str(data.get("source_data", {}).get("pan", "")),
            str(data.get("source_data", {}).get("sub_type", "")),
            str(data.get("source_data", {}).get("type", "")),
            str(data.get("success", "")),
        ])

        computed = hmac.new(
            hmac_secret.encode(),
            string_to_hash.encode(),
            hashlib.sha512
        ).hexdigest()

        return computed == data.get("hmac")
