import json

from fastapi import APIRouter, HTTPException, Header, Query
from typing import Optional
from app.models.schemas import (
    UserRegister, UserLogin, TokenResponse,
    UserProfileUpdate, UserProfileResponse,
    MathProfileUpdate, MathProfileResponse,
    KnowledgeStatsResponse, DiagnosticHistoryResponse
)
from app.db.auth_db import save_user, get_user_by_username, get_user_by_id, get_user_by_device_id
from app.db.user_profile_db import save_user_profile, get_user_profile
from app.db.math_profile_db import save_math_profile, get_math_profile
from app.db.knowledge_stats_db import get_knowledge_stats
from app.db.question_assessment_db import get_question_assessments
from app.auth.jwt_handler import (
    get_password_hash, verify_password, create_access_token,
    decode_token, generate_user_id
)

router = APIRouter(prefix="/api/auth", tags=["用户认证"])


def get_user_id_from_token(authorization: Optional[str]) -> Optional[str]:
    """从Authorization header解析user_id"""
    if not authorization:
        return None
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    try:
        token_data = decode_token(parts[1])
        return token_data.get("user_id")
    except Exception:
        return None


@router.post("/register", response_model=TokenResponse)
def register(req: UserRegister):
    """用户注册"""
    # 检查用户名是否已存在
    existing = get_user_by_username(req.username)
    if existing:
        raise HTTPException(status_code=400, detail="用户名已存在")

    # 创建用户
    user_id = generate_user_id()
    password_hash = get_password_hash(req.password)
    success = save_user(user_id, req.username, password_hash, req.device_id)
    if not success:
        raise HTTPException(status_code=500, detail="创建用户失败")

    # 创建空画像
    save_user_profile(user_id)

    # 生成token
    token = create_access_token({"user_id": user_id, "username": req.username})
    return TokenResponse(
        access_token=token,
        user_id=user_id,
        username=req.username
    )


@router.post("/login", response_model=TokenResponse)
def login(req: UserLogin):
    """用户登录"""
    user = get_user_by_username(req.username)
    if not user:
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    if not verify_password(req.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    token = create_access_token({"user_id": user["id"], "username": user["username"]})
    return TokenResponse(
        access_token=token,
        user_id=user["id"],
        username=user["username"]
    )


@router.post("/anonymous", response_model=TokenResponse)
def anonymous_access(device_id: str):
    """匿名访问（设备首次访问自动创建账户）"""
    # 检查设备是否已有账户
    existing = get_user_by_device_id(device_id)
    if existing:
        token = create_access_token({"user_id": existing["id"], "username": existing["username"]})
        return TokenResponse(
            access_token=token,
            user_id=existing["id"],
            username=existing["username"]
        )

    # 自动创建匿名账户
    user_id = generate_user_id()
    username = f"user_{device_id[:8]}"  # 用设备ID前8位作为默认用户名
    password_hash = get_password_hash("")
    success = save_user(user_id, username, password_hash, device_id)
    if not success:
        raise HTTPException(status_code=500, detail="创建匿名账户失败")

    # 创建空画像
    save_user_profile(user_id)

    token = create_access_token({"user_id": user_id, "username": username})
    return TokenResponse(
        access_token=token,
        user_id=user_id,
        username=username
    )


@router.get("/me", response_model=UserProfileResponse)
def get_current_user(authorization: Optional[str] = Header(None)):
    """获取当前登录用户信息"""
    user_id = get_user_id_from_token(authorization)
    if not user_id:
        raise HTTPException(status_code=401, detail="未登录或token无效")

    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    profile = get_user_profile(user_id)
    return UserProfileResponse(
        id=user_id,
        username=user["username"],
        grade=profile.get("grade") if profile else "",
        weak_points=profile.get("weak_points", []) if profile else [],
        strong_points=profile.get("strong_points", []) if profile else [],
        created_at=user["created_at"]
    )


@router.put("/profile", response_model=UserProfileResponse)
def update_profile(
    profile_update: UserProfileUpdate,
    authorization: Optional[str] = Header(None)
):
    """更新用户画像"""
    user_id = get_user_id_from_token(authorization)
    if not user_id:
        raise HTTPException(status_code=401, detail="未登录或token无效")

    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    save_user_profile(
        user_id,
        grade=profile_update.grade,
        weak_points=profile_update.weak_points,
        strong_points=profile_update.strong_points,
        learning_preferences=profile_update.learning_preferences
    )

    profile = get_user_profile(user_id)
    return UserProfileResponse(
        id=user_id,
        username=user["username"],
        grade=profile.get("grade") if profile else "",
        weak_points=profile.get("weak_points", []) if profile else [],
        strong_points=profile.get("strong_points", []) if profile else [],
        created_at=user["created_at"]
    )


# === 数学素养画像API ===

@router.get("/math-profile", response_model=MathProfileResponse)
def get_math_user_profile(authorization: Optional[str] = Header(None)):
    """获取当前用户的数学素养画像（多维度）"""
    user_id = get_user_id_from_token(authorization)
    if not user_id:
        raise HTTPException(status_code=401, detail="未登录或token无效")

    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    profile = get_math_profile(user_id)
    if not profile:
        # 返回默认空画像
        return MathProfileResponse(
            user_id=user_id,
            username=user["username"],
            grade="",
            dimensions={
                "mathematical_thinking": {"coverage": 0, "radius": 0, "technical": 0},
                "logical_reasoning": {"coverage": 0, "radius": 0, "technical": 0},
                "symbolic_operation": {"coverage": 0, "radius": 0, "technical": 0},
                "multi_representation": {"coverage": 0, "radius": 0, "technical": 0},
                "problem_solving": {"coverage": 0, "radius": 0, "technical": 0},
            },
            weak_points=[],
            latest_diagnostic_report={},
            last_diagnosed_at=None,
            overall_average=0.0
        )

    # 计算各维度平均分
    dims = profile["dimensions"]
    dim_averages = {}
    total = 0.0
    for dim_name, scores in dims.items():
        avg = (scores["coverage"] + scores["radius"] + scores["technical"]) / 3.0
        dim_averages[dim_name] = avg
        total += avg
    overall_avg = total / 5.0

    return MathProfileResponse(
        user_id=user_id,
        username=user["username"],
        grade=profile.get("grade", ""),
        dimensions=dims,
        weak_points=profile.get("weak_points", []),
        latest_diagnostic_report=profile.get("latest_diagnostic_report", {}),
        last_diagnosed_at=profile.get("last_diagnosed_at"),
        overall_average=round(overall_avg, 2),
        created_at=profile.get("created_at")
    )


@router.put("/math-profile", response_model=MathProfileResponse)
def update_math_user_profile(
    profile_update: MathProfileUpdate,
    authorization: Optional[str] = Header(None)
):
    """更新当前用户的数学素养画像"""
    user_id = get_user_id_from_token(authorization)
    if not user_id:
        raise HTTPException(status_code=401, detail="未登录或token无效")

    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    save_math_profile(
        user_id,
        grade=profile_update.grade,
        mt_coverage=profile_update.mt_coverage or 0,
        mt_radius=profile_update.mt_radius or 0,
        mt_technical=profile_update.mt_technical or 0,
        lr_coverage=profile_update.lr_coverage or 0,
        lr_radius=profile_update.lr_radius or 0,
        lr_technical=profile_update.lr_technical or 0,
        so_coverage=profile_update.so_coverage or 0,
        so_radius=profile_update.so_radius or 0,
        so_technical=profile_update.so_technical or 0,
        mr_coverage=profile_update.mr_coverage or 0,
        mr_radius=profile_update.mr_radius or 0,
        mr_technical=profile_update.mr_technical or 0,
        ps_coverage=profile_update.ps_coverage or 0,
        ps_radius=profile_update.ps_radius or 0,
        ps_technical=profile_update.ps_technical or 0,
        weak_points=profile_update.weak_points
    )

    # 返回更新后的画像
    profile = get_math_profile(user_id)
    dims = profile["dimensions"] if profile else {}
    dim_averages = {}
    total = 0.0
    for dim_name, scores in dims.items():
        avg = (scores["coverage"] + scores["radius"] + scores["technical"]) / 3.0
        dim_averages[dim_name] = avg
        total += avg
    overall_avg = total / 5.0 if dims else 0.0

    return MathProfileResponse(
        user_id=user_id,
        username=user["username"],
        grade=profile.get("grade", "") if profile else "",
        dimensions=dims,
        weak_points=profile.get("weak_points", []) if profile else [],
        latest_diagnostic_report=profile.get("latest_diagnostic_report", {}) if profile else {},
        last_diagnosed_at=profile.get("last_diagnosed_at") if profile else None,
        overall_average=round(overall_avg, 2),
        created_at=profile.get("created_at") if profile else None
    )


@router.get("/knowledge-stats", response_model=KnowledgeStatsResponse)
def get_user_knowledge_stats(authorization: Optional[str] = Header(None)):
    """获取用户的知识点统计（哪些概念被反复问）"""
    user_id = get_user_id_from_token(authorization)
    if not user_id:
        raise HTTPException(status_code=401, detail="未登录或token无效")

    stats = get_knowledge_stats(user_id)
    return KnowledgeStatsResponse(user_id=user_id, stats=stats)


@router.get("/diagnostic-history", response_model=DiagnosticHistoryResponse)
def get_user_diagnostic_history(authorization: Optional[str] = Header(None)):
    """获取用户的诊断历史记录"""
    user_id = get_user_id_from_token(authorization)
    if not user_id:
        raise HTTPException(status_code=401, detail="未登录或token无效")

    assessments = get_question_assessments(user_id)
    history = []
    for a in assessments:
        history.append({
            "assessment_id": a.get("id", ""),
            "sequence_id": a.get("sequence_id", ""),
            "dimension_deltas": a.get("dimension_deltas", []),
            "weak_concepts": a.get("weak_concepts", []),
            "summary": a.get("summary", ""),
            "created_at": a.get("created_at")
        })
    return DiagnosticHistoryResponse(user_id=user_id, history=history)


# === Phase 2: 画像洞察 ===

@router.get("/insight")
async def get_insight(authorization: Optional[str] = Header(None)):
    """获取学习洞察报告（24h 缓存）。"""
    user_id = get_user_id_from_token(authorization)
    if not user_id:
        raise HTTPException(status_code=401, detail="未登录或token无效")

    from app.services.insight_generator import get_cached_or_generate, generate

    cached = get_cached_or_generate(user_id)
    if cached:
        return {"user_id": user_id, "insight": cached, "cached": True}

    report = await generate(user_id)
    return {"user_id": user_id, "insight": report, "cached": False}


@router.post("/insight/regenerate")
async def regenerate_insight(authorization: Optional[str] = Header(None)):
    """强制重新生成洞察报告（无视缓存）。"""
    user_id = get_user_id_from_token(authorization)
    if not user_id:
        raise HTTPException(status_code=401, detail="未登录或token无效")

    from app.services.insight_generator import generate

    report = await generate(user_id)
    return {"user_id": user_id, "insight": report, "cached": False}


# === 知识图谱 API ===

STAGE_LABELS = {0: "未接触", 1: "入门", 2: "理解", 3: "应用", 4: "分析", 5: "综合"}


@router.get("/diagnostic-cards")
async def get_diagnostic_cards(
    user_id: str = Query(...),
    limit: int = Query(default=20, le=50),
):
    """获取用户的诊断卡片列表。

    从 knowledge_stages 取 stage ≤ 2 且有 evidence 的概念，
    按 last_updated 降序排列。附带教材出处信息。
    """
    from app.db.connection import get_conn
    from app.db.textbook_section_db import parse_source_code

    conn = get_conn()
    try:
        rows = conn.execute(
            """
            SELECT concept_name, stage, confidence, evidence, last_updated
            FROM knowledge_stages
            WHERE user_id=? AND stage IS NOT NULL AND stage <= 2
              AND evidence IS NOT NULL AND evidence != '[]'
            ORDER BY last_updated DESC
            LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()

        cards = []
        for row in rows:
            evidence_list = []
            try:
                evidence_list = json.loads(row["evidence"] or "[]")
            except (json.JSONDecodeError, TypeError):
                pass

            # 取最新一条 evidence
            latest = evidence_list[-1] if evidence_list else {}

            # 查询 KG 获取 source_code 和 evidence_span
            source_code = ""
            evidence_span = ""
            rule_cases = []
            try:
                from app.db.kg_v44 import find_node, get_rule_cases_for_node

                node = find_node(row["concept_name"])
                if node:
                    source_code = node.get("source_code") or ""
                    evidence_span = node.get("evidence_span") or ""
                    # 查询规则案例
                    if node.get("node_id"):
                        cases = get_rule_cases_for_node(row["concept_name"], limit=3)
                        rule_cases = [
                            {
                                "name": c.get("rule_case", ""),
                                "owner": c.get("owner_name", ""),
                                "applies_to": c.get("applies_to", []),
                                "condition_logic": c.get("condition_logic", ""),
                                "conditions": c.get("conditions", []),
                                "outcomes": c.get("outcomes", []),
                            }
                            for c in cases
                        ]
            except Exception:
                pass

            source_info = parse_source_code(source_code) if source_code else {}

            cards.append({
                "concept_name": row["concept_name"],
                "stage": row["stage"],
                "confidence": row["confidence"],
                "evidence_quote": latest.get("quote", ""),
                "diagnosis": latest.get("diagnosis", ""),
                "evidence_count": len(evidence_list),
                "last_updated": row["last_updated"],
                "source_code": source_code,
                "source_display": source_info.get("display", ""),
                "textbook_name": source_info.get("textbook_name", ""),
                "evidence_span": evidence_span[:300] if evidence_span else "",
                "rule_cases": rule_cases,
            })

        return {"cards": cards}
    finally:
        conn.close()


@router.get("/knowledge-graph")
def get_knowledge_graph_v44(authorization: Optional[str] = Header(None)):
    """Return weak concepts plus v4.4 KG support/extension neighbors."""
    user_id = get_user_id_from_token(authorization)
    if not user_id:
        raise HTTPException(status_code=401, detail="未登录或token无效")

    from app.db.knowledge_stages_db import get_stages_batch
    from app.config import config

    weak_names = []
    try:
        import sqlite3
        conn = sqlite3.connect(config.DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT concept_name, stage
            FROM knowledge_stages
            WHERE user_id=? AND stage IS NOT NULL AND stage <= 2
            ORDER BY stage ASC
            LIMIT 5
            """,
            (user_id,),
        )
        weak_names = [(row[0], row[1]) for row in cursor.fetchall()]
        conn.close()
    except Exception:
        pass

    if not weak_names:
        return {"user_id": user_id, "weak_concepts": []}

    try:
        from app.db.kg_v44 import find_node, related_nodes

        result = []
        for concept_name, concept_stage in weak_names:
            matched = find_node(concept_name)
            if not matched:
                continue

            support_nodes, extension_nodes = related_nodes(matched["name"], limit=5)
            support_names = [n["name"] for n in support_nodes if n.get("name")]
            extension_names = [n["name"] for n in extension_nodes if n.get("name")]
            all_needs = [concept_name] + support_names + extension_names
            stages = get_stages_batch(user_id, all_needs)
            stage_map = {s["concept_name"]: s["stage"] for s in stages}

            def make_node(name):
                stage = stage_map.get(name)
                return {
                    "name": name,
                    "stage": stage,
                    "stage_label": STAGE_LABELS.get(stage, "未知") if stage is not None else "未知",
                }

            result.append({
                "name": concept_name,
                "neo4j_name": matched["name"] if matched["name"] != concept_name else None,
                "stage": concept_stage,
                "stage_label": STAGE_LABELS.get(concept_stage, "未知"),
                "prerequisites": [make_node(name) for name in support_names],
                "dependents": [make_node(name) for name in extension_names],
            })

        return {"user_id": user_id, "weak_concepts": result}

    except Exception as e:
        print(f"[KnowledgeGraph] v4.4 KG query failed: {e}")
        return {"user_id": user_id, "weak_concepts": [], "error": str(e)}



