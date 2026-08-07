import sqlite3
from app.config import config


def get_conn():
    conn = sqlite3.connect(config.DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=10000")
    return conn


def init_db():
    conn = get_conn()
    cursor = conn.cursor()

    # WAL 模式：多读一写并发，reader 与 writer 互不阻塞
    journal_mode = config.DB_JOURNAL_MODE
    if journal_mode not in {"WAL", "DELETE"}:
        journal_mode = "WAL"
    cursor.execute(f"PRAGMA journal_mode={journal_mode}")

    # 用户基本信息表（user_profiles）
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_profiles (
            user_id TEXT PRIMARY KEY,
            grade TEXT,
            weak_points TEXT DEFAULT '[]',
            strong_points TEXT DEFAULT '[]',
            learning_preferences TEXT DEFAULT '{}',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # 教材表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS textbooks (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            subject TEXT NOT NULL,
            grade TEXT NOT NULL,
            chapters TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 问答历史表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat_history (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            sources TEXT,
            knowledge_points TEXT,
            page_number INTEGER,
            marker_y_ratio REAL,
            marker_type TEXT DEFAULT 'screenshot',
            thumbnail TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Phase 2: 给旧 chat_history 表补字段
    for col, col_type in [
        ("page_number", "INTEGER"),
        ("marker_y_ratio", "REAL"),
        ("marker_type", "TEXT DEFAULT 'screenshot'"),
        ("thumbnail", "TEXT"),
        ("thinking", "TEXT"),
        ("follow_ups", "TEXT DEFAULT '[]'"),
        ("crop_bbox", "TEXT"),
        ("screenshot_context_id", "TEXT"),
    ]:
        try:
            cursor.execute(f"ALTER TABLE chat_history ADD COLUMN {col} {col_type}")
        except Exception:
            pass

    # 用户账号表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            device_id TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 数学素养画像表（多维度评价体系）
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS math_profiles (
            user_id TEXT PRIMARY KEY,
            grade TEXT,
            mt_coverage INTEGER DEFAULT 0,
            mt_radius INTEGER DEFAULT 0,
            mt_technical INTEGER DEFAULT 0,
            lr_coverage INTEGER DEFAULT 0,
            lr_radius INTEGER DEFAULT 0,
            lr_technical INTEGER DEFAULT 0,
            so_coverage INTEGER DEFAULT 0,
            so_radius INTEGER DEFAULT 0,
            so_technical INTEGER DEFAULT 0,
            mr_coverage INTEGER DEFAULT 0,
            mr_radius INTEGER DEFAULT 0,
            mr_technical INTEGER DEFAULT 0,
            ps_coverage INTEGER DEFAULT 0,
            ps_radius INTEGER DEFAULT 0,
            ps_technical INTEGER DEFAULT 0,
            weak_points TEXT DEFAULT '[]',
            latest_diagnostic_report TEXT DEFAULT '{}',
            last_diagnosed_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # 为 math_profiles 添加教材偏好字段（如不存在则添加）
    try:
        cursor.execute("ALTER TABLE math_profiles ADD COLUMN last_textbook_id TEXT")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE math_profiles ADD COLUMN last_page_number INTEGER DEFAULT 1")
    except Exception:
        pass

    # 提问历史扩展表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS question_assessments (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            question_id TEXT NOT NULL,
            mt_coverage INTEGER, mt_radius INTEGER, mt_technical INTEGER,
            lr_coverage INTEGER, lr_radius INTEGER, lr_technical INTEGER,
            so_coverage INTEGER, so_radius INTEGER, so_technical INTEGER,
            mr_coverage INTEGER, mr_radius INTEGER, mr_technical INTEGER,
            ps_coverage INTEGER, ps_radius INTEGER, ps_technical INTEGER,
            overall_score REAL,
            weak_points TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # 用户知识点统计表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_knowledge_stats (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            topic TEXT NOT NULL,
            consecutive_turns INTEGER DEFAULT 1,
            total_asks INTEGER DEFAULT 1,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_stats_user_topic ON user_knowledge_stats(user_id, topic)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_chat_history_user_id ON chat_history(user_id)
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS screenshot_context_cache (
            id TEXT PRIMARY KEY,
            user_id TEXT,
            image_hash TEXT NOT NULL,
            textbook_id TEXT NOT NULL,
            page_number INTEGER NOT NULL,
            crop_bbox TEXT,
            crop_bbox_hash TEXT,
            full_context_hash TEXT,
            pdf_crop_path TEXT,
            md_match_status TEXT,
            md_match_confidence REAL,
            md_match_text TEXT,
            locator_signals TEXT,
            vision_summary TEXT,
            vision_extraction TEXT,
            extraction_version TEXT,
            vision_model TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    for column, definition in (
        ("user_id", "TEXT"),
        ("vision_extraction", "TEXT"),
        ("extraction_version", "TEXT"),
    ):
        try:
            cursor.execute(f"ALTER TABLE screenshot_context_cache ADD COLUMN {column} {definition}")
        except Exception:
            pass

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_screenshot_cache_lookup
        ON screenshot_context_cache(image_hash, textbook_id, page_number, crop_bbox_hash, full_context_hash)
    """)

    # 教材章节页码映射表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS textbook_sections (
            id TEXT PRIMARY KEY,
            textbook_id TEXT NOT NULL,
            sequence_id TEXT NOT NULL,
            chapter_num TEXT NOT NULL,
            chapter_name TEXT NOT NULL,
            content TEXT NOT NULL,
            start_page INTEGER NOT NULL,
            end_page INTEGER NOT NULL
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_sections_pages
        ON textbook_sections(textbook_id, start_page, end_page)
    """)

    # 诊断用对话日志表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat_logs (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            sequence_id TEXT NOT NULL,
            question TEXT NOT NULL,
            answer TEXT,
            sources TEXT,
            is_analyzed INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    try:
        cursor.execute("ALTER TABLE chat_logs ADD COLUMN is_analyzed INTEGER DEFAULT 0")
    except Exception:
        pass

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_chat_logs_analyzed ON chat_logs(user_id, is_analyzed)
    """)

    # QA 模块事实记录表：保存每轮回答的完整结构化上下文。
    # chat_history 面向前端展示，chat_logs 面向旧诊断 worker；本表面向 QA 复盘和后续模块消费。
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS qa_turn_records (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            chat_id TEXT,
            marker_id TEXT,
            input_type TEXT NOT NULL,
            question TEXT NOT NULL,
            answer TEXT,
            textbook_id TEXT,
            page_number INTEGER,
            sequence_id TEXT,
            section_node_id TEXT,
            chapter_name TEXT,
            sources TEXT,
            context_snapshot TEXT,
            messages_snapshot TEXT,
            model_name TEXT,
            prompt_preview TEXT,
            image_hash TEXT,
            crop_bbox TEXT,
            screenshot_context_id TEXT,
            latency_ms INTEGER,
            error TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    try:
        cursor.execute("ALTER TABLE qa_turn_records ADD COLUMN marker_id TEXT")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE qa_turn_records ADD COLUMN apprenticeship_level TEXT")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE qa_turn_records ADD COLUMN applied_directive_id TEXT")
    except Exception:
        pass
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_qa_turn_records_user_time
        ON qa_turn_records(user_id, created_at)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_qa_turn_records_sequence
        ON qa_turn_records(sequence_id)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_qa_turn_records_marker
        ON qa_turn_records(marker_id)
    """)

    # Migration: add sequence_id / summary columns to question_assessments if missing
    try:
        cursor.execute("ALTER TABLE question_assessments ADD COLUMN sequence_id TEXT")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE question_assessments ADD COLUMN summary TEXT")
    except Exception:
        pass

    # === Phase 2: 六阶段认知语言 ===
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS knowledge_stages (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            concept_name TEXT NOT NULL,
            stage INTEGER DEFAULT NULL,
            confidence REAL NOT NULL DEFAULT 0.3,
            evidence TEXT DEFAULT '[]',
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, concept_name)
        )
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_ks_user_stage ON knowledge_stages(user_id, stage)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_ks_user_concept ON knowledge_stages(user_id, concept_name)
    """)

    # Phase 2: 画像洞察缓存
    try:
        cursor.execute("ALTER TABLE math_profiles ADD COLUMN insight_cache TEXT DEFAULT '{}'")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE math_profiles ADD COLUMN insight_generated_at TIMESTAMP")
    except Exception:
        pass

    # Phase 2: 题库
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS exercise_bank (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            topic TEXT NOT NULL,
            difficulty TEXT NOT NULL,
            target_stage INTEGER NOT NULL,
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            verification TEXT,
            hints TEXT DEFAULT '[]',
            computable TEXT DEFAULT '{}',
            hint_level INTEGER DEFAULT 0,
            source_chat_id TEXT,
            is_answered INTEGER DEFAULT 0,
            student_answer TEXT,
            is_correct INTEGER,
            error_analysis TEXT,
            quality_score INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_exercise_user_topic ON exercise_bank(user_id, topic)
    """)

    # v2.4 迁移：加 source 和 sequence_id 列
    for col, defn in [("source", "TEXT DEFAULT 'llm'"), ("sequence_id", "TEXT DEFAULT ''")]:
        try:
            cursor.execute(f"ALTER TABLE exercise_bank ADD COLUMN {col} {defn}")
        except Exception:
            pass

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_exercise_seq_stage ON exercise_bank(sequence_id, target_stage)
    """)

    # Per-user mutable state. exercise_bank rows are immutable question templates.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS exercise_user_state (
            user_id TEXT NOT NULL,
            exercise_id TEXT NOT NULL,
            hint_level INTEGER NOT NULL DEFAULT 0,
            is_answered INTEGER NOT NULL DEFAULT 0,
            student_answer TEXT,
            is_correct INTEGER,
            grading_feedback TEXT DEFAULT '',
            grading_status TEXT NOT NULL DEFAULT 'not_submitted',
            error_analysis TEXT DEFAULT '{}',
            latest_attempt_id TEXT,
            reported_error INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, exercise_id)
        )
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_exercise_state_user_updated
        ON exercise_user_state(user_id, updated_at)
    """)

    # Phase 2: pending 更新队列
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pending_stage_updates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            concept_name TEXT NOT NULL,
            delta_value INTEGER,
            override_stage INTEGER,
            confidence_adjustment REAL DEFAULT 0,
            source TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_psu_user_concept ON pending_stage_updates(user_id, concept_name)
    """)

    # === 认知诊断 V2：分源评分、统一证据账本、可审计投影 ===
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS exercise_attempts (
            id TEXT PRIMARY KEY,
            exercise_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            sequence_id TEXT DEFAULT '',
            target_concept TEXT DEFAULT '',
            target_stage INTEGER,
            difficulty TEXT DEFAULT '',
            question TEXT NOT NULL,
            student_answer TEXT NOT NULL,
            correct_answer TEXT NOT NULL,
            is_correct INTEGER NOT NULL,
            hint_level INTEGER NOT NULL DEFAULT 0,
            grading_feedback TEXT DEFAULT '',
            error_analysis TEXT DEFAULT '{}',
            analysis_status TEXT NOT NULL DEFAULT 'ready',
            grading_status TEXT NOT NULL DEFAULT 'valid',
            grader_version TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_attempt_user_seq ON exercise_attempts(user_id, sequence_id, created_at)")
    for col, definition in (
        ("analysis_status", "TEXT NOT NULL DEFAULT 'ready'"),
        ("grading_status", "TEXT NOT NULL DEFAULT 'valid'"),
    ):
        try:
            cursor.execute(f"ALTER TABLE exercise_attempts ADD COLUMN {col} {definition}")
        except Exception:
            pass

    # Exercise v2: conversation-driven practice drafts and immutable item/attempt records.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS exercise_items (
            id TEXT PRIMARY KEY,
            textbook_id TEXT NOT NULL DEFAULT '',
            source_locator TEXT NOT NULL DEFAULT '',
            sequence_id TEXT NOT NULL DEFAULT '',
            concept_ids TEXT NOT NULL DEFAULT '[]',
            question_type TEXT NOT NULL CHECK(question_type IN ('calculation','concept','proof')),
            target_stage INTEGER NOT NULL DEFAULT 1 CHECK(target_stage BETWEEN 0 AND 5),
            difficulty TEXT NOT NULL DEFAULT 'basic',
            question TEXT NOT NULL,
            answer_spec TEXT NOT NULL DEFAULT '{}',
            hints TEXT NOT NULL DEFAULT '[]',
            rubric TEXT NOT NULL DEFAULT '[]',
            source TEXT NOT NULL DEFAULT 'textbook',
            trust_status TEXT NOT NULL DEFAULT 'teacher_approved'
                CHECK(trust_status IN ('teacher_approved','machine_verified','machine_reviewed')),
            owner_user_id TEXT,
            generation_model TEXT NOT NULL DEFAULT '',
            reviewer_model TEXT NOT NULL DEFAULT '',
            prompt_version TEXT NOT NULL DEFAULT '',
            context_hash TEXT NOT NULL DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_exercise_items_scope ON exercise_items(textbook_id, sequence_id, target_stage)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_exercise_items_concepts ON exercise_items(concept_ids)")
    # Textbook-first item metadata.  These additive columns keep existing
    # databases readable while separating item provenance from runtime use.
    existing_item_columns = {row[1] for row in cursor.execute("PRAGMA table_info(exercise_items)").fetchall()}
    for col, definition in {
        "item_kind": "TEXT NOT NULL DEFAULT 'exercise_item'",
        "concept_names": "TEXT NOT NULL DEFAULT '[]'",
        "prerequisite_concept_ids": "TEXT NOT NULL DEFAULT '[]'",
        "prerequisite_concept_names": "TEXT NOT NULL DEFAULT '[]'",
        "primary_concept_id": "TEXT NOT NULL DEFAULT ''",
        "primary_concept_name": "TEXT NOT NULL DEFAULT ''",
        "secondary_concept_ids": "TEXT NOT NULL DEFAULT '[]'",
        "stage_rationale": "TEXT NOT NULL DEFAULT ''",
        "literacy_tags": "TEXT NOT NULL DEFAULT '[]'",
        "stem_source": "TEXT NOT NULL DEFAULT 'textbook'",
        "solution_source": "TEXT NOT NULL DEFAULT 'textbook'",
        "solution_review_status": "TEXT NOT NULL DEFAULT 'unreviewed'",
        "source_hash": "TEXT NOT NULL DEFAULT ''",
        "parent_item_id": "TEXT",
        "source_asset_id": "TEXT NOT NULL DEFAULT ''",
        "original_textbook_name": "TEXT NOT NULL DEFAULT ''",
        "source_page": "INTEGER",
        "source_problem_no": "TEXT NOT NULL DEFAULT ''",
        "source_subitem_no": "TEXT",
        "stem_review_status": "TEXT NOT NULL DEFAULT 'unreviewed'",
        "review_status": "TEXT NOT NULL DEFAULT 'draft_subject_review'",
        "diagnostic_goal": "TEXT NOT NULL DEFAULT 'application'",
        "kg_mapping_status": "TEXT NOT NULL DEFAULT 'unverified'",
    }.items():
        if col not in existing_item_columns:
            cursor.execute(f"ALTER TABLE exercise_items ADD COLUMN {col} {definition}")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_exercise_items_primary_concept ON exercise_items(primary_concept_id, target_stage)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_exercise_items_kind ON exercise_items(item_kind, trust_status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_exercise_items_mvp_goal ON exercise_items(textbook_id, diagnostic_goal, trust_status)")
    cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_exercise_items_source_asset ON exercise_items(source_asset_id) WHERE source_asset_id<>''")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS practice_drafts (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            turn_id TEXT NOT NULL,
            tree_id TEXT DEFAULT '',
            node_id TEXT DEFAULT '',
            textbook_id TEXT NOT NULL DEFAULT '',
            sequence_id TEXT NOT NULL DEFAULT '',
            concept_ids TEXT NOT NULL DEFAULT '[]',
            trigger_kind TEXT NOT NULL DEFAULT 'agent_recommended',
            intervention_goal TEXT NOT NULL DEFAULT '',
            evidence_quote TEXT NOT NULL DEFAULT '',
            selection_reason TEXT NOT NULL DEFAULT '',
            context_snapshot TEXT NOT NULL DEFAULT '{}',
            context_hash TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'queued'
                CHECK(status IN ('queued','running','ready','partial','failed','stale','cancelled')),
            auto_prepared INTEGER NOT NULL DEFAULT 1,
            version INTEGER NOT NULL DEFAULT 1,
            parent_draft_id TEXT,
            error TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # Only an active draft is idempotent. Failed/stale drafts may be retried as
    # a new immutable version without overwriting their audit trail.
    cursor.execute("DROP INDEX IF EXISTS uq_practice_draft_active")
    cursor.execute("""CREATE UNIQUE INDEX IF NOT EXISTS uq_practice_draft_active
                      ON practice_drafts(user_id, turn_id, context_hash)
                      WHERE status IN ('queued','running','ready','partial')""")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_practice_drafts_user_status ON practice_drafts(user_id, status, updated_at)")
    try:
        cursor.execute("ALTER TABLE practice_drafts ADD COLUMN intervention_action_id TEXT")
    except Exception:
        pass
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_practice_drafts_intervention "
        "ON practice_drafts(intervention_action_id)"
    )

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS practice_draft_items (
            draft_id TEXT NOT NULL,
            item_id TEXT NOT NULL,
            branch_role TEXT NOT NULL CHECK(branch_role IN ('diagnostic','remedial','verify','advance')),
            rank INTEGER NOT NULL DEFAULT 0,
            reason TEXT NOT NULL DEFAULT '',
            PRIMARY KEY (draft_id, item_id),
            FOREIGN KEY (draft_id) REFERENCES practice_drafts(id),
            FOREIGN KEY (item_id) REFERENCES exercise_items(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS practice_sessions (
            id TEXT PRIMARY KEY,
            draft_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            current_item_id TEXT,
            item_count INTEGER NOT NULL DEFAULT 0,
            completed_count INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','completed','inconclusive','abandoned')),
            summary TEXT NOT NULL DEFAULT '{}',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (draft_id) REFERENCES practice_drafts(id)
        )
    """)
    session_sql = cursor.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='practice_sessions'"
    ).fetchone()
    if session_sql and "inconclusive" not in str(session_sql[0]):
        # SQLite cannot alter a CHECK constraint in place. Preserve all
        # existing rows while rebuilding this small state table.
        cursor.execute("PRAGMA foreign_keys=OFF")
        cursor.execute("""
            CREATE TABLE practice_sessions_v2 (
                id TEXT PRIMARY KEY,
                draft_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                current_item_id TEXT,
                item_count INTEGER NOT NULL DEFAULT 0,
                completed_count INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'active'
                    CHECK(status IN ('active','completed','inconclusive','abandoned')),
                summary TEXT NOT NULL DEFAULT '{}',
                outcome_status TEXT NOT NULL DEFAULT 'undetermined',
                mastery_verified INTEGER NOT NULL DEFAULT 0,
                selection_decision TEXT NOT NULL DEFAULT '{}',
                ungradable_retries INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (draft_id) REFERENCES practice_drafts(id)
            )
        """)
        cursor.execute("""
            INSERT INTO practice_sessions_v2
            (id,draft_id,user_id,current_item_id,item_count,completed_count,status,summary,created_at,updated_at)
            SELECT id,draft_id,user_id,current_item_id,item_count,completed_count,status,summary,created_at,updated_at
            FROM practice_sessions
        """)
        cursor.execute("DROP TABLE practice_sessions")
        cursor.execute("ALTER TABLE practice_sessions_v2 RENAME TO practice_sessions")
        cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_practice_sessions_user ON practice_sessions(user_id, updated_at)")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS practice_attempts (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            draft_id TEXT NOT NULL,
            item_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            student_answer TEXT NOT NULL,
            verdict TEXT NOT NULL CHECK(verdict IN ('correct','partial','incorrect','ungradable')),
            evidence_quotes TEXT NOT NULL DEFAULT '[]',
            rubric_findings TEXT NOT NULL DEFAULT '[]',
            feedback TEXT NOT NULL DEFAULT '',
            error_analysis TEXT NOT NULL DEFAULT '{}',
            hint_level INTEGER NOT NULL DEFAULT 0,
            next_item_id TEXT,
            next_reason TEXT NOT NULL DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES practice_sessions(id),
            FOREIGN KEY (draft_id) REFERENCES practice_drafts(id),
            FOREIGN KEY (item_id) REFERENCES exercise_items(id)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_practice_attempts_user ON practice_attempts(user_id, created_at)")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS practice_hint_events (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            item_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            hint_level INTEGER NOT NULL CHECK(hint_level BETWEEN 1 AND 3),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES practice_sessions(id),
            FOREIGN KEY (item_id) REFERENCES exercise_items(id)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_practice_hints_session ON practice_hint_events(session_id, item_id, created_at)")
    existing_session_columns = {row[1] for row in cursor.execute("PRAGMA table_info(practice_sessions)").fetchall()}
    for col, definition in {
        "outcome_status": "TEXT NOT NULL DEFAULT 'undetermined'",
        "mastery_verified": "INTEGER NOT NULL DEFAULT 0",
        "selection_decision": "TEXT NOT NULL DEFAULT '{}'",
        "ungradable_retries": "INTEGER NOT NULL DEFAULT 0",
    }.items():
        if col not in existing_session_columns:
            cursor.execute(f"ALTER TABLE practice_sessions ADD COLUMN {col} {definition}")
    existing_attempt_columns = {row[1] for row in cursor.execute("PRAGMA table_info(practice_attempts)").fetchall()}
    for col, definition in {
        "counts_toward_limit": "INTEGER NOT NULL DEFAULT 1",
        "selection_decision": "TEXT NOT NULL DEFAULT '{}'",
    }.items():
        if col not in existing_attempt_columns:
            cursor.execute(f"ALTER TABLE practice_attempts ADD COLUMN {col} {definition}")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS exercise_agent_jobs (
            id TEXT PRIMARY KEY,
            draft_id TEXT NOT NULL,
            task_kind TEXT NOT NULL CHECK(task_kind IN ('plan','author','review')),
            branch_role TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'queued'
                CHECK(status IN ('queued','running','ready','failed','cancelled')),
            payload TEXT NOT NULL DEFAULT '{}',
            result TEXT NOT NULL DEFAULT '{}',
            attempts INTEGER NOT NULL DEFAULT 0,
            worker_id TEXT,
            lease_until TIMESTAMP,
            error TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (draft_id) REFERENCES practice_drafts(id)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_exercise_agent_jobs_status ON exercise_agent_jobs(status, created_at)")
    existing_job_columns = {row[1] for row in cursor.execute("PRAGMA table_info(exercise_agent_jobs)").fetchall()}
    for col, definition in {
        "worker_id": "TEXT",
        "lease_until": "TIMESTAMP",
    }.items():
        if col not in existing_job_columns:
            cursor.execute(f"ALTER TABLE exercise_agent_jobs ADD COLUMN {col} {definition}")

    # Diagnosis snapshots and the bounded teaching-controller control plane.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS diagnostic_signals (
            id TEXT PRIMARY KEY,
            source_type TEXT NOT NULL CHECK(source_type IN ('qa_turn','exercise_attempt')),
            source_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            sequence_id TEXT NOT NULL DEFAULT '',
            signal_type TEXT NOT NULL,
            concept_ids TEXT NOT NULL DEFAULT '[]',
            student_quote TEXT NOT NULL,
            confidence REAL NOT NULL CHECK(confidence BETWEEN 0 AND 1),
            strength TEXT NOT NULL CHECK(strength IN ('certain','probable','hypothesis')),
            rationale TEXT NOT NULL DEFAULT '',
            scorer_version TEXT NOT NULL DEFAULT 'v2',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(source_type, source_id, signal_type, student_quote, scorer_version)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_diagnostic_signals_user ON diagnostic_signals(user_id, created_at)")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS diagnosis_snapshots (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            source_type TEXT NOT NULL,
            source_id TEXT NOT NULL,
            tree_id TEXT NOT NULL DEFAULT '',
            node_id TEXT NOT NULL DEFAULT '',
            textbook_id TEXT NOT NULL DEFAULT '',
            sequence_id TEXT NOT NULL DEFAULT '',
            concept_ids TEXT NOT NULL DEFAULT '[]',
            state_payload TEXT NOT NULL DEFAULT '{}',
            signal_ids TEXT NOT NULL DEFAULT '[]',
            version INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(source_type, source_id)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_diagnosis_snapshots_scope ON diagnosis_snapshots(user_id, tree_id, node_id, created_at)")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tutor_directives (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            snapshot_id TEXT,
            source_turn_id TEXT NOT NULL DEFAULT '',
            tree_id TEXT NOT NULL DEFAULT '',
            node_id TEXT NOT NULL DEFAULT '',
            sequence_id TEXT NOT NULL DEFAULT '',
            concept_ids TEXT NOT NULL DEFAULT '[]',
            teaching_goal TEXT NOT NULL DEFAULT '',
            qa_policy TEXT NOT NULL DEFAULT '{}',
            action TEXT NOT NULL CHECK(action IN ('no_action','adjust_qa','offer_practice_entry','prepare_practice')),
            evidence_refs TEXT NOT NULL DEFAULT '[]',
            confidence REAL NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('shadow','active','applied','expired','stale')),
            context_version TEXT NOT NULL DEFAULT '',
            model_name TEXT NOT NULL DEFAULT '',
            prompt_version TEXT NOT NULL DEFAULT '',
            applied_turn_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(snapshot_id) REFERENCES diagnosis_snapshots(id)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tutor_directives_scope ON tutor_directives(user_id, tree_id, node_id, status, created_at)")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS intervention_actions (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            directive_id TEXT,
            turn_id TEXT NOT NULL,
            node_id TEXT NOT NULL DEFAULT '',
            action_type TEXT NOT NULL CHECK(action_type IN ('offer_practice_entry','prepare_practice')),
            trigger_kind TEXT NOT NULL CHECK(trigger_kind IN ('explicit_button','agent_recommended','text_request')),
            payload TEXT NOT NULL DEFAULT '{}',
            status TEXT NOT NULL DEFAULT 'queued' CHECK(status IN ('queued','running','ready','failed','stale','cancelled')),
            draft_id TEXT,
            error TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(directive_id) REFERENCES tutor_directives(id)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_intervention_actions_turn ON intervention_actions(user_id, turn_id, created_at)")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS intervention_agent_jobs (
            id TEXT PRIMARY KEY,
            snapshot_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'queued' CHECK(status IN ('queued','running','ready','failed','cancelled')),
            payload TEXT NOT NULL DEFAULT '{}',
            result TEXT NOT NULL DEFAULT '{}',
            attempts INTEGER NOT NULL DEFAULT 0,
            worker_id TEXT,
            lease_until TIMESTAMP,
            error TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(snapshot_id),
            FOREIGN KEY(snapshot_id) REFERENCES diagnosis_snapshots(id)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_intervention_jobs_status ON intervention_agent_jobs(status, created_at)")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS diagnosis_runs (
            id TEXT PRIMARY KEY,
            source_type TEXT NOT NULL,
            source_id TEXT NOT NULL,
            scorer_type TEXT NOT NULL,
            scorer_version TEXT NOT NULL,
            status TEXT NOT NULL,
            model_name TEXT DEFAULT '',
            prompt_version TEXT DEFAULT '',
            raw_output TEXT DEFAULT '',
            error_reason TEXT DEFAULT '',
            attempts INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(source_type, source_id, scorer_type, scorer_version)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_diag_runs_status ON diagnosis_runs(status, updated_at)")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS diagnostic_evidence (
            id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            source_type TEXT NOT NULL,
            source_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            sequence_id TEXT DEFAULT '',
            observation_type TEXT NOT NULL,
            concept_name TEXT,
            observed_stage INTEGER,
            dimension TEXT,
            facet TEXT,
            direction TEXT NOT NULL,
            strength TEXT NOT NULL,
            student_quote TEXT NOT NULL,
            behavior TEXT,
            support_level TEXT DEFAULT 'unknown',
            scorer_version TEXT NOT NULL,
            window_id TEXT,
            payload TEXT DEFAULT '{}',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(run_id, observation_type, concept_name, dimension, facet, student_quote)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_diag_evidence_stage ON diagnostic_evidence(user_id, concept_name, observation_type)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_diag_evidence_dimension ON diagnostic_evidence(user_id, sequence_id, observation_type)")
    try:
        cursor.execute("ALTER TABLE diagnostic_evidence ADD COLUMN window_id TEXT")
    except Exception:
        pass

    # Dialogue probability diagnosis V1.  This shadow state is deliberately
    # separate from knowledge_stages so rollout cannot change teaching behavior.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS dialogue_knowledge_states (
            user_id TEXT NOT NULL,
            concept_id TEXT NOT NULL,
            concept_name TEXT NOT NULL,
            probabilities_json TEXT NOT NULL,
            map_stage INTEGER NOT NULL,
            expected_stage REAL NOT NULL,
            confidence REAL NOT NULL,
            evidence_count INTEGER NOT NULL DEFAULT 0,
            last_evidence_id TEXT,
            model_version TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, concept_id, model_version)
        )
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_dialogue_state_user
        ON dialogue_knowledge_states(user_id, updated_at)
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS dialogue_state_projection_log (
            id TEXT PRIMARY KEY,
            evidence_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            concept_id TEXT NOT NULL,
            before_distribution TEXT NOT NULL,
            likelihood TEXT NOT NULL,
            after_distribution TEXT NOT NULL,
            effective_weight REAL NOT NULL DEFAULT 0.0,
            action TEXT NOT NULL,
            model_version TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(evidence_id, model_version)
        )
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_dialogue_projection_user
        ON dialogue_state_projection_log(user_id, concept_id, created_at)
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS state_projection_log (
            id TEXT PRIMARY KEY,
            evidence_id TEXT,
            window_id TEXT,
            projection_type TEXT NOT NULL,
            projection_key TEXT NOT NULL,
            before_value TEXT,
            after_value TEXT,
            projection_version TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(evidence_id, projection_type, projection_version),
            UNIQUE(window_id, projection_type, projection_key, projection_version)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS dimension_windows (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            sequence_id TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'open',
            event_count INTEGER NOT NULL DEFAULT 0,
            member_source_ids TEXT NOT NULL DEFAULT '[]',
            member_evidence_ids TEXT NOT NULL DEFAULT '[]',
            result TEXT NOT NULL DEFAULT '{}',
            projection_version TEXT NOT NULL DEFAULT 'v2',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            closed_at TIMESTAMP
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_dimension_window_open ON dimension_windows(user_id, sequence_id, status)")

    for table in ("knowledge_stages", "math_profiles"):
        for col, definition in (
            ("baseline_version", "TEXT DEFAULT 'legacy_v1'"),
            ("projection_version", "TEXT DEFAULT 'legacy_v1'"),
        ):
            try:
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col} {definition}")
            except Exception:
                pass

    # 数据迁移：旧 weak_points → knowledge_stages
    try:
        cursor.execute("""
            INSERT OR IGNORE INTO knowledge_stages (id, user_id, concept_name, stage, confidence, evidence)
            SELECT lower(hex(randomblob(16))), user_id, value, 1, 0.2,
                   '[{"source":"migration","detail":"from user_profiles.weak_points"}]'
            FROM user_profiles, json_each(weak_points)
            WHERE json_valid(weak_points)
        """)
    except Exception:
        pass
    try:
        cursor.execute("""
            INSERT OR IGNORE INTO knowledge_stages (id, user_id, concept_name, stage, confidence, evidence)
            SELECT lower(hex(randomblob(16))), user_id, value, 1, 0.25,
                   '[{"source":"migration","detail":"from math_profiles.weak_points"}]'
            FROM math_profiles, json_each(weak_points)
            WHERE json_valid(weak_points)
        """)
    except Exception:
        pass

    # Normalized conversation tree storage.  Kept separate from the legacy
    # chat_history/follow_ups format so existing clients remain compatible.
    from app.db.chat_tree_db import init_chat_tree_schema
    init_chat_tree_schema(conn)
    from app.db.visualization_db import init_visualization_schema
    init_visualization_schema(conn)
    from app.db.tool_trace_db import init_tool_trace_schema
    init_tool_trace_schema(conn)

    conn.commit()
    conn.close()
