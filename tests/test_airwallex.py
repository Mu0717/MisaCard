import unittest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import httpx

from app.utils import activation, mercury


CODE = "00000000-0000-4000-8000-000000000001"
SAMPLE = {
    "card_id": "test-card",
    "card_number": "4111111111111111",
    "exp": "10/27",
    "cvc": "123",
    "limit": 0,
    "billing_address": None,
    "remaining_minutes": 60,
    "is_new": True,
}


class AirwallexTests(unittest.IsolatedAsyncioTestCase):
    async def redeem(self, data=None, status=200, key=CODE + "-4513", content=None):
        response = httpx.Response(status, json=data) if content is None else httpx.Response(status, content=content)
        with patch.object(mercury.httpx.AsyncClient, "post", new_callable=AsyncMock, return_value=response) as post:
            result = await mercury.redeem_airwallex_key(key)
            post.assert_awaited_once()
            self.assertEqual(post.call_args.args[0], "https://timoes.me/api/redeem/view")
            self.assertEqual(post.call_args.kwargs["json"], {"code": CODE})
            self.assertEqual(post.call_args.kwargs["headers"]["origin"], "https://timoes.me")
        return result

    async def test_success_and_extraction(self):
        before = datetime.now(timezone.utc)
        result = await self.redeem(SAMPLE)
        self.assertTrue(result["success"])
        info = activation.extract_card_info(result)
        self.assertEqual(info["card_number"], SAMPLE["card_number"])
        self.assertEqual(info["card_cvc"], "123")
        self.assertEqual(info["card_exp_date"], "10/27")
        self.assertEqual(info["card_limit"], 0)
        self.assertEqual(info["validity_hours"], 1)
        self.assertEqual(info["legal_address"]["country"], "US")
        self.assertIsNone(info["create_time"])
        self.assertAlmostEqual((datetime.fromisoformat(info["exp_date"]) - before).total_seconds(), 3600, delta=5)

    async def test_bare_uuid_not_truncated(self):
        self.assertTrue((await self.redeem(SAMPLE, key=" " + CODE + " "))["success"])

    async def test_existing_card_zero_remaining(self):
        result = await self.redeem({**SAMPLE, "is_new": False, "remaining_minutes": 0})
        self.assertTrue(result["success"])
        self.assertFalse(result["is_new"])
        self.assertEqual(activation.extract_card_info(result)["validity_hours"], 0)

    async def test_addresses(self):
        for address in ("123 Test Street", {"address1": "123 Test Street", "city": "Test City"}):
            with self.subTest(address=address):
                result = await self.redeem({**SAMPLE, "billing_address": address})
                self.assertIn("123 Test Street", activation.extract_card_info(result)["billing_address"])

    async def test_errors(self):
        for data, status in (({"error": "invalid code"}, 400), ({"detail": "expired"}, 403),
                             ({"success": False}, 200), ([], 200), ({}, 200),
                             ({**SAMPLE, "cvc": None}, 200), (SAMPLE, 500)):
            with self.subTest(data=data, status=status):
                result = await self.redeem(data, status)
                self.assertFalse(result["success"])
                self.assertTrue(result["error"])
        self.assertFalse((await self.redeem(content=b"<html>error</html>", status=502))["success"])

    async def test_network_error(self):
        with patch.object(mercury.httpx.AsyncClient, "post", new_callable=AsyncMock,
                          side_effect=httpx.ConnectError("unavailable")):
            self.assertFalse((await mercury.redeem_airwallex_key(CODE))["success"])

    async def test_activation_routes(self):
        with patch.object(activation, "redeem_airwallex_key", new_callable=AsyncMock,
                          return_value={"success": True}) as airwallex, \
             patch.object(activation, "redeem_key", new_callable=AsyncMock,
                          return_value={"success": True}) as mercury_redeem:
            self.assertTrue((await activation.activate_card_via_api(CODE + "-4513"))[0])
            airwallex.assert_awaited_once_with(CODE + "-4513")
            mercury_redeem.assert_not_awaited()
            await activation.activate_card_via_api(CODE)
            await activation.activate_card_via_api(CODE + "-520524")
            self.assertEqual(mercury_redeem.await_count, 2)


if __name__ == "__main__":
    unittest.main()
