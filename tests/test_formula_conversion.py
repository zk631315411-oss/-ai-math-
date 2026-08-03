from __future__ import annotations

import asyncio
import json
import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.auth.jwt_handler import create_access_token
from app.main import app
from app.services.formula_conversion_service import (
    FormulaConversionError,
    FormulaConversionService,
    SYSTEM_PROMPT,
    UnsafeFormulaError,
    choose_display_mode,
    sanitize_latex,
)


class FakeProvider:
    def __init__(self, name: str, result: str = "", error: Exception | None = None):
        self.name = name
        self.result = result
        self.error = error
        self.calls = 0

    async def convert(self, description: str, timeout: float) -> str:
        self.calls += 1
        if self.error:
            raise self.error
        return self.result


class FormulaSanitizerTests(unittest.TestCase):
    def test_extracts_json_and_delimiters(self) -> None:
        self.assertEqual(sanitize_latex('```json\n{"latex":"$x^2$"}\n```'), "x^2")

    def test_repairs_doubled_environment_end_slash(self) -> None:
        self.assertEqual(
            sanitize_latex(r"\begin{pmatrix}a&b\\c&d\\end{pmatrix}"),
            r"\begin{pmatrix}a&b\\c&d\end{pmatrix}",
        )

    def test_rejects_json_escapes_that_corrupt_latex_commands(self) -> None:
        malformed = r'{"latex":"\\lim_{x \to 0} \frac{\text{sin } x}{x}"}'
        with self.assertRaises(UnsafeFormulaError):
            sanitize_latex(malformed)

    def test_rejects_control_characters_before_stripping(self) -> None:
        for value in ("\frac{x}{y}", "\text{x}", "x\ny"):
            with self.subTest(value=repr(value)), self.assertRaises(UnsafeFormulaError):
                sanitize_latex(value)

    def test_rejects_non_math_commands(self) -> None:
        for value in (
            r"\href{https://example.com}{x}", r"\input{secret}", "<b>x</b>",
            '{"latex":"x^2","explanation":"square x"}', "解释：x^2", "The formula is x^2",
        ):
            with self.subTest(value=value), self.assertRaises(UnsafeFormulaError):
                sanitize_latex(value)

    def test_keeps_chinese_conditions_inside_latex_text(self) -> None:
        self.assertEqual(sanitize_latex(r"x\text{ 为偶数}"), r"x\text{ 为偶数}")

    def test_auto_display_uses_block_for_matrices(self) -> None:
        self.assertEqual(choose_display_mode(r"\begin{pmatrix}a&b\\c&d\end{pmatrix}", "auto"), "block")
        self.assertEqual(choose_display_mode(r"\frac{a}{b}", "auto"), "inline")


class FormulaFallbackTests(unittest.IsolatedAsyncioTestCase):
    async def test_local_success_stops_fallback(self) -> None:
        local = FakeProvider("local", result='{"latex":"x^2"}')
        cloudflare = FakeProvider("cloudflare", result="y")
        service = FormulaConversionService([local, cloudflare], timeout_seconds=1)
        self.assertEqual(await service.convert("x平方"), ("x^2", "inline"))
        self.assertEqual((local.calls, cloudflare.calls), (1, 0))

    async def test_falls_back_in_order(self) -> None:
        local = FakeProvider("local", error=ConnectionError("offline"))
        cloudflare = FakeProvider("cloudflare", result='{"latex":"\\\\frac{a}{b}"}')
        existing = FakeProvider("existing", result="x")
        service = FormulaConversionService([local, cloudflare, existing], timeout_seconds=1)
        latex, mode = await service.convert("a除以b")
        self.assertEqual((latex, mode), (r"\frac{a}{b}", "inline"))
        self.assertEqual((local.calls, cloudflare.calls, existing.calls), (1, 1, 0))

    async def test_existing_model_is_the_final_fallback(self) -> None:
        local = FakeProvider("local", error=ConnectionError("offline"))
        cloudflare = FakeProvider("cloudflare", result=r"\input{file}")
        existing = FakeProvider("existing", result='{"latex":"x_1+x_2"}')
        service = FormulaConversionService([local, cloudflare, existing], timeout_seconds=1)
        self.assertEqual(await service.convert("x下标1加x下标2"), ("x_1+x_2", "inline"))
        self.assertEqual((local.calls, cloudflare.calls, existing.calls), (1, 1, 1))

    async def test_control_character_output_falls_back(self) -> None:
        malformed = FakeProvider(
            "cloudflare",
            result=r'{"latex":"\\lim_{x \to 0} \frac{x}{x}"}',
        )
        existing = FakeProvider(
            "existing", result=r'{"latex":"\\lim_{x \\to 0} \\frac{x}{x}"}'
        )
        service = FormulaConversionService([malformed, existing], timeout_seconds=1)

        self.assertEqual(
            await service.convert("x趋于0时x除以x的极限"),
            (r"\lim_{x \to 0} \frac{x}{x}", "inline"),
        )
        self.assertEqual((malformed.calls, existing.calls), (1, 1))

    def test_prompt_examples_round_trip_as_json(self) -> None:
        outputs = [
            line.removeprefix("输出：")
            for line in SYSTEM_PROMPT.splitlines()
            if line.startswith("输出：")
        ]

        self.assertEqual(
            [json.loads(output)["latex"] for output in outputs],
            [
                r"\lim_{x \to 0} \frac{\sin x}{x}",
                r"\begin{pmatrix} a & b \\ c & d \end{pmatrix}",
                "x^2+y^2=1",
            ],
        )

    def test_prompt_forbids_solving_and_explanations(self) -> None:
        self.assertIn("不求值、不化简、不证明、不解释", SYSTEM_PROMPT)
        self.assertIn("裸公式", SYSTEM_PROMPT)

    async def test_total_timeout_is_enforced(self) -> None:
        slow = AsyncMock()

        class SlowProvider:
            name = "slow"

            async def convert(self, description: str, timeout: float) -> str:
                await asyncio.sleep(0.1)
                return "x"

        service = FormulaConversionService([SlowProvider()], timeout_seconds=0.01)
        with self.assertRaises(FormulaConversionError):
            await service.convert("x")

    async def test_logs_metadata_without_content(self) -> None:
        service = FormulaConversionService([FakeProvider("local", result="x")], timeout_seconds=1)
        with patch("app.services.formula_conversion_service.logger.info") as log:
            await service.convert("不能出现在日志里的描述")
        args, kwargs = log.call_args
        self.assertEqual(args, ("formula_conversion",))
        self.assertNotIn("不能出现在日志里的描述", repr(kwargs))
        self.assertNotIn("latex", kwargs["extra"])


class FormulaRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)
        token = create_access_token({"user_id": "formula-test-user"})
        self.headers = {"Authorization": f"Bearer {token}"}

    def test_requires_authentication(self) -> None:
        response = self.client.post("/api/formula/convert", json={"description": "x平方"})
        self.assertEqual(response.status_code, 401)

    def test_validates_description_boundary(self) -> None:
        response = self.client.post(
            "/api/formula/convert", json={"description": ""}, headers=self.headers
        )
        self.assertEqual(response.status_code, 422)
        response = self.client.post(
            "/api/formula/convert", json={"description": "   "}, headers=self.headers
        )
        self.assertEqual(response.status_code, 422)
        response = self.client.post(
            "/api/formula/convert", json={"description": "x" * 501}, headers=self.headers
        )
        self.assertEqual(response.status_code, 422)

    def test_returns_conversion(self) -> None:
        with patch(
            "app.routers.formula.formula_conversion_service.convert",
            new=AsyncMock(return_value=(r"\lim_{x \to 0}\frac{\sin x}{x}", "inline")),
        ):
            response = self.client.post(
                "/api/formula/convert",
                json={"description": "x趋于0时sin x除以x的极限", "preferred_display": "auto"},
                headers=self.headers,
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["display_mode"], "inline")

    def test_all_providers_failed_returns_503(self) -> None:
        with patch(
            "app.routers.formula.formula_conversion_service.convert",
            new=AsyncMock(side_effect=FormulaConversionError("unavailable")),
        ):
            response = self.client.post(
                "/api/formula/convert", json={"description": "x平方"}, headers=self.headers
            )
        self.assertEqual(response.status_code, 503)


if __name__ == "__main__":
    unittest.main()
