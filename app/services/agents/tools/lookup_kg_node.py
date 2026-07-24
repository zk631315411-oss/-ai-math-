"""lookup_kg_node 工具：查询知识图谱节点信息。"""

from __future__ import annotations

from app.db.kg_v44 import find_node, related_nodes
from app.services.agents.tool_def import ToolDef


def _lookup_kg_node_impl(
    concept_name: str,
) -> dict:
    """查询知识图谱节点信息。"""
    node = find_node(concept_name)
    if not node:
        return {"found": False, "message": f"未找到概念 '{concept_name}'"}

    support_nodes, lookahead_nodes = related_nodes(node.get("name", concept_name), limit=10)

    return {
        "found": True,
        "node": {
            "name": node.get("name"),
            "type": node.get("type") or node.get("node_type"),
            "source_code": node.get("source_code"),
            "evidence_span": node.get("evidence_span"),
        },
        "support_nodes": [
            {"name": n.get("name"), "type": n.get("type"), "rel_type": n.get("rel_type")}
            for n in (support_nodes or [])
            if n.get("name")
        ],
        "lookahead_nodes": [
            {"name": n.get("name"), "type": n.get("type"), "rel_type": n.get("rel_type")}
            for n in (lookahead_nodes or [])
            if n.get("name")
        ],
    }


lookup_kg_node_tool = ToolDef(
    name="lookup_kg_node",
    description="查询知识图谱中某个概念的定义、证据原文、前后置关系，返回概念详情和关联节点",
    input_schema={
        "type": "object",
        "properties": {
            "concept_name": {
                "type": "string",
                "description": "概念名称，如'特征值'、'线性无关'、'行列式'",
            },
        },
        "required": ["concept_name"],
    },
    execute=_lookup_kg_node_impl,
)