"""
PayTabs Integration - بوابة دفع الخليج العربي
يدعم: مدى / Visa / MasterCard / STC Pay / Apple Pay
"""
import httpx
from typing import Optional
from app.core.config import settings

REGION_URLS = {
    "EGY": "https://secure-egypt.paytabs.com",
    "SAU": "https://secure.paytabs.sa",
    "ARE": "https://secure.paytabs.com",
    "KWT": "https://secure-kuwait.paytabs.com",
    "OMN": "https://secure-oman.paytabs.com",
    "JOR": "https://secure-jordan.paytabs.com",
}

CURRENCY_MAP = {
    "EG": "EGP", "SA": "SAR", "AE": "AED",
    "KW": "KWD", "OM": "OMR", "QA": "QAR", "JO": "JOD"
}


class PayTabsService:

    def _base_url(self) -> str:
        return REGION_URLS.get(settings.PAYTABS_REGION, REGION_URLS["EGY"])

    async def create_payment(
        self,
        amount: float,
        currency: str,
        order_id: str,
        description: str,
        user_name: str,
        user_email: str,
        user_phone: str,
        country_code: str = "EG",
        callback_url: Optional[str] = None,
        return_url: Optional[str] = None
    ) -> dict:
        """إنشاء صفحة دفع PayTabs"""

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self._base_url()}/payment/request",
                headers={
                    "Authorization": settings.PAYTABS_SERVER_KEY,
                    "Content-Type": "application/json"
                },
                json={
                    "profile_id":        settings.PAYTABS_PROFILE_ID,
                    "tran_type":         "sale",
                    "tran_class":        "ecom",
                    "cart_id":           order_id,
                    "cart_description":  description,
                    "cart_currency":     currency,
                    "cart_amount":       amount,

                    "callback":   callback_url or f"https://clickbuild.com/api/v1/payments/paytabs/callback",
                    "return":     return_url    or f"https://clickbuild.com/payment/success",

                    "customer_details": {
                        "name":    user_name,
                        "email":   user_email,
                        "phone":   user_phone,
                        "street1": "NA",
                        "city":    "NA",
                        "state":   "NA",
                        "country": country_code,
                        "zip":     "00000",
                    },
                    "shipping_details": {
                        "name":    user_name,
                        "email":   user_email,
                        "phone":   user_phone,
                        "street1": "NA",
                        "city":    "NA",
                        "state":   "NA",
                        "country": country_code,
                        "zip":     "00000",
                    },
                    "hide_shipping": True,
                    "framed":        False,
                    "lang":          "ar",
                }
            )
            resp.raise_for_status()
            data = resp.json()

            return {
                "payment_url":  data.get("redirect_url"),
                "tran_ref":     data.get("tran_ref"),
                "order_id":     order_id,
                "amount":       amount,
                "currency":     currency,
            }

    async def verify_payment(self, tran_ref: str) -> dict:
        """التحقق من حالة معاملة"""
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self._base_url()}/payment/query",
                headers={
                    "Authorization": settings.PAYTABS_SERVER_KEY,
                    "Content-Type": "application/json"
                },
                json={
                    "profile_id": settings.PAYTABS_PROFILE_ID,
                    "tran_ref":   tran_ref,
                }
            )
            resp.raise_for_status()
            data = resp.json()

            return {
                "success":     data.get("payment_result", {}).get("response_status") == "A",
                "tran_ref":    tran_ref,
                "amount":      data.get("cart_amount"),
                "currency":    data.get("cart_currency"),
                "raw":         data,
            }
