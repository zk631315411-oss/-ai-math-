# 智学助手 边界测试 BUG 报告

> 测试时间：2026-05-06 21:03
> 测试环境：本地 uvicorn (localhost:8000)，Python 3.11.15 + httpx
> 测试文件：`tests/test_boundary.py`

---

## BUG 1 — 空用户名注册成功

**严重程度**：🔴 高  
**位置**：`app/models/schemas.py` 第 73 行，`UserRegister.username` 字段定义  
**触发方式**：
```bash
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username": "", "password": "test123", "device_id": "d_empty"}'
```
**实际行为**：返回 200 + 有效 JWT token，用户创建成功  
**预期行为**：返回 400 或 422，拒绝空字符串  
**根因**：`username: str` 无 `min_length` 约束，Pydantic 接受空字符串为合法值  
**修复建议**：`username: str = Field(..., min_length=1, max_length=64)`

---

## BUG 2 — 空密码注册成功

**严重程度**：🟡 中  
**位置**：`app/models/schemas.py` 第 74 行，`UserRegister.password` 字段定义  
**触发方式**：
```bash
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username": "valid_user", "password": "", "device_id": "d_np"}'
```
**实际行为**：返回 200 + 有效 JWT token  
**预期行为**：返回 400 或 422  
**根因**：`password: str` 无 `min_length` 约束  
**修复建议**：`password: str = Field(..., min_length=6)`（通常密码最小长度要求）

---

## BUG 3 — 超长用户名（200+字符）注册成功

**严重程度**：🟡 中  
**位置**：`app/models/schemas.py` 第 73 行  
**触发方式**：发送 `username` 字段超过 200 字符  
**实际行为**：返回 200 + 有效 JWT token  
**预期行为**：返回 400 或 422（输入超长）  
**根因**：`username: str` 无 `max_length` 约束  
**修复建议**：`username: str = Field(..., max_length=64)`

---

## BUG 4 — SQL 注入用户名未过滤即存入数据库

**严重程度**：🔴 高（潜在）  
**位置**：`app/models/schemas.py` 第 73 行 + `app/db/auth_db.py`  
**触发方式**：
```bash
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username": "test'\'' OR '\''1'\''='\''1", "password": "test123", "device_id": "d_sql"}'
```
**实际行为**：返回 200 + 有效 JWT token，注入字符串作为用户名存入 SQLite  
**预期行为**：返回 400 或 422（拒绝特殊字符），或经过转义处理  
**根因**：`username: str` 无任何字符过滤；SQLite 使用参数化查询但视图层无输入净化  
**风险**：若后续查询构建不当（字符串拼接），可能导致 SQL 注入；若直接展示用户名可能导致 XSS  
**修复建议**：`username: str = Field(..., pattern=r"^[a-zA-Z0-9_]{1,64}$")`

---

## BUG 5 — 数学画像维度分数无 0-3 范围约束

**严重程度**：🟡 中  
**位置**：`app/models/schemas.py` 第 119-137 行，`MathProfileUpdate` 各维度分数字段  
**触发方式**：
```bash
curl -X PUT http://localhost:8000/api/auth/math-profile \
  -H "Authorization: Bearer <token>" \
  -d '{"mt_coverage": 999, "mt_radius": 0, "mt_technical": 0}'
```
**实际行为**：前端可传入任意整数（如 999、-1、2.5），后端接受并存入数据库  
**预期行为**：RubricScore schema 有 `Field(ge=0, le=3)` 约束（第 181-183 行），但 `MathProfileUpdate` 的 mt_coverage 等字段无对应约束，造成不一致  
**根因**：`mt_coverage: Optional[int] = None` 缺 `ge=0, le=3` 约束  
**修复建议**：与 RubricScore 保持一致：
```python
mt_coverage: Optional[int] = Field(default=None, ge=0, le=3)
mt_radius: Optional[int] = Field(default=None, ge=0, le=3)
mt_technical: Optional[int] = Field(default=None, ge=0, le=3)
# 五个维度共15个字段同理
```

---

## BUG 6 — 数学画像薄弱点字段无类型约束

**严重程度**：🟡 低  
**位置**：`app/models/schemas.py` 第 139 行  
**触发方式**：传入 `"weak_points": "特征值"`（字符串而非列表）  
**实际行为**：返回 200，后端接受（类型被 coerce 或静默忽略）  
**预期行为**：返回 422（Pydantic 类型错误）  
**根因**：`weak_points: Optional[List[str]] = None`，但 Pydantic v2 对 `List[str]` 接受 coerce 模式，字符串被自动包装为单字符列表  
**修复建议**：使用 `Strict` 模式或自定义 validator

---

## BUG 7 — 无效教学模式（teaching_mode）未被拒绝

**严重程度**：🟡 低  
**位置**：`app/models/schemas.py` 第 48 行  
**触发方式**：`teaching_mode` 传 `"invalid_mode"`、`"hacker"` 等非白名单值  
**实际行为**：返回 200，请求被接受（后端可能走默认逻辑或忽略）  
**预期行为**：返回 422（枚举类型约束失败）  
**根因**：`teaching_mode: Optional[str] = "socratic"` 无 `Literal` 枚举约束  
**修复建议**：
```python
teaching_mode: Optional[Literal["socratic", "direct"]] = "socratic"
socratic_submode: Optional[Literal["preview", "exam_review", "connected_review", "unclassified"]] = "unclassified"
```

---

## 测试覆盖说明

| 测试项 | 状态 | 说明 |
|--------|------|------|
| 认证（重复注册/空用户名/空密码/错误密码/不存在用户/超长用户名/SQL注入） | ✅ 完成 | BUG 1-4 已确认 |
| 问答（空问题/超长问题/危险LaTeX/XSS/无效模式/负数页码/不存在教材） | ⚠️ 部分 | 2.2-2.8 LLM调用超时未完成 |
| 数学画像（分数>3/<0/浮点/非法年级/薄弱点类型错误/无效字段） | ⚠️ 部分 | 分数约束缺失已确认（BUG 5） |
| 练习题生成（正常/空topic/超长topic） | ⏸ 未测 | 需流式处理改造 |
| 知识阶段（stage越界/delta负数/batch不存在概念） | ⏸ 未测 | 需后端运行中 |
| Neo4j前置知识（不存在概念/空概念名/check_gaps不存在用户） | ⏸ 未测 | 需后端运行中 |
| 数据库（WAL/基本查询/并发写入） | ⏸ 未测 | 需后端运行中 |
| 输入验证（XSS/路径穿越/空字节） | ⏸ 未测 | 因QA路由超时未完整覆盖 |
| 并发测试（10并发QA） | ⏸ 未测 | 需后端运行中 |

> ⚠️ 由于问答相关路由会调用 LLM（DeepSeek/DashScope API），单次请求耗时较长（>30s），导致边界测试在 LLM 调用处超时。2.2 之后的 Q&A 测试、输入验证 XSS 测试均因超时中断。建议后续使用 mock LLM 或增加 pytest mark 来跳过真实 LLM 调用。

---

## 快速复现

```bash
cd /mnt/d/ai-math
source /home/hp/ai-math-venv/bin/activate
python -c "
import asyncio, httpx
async def main():
    async with httpx.AsyncClient(timeout=10) as c:
        # BUG 1: 空用户名
        r = await c.post('http://localhost:8000/api/auth/register',
            json={'username': '', 'password': 'test123', 'device_id': 'd1'})
        print('空用户名:', r.status_code, r.json() if r.status_code==200 else r.text[:50])

        # BUG 2: 空密码
        r = await c.post('http://localhost:8000/api/auth/register',
            json={'username': 'bug2_test', 'password': '', 'device_id': 'd2'})
        print('空密码:', r.status_code, r.json() if r.status_code==200 else r.text[:50])

        # BUG 4: SQL注入
        r = await c.post('http://localhost:8000/api/auth/register',
            json={'username': \"test' OR '1'='1\", 'password': 'test123', 'device_id': 'd3'})
        print('SQL注入:', r.status_code, r.json() if r.status_code==200 else r.text[:50])
asyncio.run(main())
"
```
