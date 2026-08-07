from __future__ import annotations

import json
import asyncio
import tempfile
import unittest
from types import SimpleNamespace

from app.config import config
from app.db.chat_history_db import get_chat_history, migrate_user_id, save_chat_history
from app.db.chat_tree_db import begin_turn, create_tree, finish_turn, get_authorized_context
from app.db.connection import init_db
from app.db.visualization_db import get_visualization, save_visualization
from app.services.agents.tool_executor import execute_tool_call
from app.services.agents.tool_def import ToolDef
from app.services.agents.tools.create_math_visualization import create_math_visualization_tool
from app.services.visualization.expression import ExpressionError, SafeExpression
from app.services.visualization.spec_builder import build_visualization
from app.workers.manim_worker import validate_animation_recipe


class MathExpressionTests(unittest.TestCase):
    def test_allowed_expression_and_discontinuity(self) -> None:
        expression = SafeExpression("sin(x) + x^2")
        self.assertAlmostEqual(expression.evaluate(1), 1.8414709848)
        points = SafeExpression("1 / x").sample(-1, 1, 33)
        self.assertIsNone(points[16]["y"])

    def test_code_and_unsupported_names_are_rejected(self) -> None:
        for source in ("__import__('os')", "open('secret')", "x.__class__", "lambda: 1", "(-1)^0.5"):
            with self.subTest(source=source), self.assertRaises(ExpressionError):
                SafeExpression(source).evaluate(1)

    def test_sampling_limits_are_enforced(self) -> None:
        with self.assertRaises(ExpressionError):
            SafeExpression("x").sample(-1, 1, 601)
        with self.assertRaises(ExpressionError):
            SafeExpression("x").sample(-101, 101, 100)


class VisualizationSpecTests(unittest.IsolatedAsyncioTestCase):
    def test_supported_specs_and_animation_templates(self) -> None:
        function = build_visualization(
            kind="function_2d",
            series=[{"expression": "sin(x)"}, {"expression": "cos(x)"}],
            domain={"min": -3.14, "max": 3.14},
            samples=64,
            animation={"template": "function_transform"},
        )
        self.assertEqual(len(function["spec"]["series"]), 2)
        self.assertEqual(function["_animation_recipe"]["template"], "function_transform")

        parametric = build_visualization(
            kind="parametric_2d",
            series=[{"x_expression": "cos(t)", "y_expression": "sin(t)"}],
            samples=48,
        )
        self.assertEqual(len(parametric["spec"]["series"][0]["points"]), 48)

        vectors = build_visualization(kind="vector_2d", vectors=[{"x": 2, "y": 1}])
        self.assertEqual(vectors["spec"]["vectors"][0]["x"], 2)

        linear = build_visualization(
            kind="linear_transform_2d",
            matrix=[[1, 1], [0, 1]],
            vectors=[{"x": 1, "y": 2}],
            animation={"template": "linear_map_2d"},
        )
        self.assertEqual(linear["spec"]["vectors"][0]["transformed"], {"x": 3.0, "y": 2.0})

    def test_invalid_shapes_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            build_visualization(kind="function_2d", series=[])
        with self.assertRaises(ValueError):
            build_visualization(kind="linear_transform_2d", matrix=[[1]], vectors=[{"x": 1, "y": 1}])
        with self.assertRaises(ValueError):
            build_visualization(kind="vector_2d", vectors=[])
        with self.assertRaises(ValueError):
            build_visualization(kind="function_2d", series=[{"expression": "sqrt(-1)"}], samples=32)

    def test_worker_revalidates_versioned_animation_recipe(self) -> None:
        artifact = build_visualization(
            kind="linear_transform_2d",
            matrix=[[1, 1], [0, 1]],
            vectors=[{"x": 1, "y": 2}],
            animation={"template": "linear_map_2d"},
        )
        recipe = validate_animation_recipe(artifact["_animation_recipe"])
        self.assertEqual(recipe["parameters"]["vectors"][0]["transformed"], {"x": 3.0, "y": 2.0})
        with self.assertRaises(ValueError):
            validate_animation_recipe({**artifact["_animation_recipe"], "version": 2})
        with self.assertRaises(ValueError):
            validate_animation_recipe({**artifact["_animation_recipe"], "template": "arbitrary_python"})

    async def test_tool_executor_separates_model_result_from_artifact(self) -> None:
        tool_call = SimpleNamespace(
            id="call-1",
            function=SimpleNamespace(
                name="create_math_visualization",
                arguments=json.dumps({
                    "kind": "function_2d",
                    "series": [{"expression": "x**2"}],
                    "samples": 32,
                }),
            ),
        )
        result = await execute_tool_call(tool_call, [create_math_visualization_tool])
        model_result = result.model_payload
        self.assertTrue(model_result["success"])
        self.assertNotIn("spec", model_result)
        self.assertEqual(len(result.artifacts), 1)

    async def test_tool_accepts_json_stringified_structured_arguments(self) -> None:
        tool_call = SimpleNamespace(
            id="call-stringified",
            function=SimpleNamespace(
                name="create_math_visualization",
                arguments=json.dumps({
                    "kind": "function_2d",
                    "series": json.dumps([{"expression": "sin(x)"}]),
                    "domain": json.dumps({"min": -6.28, "max": 6.28}),
                    "samples": "64",
                }),
            ),
        )
        result = await execute_tool_call(tool_call, [create_math_visualization_tool])
        artifact = result.artifacts[0]
        self.assertEqual(len(artifact["spec"]["series"][0]["points"]), 64)
        self.assertEqual(artifact["spec"]["domain"], {"min": -6.28, "max": 6.28})

    async def test_tool_timeout_is_isolated(self) -> None:
        from unittest.mock import patch

        async def slow_tool() -> dict:
            await asyncio.sleep(0.05)
            return {"ok": True}

        tool = ToolDef(
            name="slow_tool",
            description="test",
            input_schema={"type": "object", "properties": {}},
            execute=slow_tool,
            timeout_seconds=0.001,
        )
        tool_call = SimpleNamespace(
            id="call-timeout",
            function=SimpleNamespace(name="slow_tool", arguments="{}"),
        )
        result = await execute_tool_call(tool_call, [tool])
        self.assertEqual(result.status, "error")
        self.assertEqual(result.error_code, "timeout")


class VisualizationPersistenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_db_path = config.DB_PATH
        config.DB_PATH = f"{self.temp_dir.name}/visualization.db"
        init_db()

    def tearDown(self) -> None:
        config.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def test_artifact_survives_tree_reload_and_is_user_scoped(self) -> None:
        tree = create_tree("student-a", "history-1", "画图", "先看定义")
        root = tree["nodes"][0]
        turn = begin_turn(root["id"], "student-a", "画 y=sin(x)", turn_id="turn-viz-1")
        artifact = build_visualization(
            kind="function_2d",
            series=[{"expression": "sin(x)"}],
            samples=32,
            animation={"template": "secant_to_tangent", "parameters": {"x0": 0}},
        )
        save_visualization(
            artifact,
            user_id="student-a",
            turn_id="turn-viz-1",
            chat_history_id="history-1",
        )
        completed = finish_turn("turn-viz-1", "student-a", "图如下。", "completed")
        self.assertEqual(completed["assistant_message"]["visualizations"][0]["id"], artifact["id"])
        context = get_authorized_context(turn["node_id"], "student-a")
        self.assertEqual(context[-1]["visualizations"][0]["kind"], "function_2d")
        with self.assertRaises(KeyError):
            get_visualization(artifact["id"], "student-b")

    def test_visualization_api_is_owned_and_animation_creation_is_idempotent(self) -> None:
        from unittest.mock import patch

        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from app.auth.jwt_handler import create_access_token
        from app.routers.visualizations import router

        artifact = build_visualization(
            kind="function_2d",
            series=[{"expression": "x**2"}],
            samples=32,
            animation={"template": "riemann_refinement", "parameters": {"interval": [0, 1]}},
        )
        save_visualization(artifact, user_id="student-a", turn_id="turn-api", chat_history_id=None)
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)
        owner_token = create_access_token({"user_id": "student-a"})
        other_token = create_access_token({"user_id": "student-b"})

        detail = client.get(
            f"/api/visualizations/{artifact['id']}?user_id=student-a",
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        self.assertEqual(detail.status_code, 200)
        forbidden = client.get(
            f"/api/visualizations/{artifact['id']}?user_id=student-a",
            headers={"Authorization": f"Bearer {other_token}"},
        )
        self.assertEqual(forbidden.status_code, 403)

        with patch("app.routers.visualizations.enqueue_animation", return_value="rq-1"):
            first = client.post(
                f"/api/visualizations/{artifact['id']}/animations",
                headers={"Authorization": f"Bearer {owner_token}"},
                json={"user_id": "student-a"},
            )
            second = client.post(
                f"/api/visualizations/{artifact['id']}/animations",
                headers={"Authorization": f"Bearer {owner_token}"},
                json={"user_id": "student-a"},
            )
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json()["id"], second.json()["id"])

    def test_chat_history_returns_visualizations_and_user_migration_keeps_access(self) -> None:
        chat_id = save_chat_history(user_id="anonymous-a", question="画图", answer="")
        artifact = build_visualization(
            kind="function_2d",
            series=[{"expression": "sin(x)"}],
            samples=32,
        )
        save_visualization(
            artifact,
            user_id="anonymous-a",
            turn_id="turn-history",
            chat_history_id=chat_id,
        )
        history = get_chat_history("anonymous-a", chat_id=chat_id)
        self.assertEqual(history[0]["visualizations"][0]["id"], artifact["id"])

        migrate_user_id("anonymous-a", "student-a")
        self.assertEqual(get_visualization(artifact["id"], "student-a")["kind"], "function_2d")
        with self.assertRaises(KeyError):
            get_visualization(artifact["id"], "anonymous-a")


if __name__ == "__main__":
    unittest.main()
