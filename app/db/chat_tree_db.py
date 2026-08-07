"""Persistent conversation trees.

The legacy ``chat_history.follow_ups`` column remains the compatibility
format.  This module owns the normalized tree representation and deliberately
keeps all mutations transactional so a failed branch operation cannot leave an
empty or partially visible node behind.
"""
from __future__ import annotations

import json
import uuid
from typing import Any, Iterable, Optional

from app.db.connection import get_conn


class TreeError(Exception):
    """Base error for tree operations."""


class TreeNotFound(TreeError):
    pass


class TreeForbidden(TreeError):
    pass


class RevisionConflict(TreeError):
    pass


class InvalidFork(TreeError):
    pass


def _id() -> str:
    return str(uuid.uuid4())


def _json(value: Any) -> str:
    return json.dumps(value if value is not None else [], ensure_ascii=False)


def init_chat_tree_schema(conn) -> None:
    """Create the tree schema on an existing SQLite connection."""
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS chat_trees (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            root_chat_history_id TEXT,
            last_active_node_id TEXT,
            revision INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, root_chat_history_id)
        );
        CREATE INDEX IF NOT EXISTS idx_chat_trees_user ON chat_trees(user_id, updated_at);

        CREATE TABLE IF NOT EXISTS chat_nodes (
            id TEXT PRIMARY KEY,
            tree_id TEXT NOT NULL,
            parent_node_id TEXT,
            fork_message_id TEXT,
            title TEXT NOT NULL DEFAULT '',
            version_group_id TEXT,
            is_adopted INTEGER NOT NULL DEFAULT 1,
            exclude_from_summary INTEGER NOT NULL DEFAULT 0,
            migration_quality TEXT NOT NULL DEFAULT 'exact',
            revision INTEGER NOT NULL DEFAULT 0,
            archived_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            legacy_key TEXT,
            FOREIGN KEY(tree_id) REFERENCES chat_trees(id),
            FOREIGN KEY(parent_node_id) REFERENCES chat_nodes(id)
        );
        CREATE INDEX IF NOT EXISTS idx_chat_nodes_tree ON chat_nodes(tree_id, archived_at, created_at);
        CREATE INDEX IF NOT EXISTS idx_chat_nodes_parent ON chat_nodes(parent_node_id);
        CREATE UNIQUE INDEX IF NOT EXISTS uq_chat_nodes_legacy_key
            ON chat_nodes(tree_id, legacy_key) WHERE legacy_key IS NOT NULL;

        CREATE TABLE IF NOT EXISTS chat_messages (
            id TEXT PRIMARY KEY,
            node_id TEXT NOT NULL,
            turn_id TEXT,
            sequence_no INTEGER NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('user', 'assistant', 'tool', 'system_event')),
            content TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'completed'
                CHECK(status IN ('streaming', 'completed', 'interrupted', 'failed')),
            token_count INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            FOREIGN KEY(node_id) REFERENCES chat_nodes(id)
        );
        CREATE UNIQUE INDEX IF NOT EXISTS uq_chat_messages_sequence ON chat_messages(node_id, sequence_no);
        CREATE INDEX IF NOT EXISTS idx_chat_messages_node ON chat_messages(node_id, sequence_no);

        CREATE TABLE IF NOT EXISTS chat_node_references (
            source_node_id TEXT NOT NULL,
            target_node_id TEXT NOT NULL,
            selected_message_ids TEXT NOT NULL DEFAULT '[]',
            summary_version TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(source_node_id, target_node_id),
            FOREIGN KEY(source_node_id) REFERENCES chat_nodes(id),
            FOREIGN KEY(target_node_id) REFERENCES chat_nodes(id)
        );

        CREATE TABLE IF NOT EXISTS node_summaries (
            id TEXT PRIMARY KEY,
            node_id TEXT NOT NULL,
            summary_version INTEGER NOT NULL,
            content_json TEXT NOT NULL DEFAULT '{}',
            source_message_ids TEXT NOT NULL DEFAULT '[]',
            strategy_version TEXT NOT NULL DEFAULT 'v1',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(node_id, summary_version),
            FOREIGN KEY(node_id) REFERENCES chat_nodes(id)
        );

        CREATE TABLE IF NOT EXISTS summary_trees (
            id TEXT PRIMARY KEY,
            chat_tree_id TEXT NOT NULL,
            version INTEGER NOT NULL,
            previous_ai_version_id TEXT,
            created_by TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(chat_tree_id, version),
            FOREIGN KEY(chat_tree_id) REFERENCES chat_trees(id)
        );

        CREATE TABLE IF NOT EXISTS summary_nodes (
            id TEXT PRIMARY KEY,
            summary_tree_id TEXT NOT NULL,
            parent_summary_node_id TEXT,
            node_type TEXT NOT NULL CHECK(node_type IN ('conclusion', 'misconception', 'open_question')),
            learning_status TEXT NOT NULL CHECK(learning_status IN ('explained', 'understood', 'misconception', 'unresolved')),
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            source_message_ids TEXT NOT NULL DEFAULT '[]',
            edited_by_user INTEGER NOT NULL DEFAULT 0,
            locked INTEGER NOT NULL DEFAULT 0,
            deleted_at TIMESTAMP,
            revision INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY(summary_tree_id) REFERENCES summary_trees(id),
            FOREIGN KEY(parent_summary_node_id) REFERENCES summary_nodes(id)
        );
        """
    )
    columns = {row[1] for row in conn.execute("PRAGMA table_info(chat_messages)").fetchall()}
    if "turn_id" not in columns:
        conn.execute("ALTER TABLE chat_messages ADD COLUMN turn_id TEXT")
    conn.execute(
        """CREATE UNIQUE INDEX IF NOT EXISTS uq_chat_messages_turn_role
           ON chat_messages(turn_id, role) WHERE turn_id IS NOT NULL"""
    )


def _owned_node(conn, node_id: str, user_id: str, include_archived: bool = False):
    row = conn.execute(
        """SELECT n.*, t.user_id, t.revision AS tree_revision
           FROM chat_nodes n JOIN chat_trees t ON t.id=n.tree_id
          WHERE n.id=?""",
        (node_id,),
    ).fetchone()
    if not row:
        raise TreeNotFound("node not found")
    if row["user_id"] != user_id:
        raise TreeForbidden("node does not belong to user")
    if not include_archived and row["archived_at"] is not None:
        raise TreeNotFound("node is archived")
    return row


def _owned_tree(conn, tree_id: str, user_id: str):
    row = conn.execute("SELECT * FROM chat_trees WHERE id=?", (tree_id,)).fetchone()
    if not row:
        raise TreeNotFound("tree not found")
    if row["user_id"] != user_id:
        raise TreeForbidden("tree does not belong to user")
    return row


def create_tree(user_id: str, root_chat_history_id: Optional[str], question: str,
                answer: Optional[str] = None, title: Optional[str] = None) -> dict:
    """Create a root tree, or return the existing tree for a legacy marker."""
    conn = get_conn()
    try:
        init_chat_tree_schema(conn)
        conn.execute("BEGIN IMMEDIATE")
        if root_chat_history_id:
            existing = conn.execute(
                "SELECT * FROM chat_trees WHERE user_id=? AND root_chat_history_id=?",
                (user_id, root_chat_history_id),
            ).fetchone()
            if existing:
                return _tree_dict(conn, existing["id"], include_archived=True)
        tree_id, node_id = _id(), _id()
        conn.execute(
            "INSERT INTO chat_trees(id,user_id,root_chat_history_id,last_active_node_id) VALUES(?,?,?,?)",
            (tree_id, user_id, root_chat_history_id, node_id),
        )
        conn.execute(
            "INSERT INTO chat_nodes(id,tree_id,title,version_group_id) VALUES(?,?,?,?)",
            (node_id, tree_id, title or question[:80], node_id),
        )
        _insert_message(conn, node_id, "user", question, "completed", sequence_no=0)
        if answer is not None:
            _insert_message(conn, node_id, "assistant", answer, "completed", sequence_no=1)
        conn.execute("UPDATE chat_trees SET revision=revision+1,updated_at=CURRENT_TIMESTAMP WHERE id=?", (tree_id,))
        conn.commit()
        return _tree_dict(conn, tree_id)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _insert_message(conn, node_id: str, role: str, content: str, status: str,
                    sequence_no: Optional[int] = None, message_id: Optional[str] = None,
                    turn_id: Optional[str] = None) -> str:
    if role not in {"user", "assistant", "tool", "system_event"}:
        raise ValueError("invalid message role")
    if status not in {"streaming", "completed", "interrupted", "failed"}:
        raise ValueError("invalid message status")
    if sequence_no is None:
        sequence_no = conn.execute("SELECT COALESCE(MAX(sequence_no), -1)+1 FROM chat_messages WHERE node_id=?", (node_id,)).fetchone()[0]
    mid = message_id or _id()
    completed_at = "CURRENT_TIMESTAMP" if status == "completed" else "NULL"
    conn.execute(
        f"INSERT INTO chat_messages(id,node_id,turn_id,sequence_no,role,content,status,completed_at) VALUES(?,?,?,?,?,?,?,{completed_at})",
        (mid, node_id, turn_id, sequence_no, role, content, status),
    )
    return mid


def begin_turn(
    node_id: str,
    user_id: str,
    question: str,
    *,
    turn_id: str,
    fork_message_id: Optional[str] = None,
    expected_revision: Optional[int] = None,
    expected_tree_id: Optional[str] = None,
) -> dict:
    """Create one durable QA turn, optionally by forking from an AI answer."""
    conn = get_conn()
    try:
        init_chat_tree_schema(conn)
        conn.execute("BEGIN IMMEDIATE")
        existing = conn.execute(
            """SELECT m.node_id FROM chat_messages m
               JOIN chat_nodes n ON n.id=m.node_id
               JOIN chat_trees t ON t.id=n.tree_id
               WHERE m.turn_id=? AND m.role='user' AND t.user_id=?""",
            (turn_id, user_id),
        ).fetchone()
        if existing:
            result = _turn_dict(conn, turn_id, user_id, created=False)
            conn.commit()
            return result

        parent = _owned_node(conn, node_id, user_id)
        if expected_tree_id and parent["tree_id"] != expected_tree_id:
            raise TreeForbidden("node is outside the requested tree")
        if expected_revision is not None and parent["revision"] != expected_revision:
            raise RevisionConflict(f"node revision {parent['revision']} != {expected_revision}")

        target_node_id = node_id
        if fork_message_id:
            anchor = conn.execute(
                "SELECT * FROM chat_messages WHERE id=? AND node_id=?",
                (fork_message_id, node_id),
            ).fetchone()
            if not anchor or anchor["role"] != "assistant" or anchor["status"] != "completed":
                raise InvalidFork("fork anchor must be a completed assistant message in the parent node")
            target_node_id = _id()
            conn.execute(
                """INSERT INTO chat_nodes(
                       id,tree_id,parent_node_id,fork_message_id,title,version_group_id,revision
                   ) VALUES(?,?,?,?,?,?,1)""",
                (target_node_id, parent["tree_id"], node_id, fork_message_id, question[:80], target_node_id),
            )
            conn.execute(
                "UPDATE chat_nodes SET revision=revision+1,updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (node_id,),
            )
        else:
            # A new root already contains its first user question. Adopt that
            # message into the durable turn instead of inserting a duplicate.
            pending = conn.execute(
                "SELECT * FROM chat_messages WHERE node_id=? ORDER BY sequence_no DESC LIMIT 1",
                (node_id,),
            ).fetchone()
            if pending and pending["role"] == "user" and pending["content"] == question and not pending["turn_id"]:
                conn.execute("UPDATE chat_messages SET turn_id=? WHERE id=?", (turn_id, pending["id"]))
            else:
                _insert_message(conn, target_node_id, "user", question, "completed", turn_id=turn_id)
                conn.execute(
                    "UPDATE chat_nodes SET revision=revision+1,updated_at=CURRENT_TIMESTAMP WHERE id=?",
                    (target_node_id,),
                )

        if fork_message_id:
            _insert_message(conn, target_node_id, "user", question, "completed", turn_id=turn_id)
        _insert_message(conn, target_node_id, "assistant", "", "streaming", turn_id=turn_id)
        conn.execute(
            "UPDATE chat_nodes SET revision=revision+1,updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (target_node_id,),
        )
        conn.execute(
            """UPDATE chat_trees SET revision=revision+1,updated_at=CURRENT_TIMESTAMP,
               last_active_node_id=? WHERE id=?""",
            (target_node_id, parent["tree_id"]),
        )
        conn.commit()
        return _turn_dict(conn, turn_id, user_id, created=True)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def finish_turn(turn_id: str, user_id: str, content: str, status: str) -> dict:
    """Finalize the assistant placeholder created by :func:`begin_turn`."""
    if status not in {"completed", "interrupted", "failed"}:
        raise ValueError("invalid terminal message status")
    conn = get_conn()
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            """SELECT m.*, n.tree_id, t.user_id FROM chat_messages m
               JOIN chat_nodes n ON n.id=m.node_id
               JOIN chat_trees t ON t.id=n.tree_id
               WHERE m.turn_id=? AND m.role='assistant'""",
            (turn_id,),
        ).fetchone()
        if not row:
            raise TreeNotFound("tree turn not found")
        if row["user_id"] != user_id:
            raise TreeForbidden("tree turn does not belong to user")
        if row["status"] != "streaming":
            conn.commit()
            return _turn_dict(conn, turn_id, user_id, created=False)
        conn.execute(
            """UPDATE chat_messages SET content=?,status=?,completed_at=CURRENT_TIMESTAMP
               WHERE id=?""",
            (content, status, row["id"]),
        )
        conn.execute(
            "UPDATE chat_nodes SET revision=revision+1,updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (row["node_id"],),
        )
        conn.execute(
            "UPDATE chat_trees SET revision=revision+1,updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (row["tree_id"],),
        )
        conn.commit()
        from app.db.visualization_db import attach_turn_visualizations
        attach_turn_visualizations(turn_id, row["id"])
        from app.db.tool_trace_db import attach_turn_traces
        attach_turn_traces(turn_id, row["id"])
        return _turn_dict(conn, turn_id, user_id, created=False)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _turn_dict(conn, turn_id: str, user_id: str, created: bool = False) -> dict:
    rows = conn.execute(
        """SELECT m.*, n.tree_id, n.parent_node_id, n.fork_message_id,
                  n.title, n.revision AS node_revision, t.user_id
           FROM chat_messages m
           JOIN chat_nodes n ON n.id=m.node_id
           JOIN chat_trees t ON t.id=n.tree_id
           WHERE m.turn_id=? ORDER BY m.sequence_no""",
        (turn_id,),
    ).fetchall()
    if not rows:
        raise TreeNotFound("tree turn not found")
    if rows[0]["user_id"] != user_id:
        raise TreeForbidden("tree turn does not belong to user")
    from app.db.visualization_db import decorate_messages
    messages = {message["role"]: message for message in decorate_messages(conn, rows)}
    first = rows[0]
    return {
        "turn_id": turn_id,
        "created": created,
        "tree_id": first["tree_id"],
        "node_id": first["node_id"],
        "parent_node_id": first["parent_node_id"],
        "fork_message_id": first["fork_message_id"],
        "title": first["title"],
        "node_revision": first["node_revision"],
        "user_message": messages.get("user"),
        "assistant_message": messages.get("assistant"),
    }


def append_message(node_id: str, user_id: str, role: str, content: str,
                   status: str = "completed", expected_revision: Optional[int] = None,
                   message_id: Optional[str] = None) -> dict:
    conn = get_conn()
    try:
        conn.execute("BEGIN IMMEDIATE")
        node = _owned_node(conn, node_id, user_id)
        if expected_revision is not None and node["revision"] != expected_revision:
            raise RevisionConflict(f"node revision {node['revision']} != {expected_revision}")
        mid = _insert_message(conn, node_id, role, content, status, message_id=message_id)
        conn.execute("UPDATE chat_nodes SET revision=revision+1,updated_at=CURRENT_TIMESTAMP WHERE id=?", (node_id,))
        conn.execute("UPDATE chat_trees SET revision=revision+1,updated_at=CURRENT_TIMESTAMP,last_active_node_id=? WHERE id=?", (node_id, node["tree_id"]))
        conn.commit()
        return dict(conn.execute("SELECT * FROM chat_messages WHERE id=?", (mid,)).fetchone())
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def create_fork(node_id: str, user_id: str, fork_message_id: str, question: str,
                title: Optional[str] = None, expected_revision: Optional[int] = None) -> dict:
    """Create a child only together with its first user message."""
    conn = get_conn()
    try:
        conn.execute("BEGIN IMMEDIATE")
        parent = _owned_node(conn, node_id, user_id)
        if expected_revision is not None and parent["revision"] != expected_revision:
            raise RevisionConflict(f"node revision {parent['revision']} != {expected_revision}")
        anchor = conn.execute(
            "SELECT * FROM chat_messages WHERE id=? AND node_id=?",
            (fork_message_id, node_id),
        ).fetchone()
        if not anchor or anchor["role"] != "assistant" or anchor["status"] != "completed":
            raise InvalidFork("fork anchor must be a completed assistant message in the parent node")
        child_id = _id()
        conn.execute(
            "INSERT INTO chat_nodes(id,tree_id,parent_node_id,fork_message_id,title,version_group_id) VALUES(?,?,?,?,?,?)",
            (child_id, parent["tree_id"], node_id, fork_message_id, title or question[:80], child_id),
        )
        _insert_message(conn, child_id, "user", question, "completed", sequence_no=0)
        conn.execute("UPDATE chat_trees SET revision=revision+1,updated_at=CURRENT_TIMESTAMP,last_active_node_id=? WHERE id=?", (child_id, parent["tree_id"]))
        conn.execute("UPDATE chat_nodes SET revision=revision+1,updated_at=CURRENT_TIMESTAMP WHERE id=?", (node_id,))
        conn.commit()
        return _node_dict(conn, child_id, include_messages=True)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def update_node(node_id: str, user_id: str, *, title: Optional[str] = None,
                exclude_from_summary: Optional[bool] = None,
                is_adopted: Optional[bool] = None,
                expected_revision: Optional[int] = None) -> dict:
    conn = get_conn()
    try:
        conn.execute("BEGIN IMMEDIATE")
        node = _owned_node(conn, node_id, user_id, include_archived=True)
        if expected_revision is not None and node["revision"] != expected_revision:
            raise RevisionConflict(f"node revision {node['revision']} != {expected_revision}")
        sets, params = [], []
        if title is not None:
            sets.append("title=?"); params.append(title.strip()[:200])
        if exclude_from_summary is not None:
            sets.append("exclude_from_summary=?"); params.append(int(exclude_from_summary))
        if is_adopted is not None:
            sets.append("is_adopted=?"); params.append(int(is_adopted))
        if sets:
            sets += ["revision=revision+1", "updated_at=CURRENT_TIMESTAMP"]
            params.append(node_id)
            conn.execute(f"UPDATE chat_nodes SET {', '.join(sets)} WHERE id=?", params)
            conn.execute("UPDATE chat_trees SET revision=revision+1,updated_at=CURRENT_TIMESTAMP WHERE id=?", (node["tree_id"],))
        conn.commit()
        return _node_dict(conn, node_id, include_messages=True)
    except Exception:
        conn.rollback(); raise
    finally:
        conn.close()


def archive_node(node_id: str, user_id: str, expected_revision: Optional[int] = None) -> dict:
    return _set_archive(node_id, user_id, True, expected_revision)


def restore_node(node_id: str, user_id: str, expected_revision: Optional[int] = None) -> dict:
    return _set_archive(node_id, user_id, False, expected_revision)


def _set_archive(node_id: str, user_id: str, archived: bool, expected_revision: Optional[int]):
    conn = get_conn()
    try:
        conn.execute("BEGIN IMMEDIATE")
        node = _owned_node(conn, node_id, user_id, include_archived=True)
        if expected_revision is not None and node["revision"] != expected_revision:
            raise RevisionConflict(f"node revision {node['revision']} != {expected_revision}")
        if node["parent_node_id"] is None and archived:
            raise InvalidFork("the root node cannot be archived")
        conn.execute(
            "UPDATE chat_nodes SET archived_at=(CASE WHEN ? THEN CURRENT_TIMESTAMP ELSE NULL END), revision=revision+1, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (int(archived), node_id),
        )
        conn.execute("UPDATE chat_trees SET revision=revision+1,updated_at=CURRENT_TIMESTAMP WHERE id=?", (node["tree_id"],))
        conn.commit()
        return _node_dict(conn, node_id, include_messages=True)
    except Exception:
        conn.rollback(); raise
    finally:
        conn.close()


def set_active_node(tree_id: str, user_id: str, node_id: str, expected_revision: Optional[int] = None) -> dict:
    conn = get_conn()
    try:
        conn.execute("BEGIN IMMEDIATE")
        tree = _owned_tree(conn, tree_id, user_id)
        node = _owned_node(conn, node_id, user_id)
        if node["tree_id"] != tree_id:
            raise TreeForbidden("node is not in tree")
        if expected_revision is not None and tree["revision"] != expected_revision:
            raise RevisionConflict(f"tree revision {tree['revision']} != {expected_revision}")
        conn.execute("UPDATE chat_trees SET last_active_node_id=?,revision=revision+1,updated_at=CURRENT_TIMESTAMP WHERE id=?", (node_id, tree_id))
        conn.commit()
        result = _tree_dict(conn, tree_id)
        try:
            from app.services.practice.repository import mark_stale_for_context
            mark_stale_for_context(user_id=user_id, tree_id=tree_id, node_id=node_id, concept_ids=[])
        except Exception:
            # Branch navigation must remain available if practice storage is unavailable.
            pass
        return result
    except Exception:
        conn.rollback(); raise
    finally:
        conn.close()


def set_references(source_node_id: str, user_id: str, target_node_ids: Iterable[str], selected_message_ids: Optional[dict[str, list[str]]] = None) -> list[dict]:
    conn = get_conn()
    try:
        conn.execute("BEGIN IMMEDIATE")
        source = _owned_node(conn, source_node_id, user_id)
        targets = list(dict.fromkeys(target_node_ids))
        for target_id in targets:
            target = _owned_node(conn, target_id, user_id)
            if target["tree_id"] != source["tree_id"] or target_id == source_node_id:
                raise TreeForbidden("references must target another node in the same tree")
            ids = (selected_message_ids or {}).get(target_id, [])
            if ids:
                placeholders = ",".join("?" for _ in ids)
                rows = conn.execute(f"SELECT id FROM chat_messages WHERE node_id=? AND id IN ({placeholders})", [target_id, *ids]).fetchall()
                if len(rows) != len(set(ids)):
                    raise TreeForbidden("selected message is outside the referenced node")
        conn.execute("DELETE FROM chat_node_references WHERE source_node_id=?", (source_node_id,))
        for target_id in targets:
            conn.execute("INSERT INTO chat_node_references(source_node_id,target_node_id,selected_message_ids) VALUES(?,?,?)", (source_node_id, target_id, _json((selected_message_ids or {}).get(target_id, []))))
        conn.commit()
        return [dict(r) for r in conn.execute("SELECT * FROM chat_node_references WHERE source_node_id=?", (source_node_id,)).fetchall()]
    except Exception:
        conn.rollback(); raise
    finally:
        conn.close()


def get_messages(node_id: str, user_id: str, include_archived: bool = False) -> list[dict]:
    conn = get_conn()
    try:
        _owned_node(conn, node_id, user_id, include_archived=include_archived)
        from app.db.visualization_db import decorate_messages
        rows = conn.execute("SELECT * FROM chat_messages WHERE node_id=? ORDER BY sequence_no", (node_id,)).fetchall()
        return decorate_messages(conn, rows)
    finally:
        conn.close()


def get_authorized_context(
    node_id: str,
    user_id: str,
    referenced_node_ids: Optional[Iterable[str]] = None,
    terminal_message_id: Optional[str] = None,
) -> list[dict]:
    """Return only current-node, ancestor-to-anchor, and explicitly referenced messages."""
    conn = get_conn()
    try:
        current = _owned_node(conn, node_id, user_id)
        terminal_sequence = None
        if terminal_message_id:
            terminal = conn.execute(
                "SELECT * FROM chat_messages WHERE id=? AND node_id=?",
                (terminal_message_id, node_id),
            ).fetchone()
            if not terminal or terminal["role"] != "assistant" or terminal["status"] != "completed":
                raise InvalidFork("terminal message must be a completed assistant message in the current node")
            terminal_sequence = terminal["sequence_no"]
        result: list[dict] = []
        path = []
        cursor = current
        while cursor:
            path.append(cursor)
            if cursor["parent_node_id"] is None:
                break
            cursor = conn.execute("SELECT * FROM chat_nodes WHERE id=?", (cursor["parent_node_id"],)).fetchone()
        ordered_path = list(reversed(path))
        for index, item in enumerate(ordered_path):
            max_sequence = None
            # A child freezes its parent at the child's fork anchor.  The
            # anchor therefore belongs to the next node on the root-to-leaf
            # path, not to the ancestor currently being enumerated.
            child_on_path = ordered_path[index + 1] if index + 1 < len(ordered_path) else None
            if child_on_path and child_on_path["fork_message_id"]:
                anchor = conn.execute("SELECT sequence_no FROM chat_messages WHERE id=?", (child_on_path["fork_message_id"],)).fetchone()
                max_sequence = anchor[0] if anchor else -1
            elif item["id"] == node_id and terminal_sequence is not None:
                max_sequence = terminal_sequence
            query = "SELECT * FROM chat_messages WHERE node_id=?"
            params: list[Any] = [item["id"]]
            if max_sequence is not None:
                query += " AND sequence_no<=?"; params.append(max_sequence)
            result.extend(dict(r) for r in conn.execute(query + " ORDER BY sequence_no", params).fetchall())
        for ref_id in dict.fromkeys(referenced_node_ids or []):
            ref = _owned_node(conn, ref_id, user_id)
            if ref["tree_id"] != current["tree_id"]:
                raise TreeForbidden("referenced node is outside the current tree")
            selected = conn.execute("SELECT selected_message_ids FROM chat_node_references WHERE source_node_id=? AND target_node_id=?", (node_id, ref_id)).fetchone()
            if not selected:
                raise TreeForbidden("sibling must be explicitly referenced first")
            ids = json.loads(selected[0] or "[]")
            if ids:
                placeholders = ",".join("?" for _ in ids)
                rows = conn.execute(f"SELECT * FROM chat_messages WHERE node_id=? AND id IN ({placeholders}) ORDER BY sequence_no", [ref_id, *ids]).fetchall()
            else:
                rows = conn.execute("SELECT * FROM chat_messages WHERE node_id=? ORDER BY sequence_no", (ref_id,)).fetchall()
            result.extend(dict(r) for r in rows)
        from app.db.visualization_db import decorate_messages
        return decorate_messages(conn, result)
    finally:
        conn.close()


def _node_dict(conn, node_id: str, include_messages: bool = False, include_archived: bool = True) -> dict:
    row = conn.execute("SELECT * FROM chat_nodes WHERE id=?", (node_id,)).fetchone()
    data = dict(row)
    if include_messages:
        from app.db.visualization_db import decorate_messages
        rows = conn.execute("SELECT * FROM chat_messages WHERE node_id=? ORDER BY sequence_no", (node_id,)).fetchall()
        data["messages"] = decorate_messages(conn, rows)
    return data


def _tree_dict(conn, tree_id: str, include_archived: bool = False) -> dict:
    tree = dict(conn.execute("SELECT * FROM chat_trees WHERE id=?", (tree_id,)).fetchone())
    query = "SELECT * FROM chat_nodes WHERE tree_id=?"
    params: list[Any] = [tree_id]
    if not include_archived:
        query += " AND archived_at IS NULL"
    tree["nodes"] = [dict(r) for r in conn.execute(query, params).fetchall()]
    for node in tree["nodes"]:
        from app.db.visualization_db import decorate_messages
        rows = conn.execute("SELECT * FROM chat_messages WHERE node_id=? ORDER BY sequence_no", (node["id"],)).fetchall()
        node["messages"] = decorate_messages(conn, rows)
    return tree


def get_tree(tree_id: str, user_id: str, include_archived: bool = False) -> dict:
    conn = get_conn()
    try:
        _owned_tree(conn, tree_id, user_id)
        return _tree_dict(conn, tree_id, include_archived=include_archived)
    finally:
        conn.close()


def get_tree_by_history(chat_history_id: str, user_id: str) -> Optional[dict]:
    conn = get_conn()
    try:
        row = conn.execute("SELECT id FROM chat_trees WHERE root_chat_history_id=? AND user_id=?", (chat_history_id, user_id)).fetchone()
        return _tree_dict(conn, row[0]) if row else None
    finally:
        conn.close()


def _materialize_legacy_marker(conn, marker) -> tuple[str, int]:
    created = 0
    existing = conn.execute(
        "SELECT id FROM chat_trees WHERE user_id=? AND root_chat_history_id=?",
        (marker["user_id"], marker["id"]),
    ).fetchone()
    if existing:
        tree_id = existing[0]
    else:
        tree_id, root_id = _id(), _id()
        conn.execute(
            "INSERT INTO chat_trees(id,user_id,root_chat_history_id,last_active_node_id) VALUES(?,?,?,?)",
            (tree_id, marker["user_id"], marker["id"], root_id),
        )
        conn.execute(
            """INSERT INTO chat_nodes(
                   id,tree_id,title,version_group_id,migration_quality,legacy_key
               ) VALUES(?,?,?,?,?,?)""",
            (root_id, tree_id, marker["question"][:80], root_id, "exact", "root"),
        )
        _insert_message(conn, root_id, "user", marker["question"], "completed", sequence_no=0)
        if marker["answer"]:
            _insert_message(conn, root_id, "assistant", marker["answer"], "completed", sequence_no=1)
        created += 1

    try:
        followups = json.loads(marker["follow_ups"] or "[]")
    except (TypeError, ValueError):
        followups = []
    root = conn.execute(
        "SELECT id FROM chat_nodes WHERE tree_id=? AND parent_node_id IS NULL", (tree_id,)
    ).fetchone()
    if not root:
        return tree_id, created
    anchor = conn.execute(
        """SELECT id FROM chat_messages WHERE node_id=? AND role='assistant'
           AND status='completed' ORDER BY sequence_no DESC LIMIT 1""",
        (root[0],),
    ).fetchone()
    for index, followup in enumerate(followups):
        if not isinstance(followup, dict) or not followup.get("question"):
            continue
        key = f"legacy-follow-up:{index}"
        exists = conn.execute(
            "SELECT id FROM chat_nodes WHERE tree_id=? AND legacy_key=?", (tree_id, key)
        ).fetchone()
        if exists:
            continue
        node_id = _id()
        conn.execute(
            """INSERT INTO chat_nodes(
                   id,tree_id,parent_node_id,fork_message_id,title,version_group_id,
                   migration_quality,legacy_key
               ) VALUES(?,?,?,?,?,?,?,?)""",
            (node_id, tree_id, root[0], anchor[0] if anchor else None,
             followup["question"][:80], node_id, "legacy_approximate", key),
        )
        _insert_message(conn, node_id, "user", followup["question"], "completed", sequence_no=0)
        if followup.get("answer"):
            _insert_message(conn, node_id, "assistant", followup["answer"], "completed", sequence_no=1)
        created += 1
    return tree_id, created


def ensure_tree_from_history(chat_history_id: str, user_id: str) -> dict:
    """Idempotently materialize one legacy marker for its authenticated owner."""
    conn = get_conn()
    try:
        init_chat_tree_schema(conn)
        conn.execute("BEGIN IMMEDIATE")
        marker = conn.execute(
            "SELECT * FROM chat_history WHERE id=? AND user_id=?",
            (chat_history_id, user_id),
        ).fetchone()
        if not marker:
            raise TreeNotFound("chat history not found")
        tree_id, _ = _materialize_legacy_marker(conn, marker)
        conn.commit()
        return _tree_dict(conn, tree_id)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def migrate_legacy_followups(user_id: Optional[str] = None) -> int:
    """Idempotently materialize legacy markers and their follow-ups."""
    conn = get_conn()
    created = 0
    try:
        init_chat_tree_schema(conn)
        conn.execute("BEGIN IMMEDIATE")
        query = "SELECT * FROM chat_history" + (" WHERE user_id=?" if user_id else "")
        rows = conn.execute(query, (user_id,) if user_id else ()).fetchall()
        for marker in rows:
            _, marker_created = _materialize_legacy_marker(conn, marker)
            created += marker_created
        conn.commit()
        return created
    except Exception:
        conn.rollback(); raise
    finally:
        conn.close()


def create_summary_tree(tree_id: str, user_id: str, nodes: list[dict], created_by: str = "user") -> dict:
    """Persist a versioned, source-linked learning summary for a tree."""
    conn = get_conn()
    try:
        init_chat_tree_schema(conn)
        conn.execute("BEGIN IMMEDIATE")
        _owned_tree(conn, tree_id, user_id)
        valid_nodes = conn.execute(
            "SELECT id FROM chat_nodes WHERE tree_id=? AND archived_at IS NULL AND is_adopted=1 AND exclude_from_summary=0",
            (tree_id,),
        ).fetchall()
        valid_node_ids = {row[0] for row in valid_nodes}
        version = conn.execute("SELECT COALESCE(MAX(version), 0)+1 FROM summary_trees WHERE chat_tree_id=?", (tree_id,)).fetchone()[0]
        summary_tree_id = _id()
        conn.execute("INSERT INTO summary_trees(id,chat_tree_id,version,created_by) VALUES(?,?,?,?)", (summary_tree_id, tree_id, version, created_by))
        inserted = []
        for item in nodes:
            node_id = item.get("id") or _id()
            parent_id = item.get("parent_summary_node_id")
            if parent_id and parent_id not in {row["id"] for row in inserted}:
                raise ValueError("summary parent must be in the same submitted tree")
            node_type = item.get("node_type", "conclusion")
            status = item.get("learning_status", "explained")
            if node_type not in {"conclusion", "misconception", "open_question"}:
                raise ValueError("invalid summary node type")
            if status not in {"explained", "understood", "misconception", "unresolved"}:
                raise ValueError("invalid learning status")
            source_ids = list(dict.fromkeys(item.get("source_message_ids") or []))
            if source_ids:
                placeholders = ",".join("?" for _ in source_ids)
                rows = conn.execute(
                    f"SELECT m.id FROM chat_messages m JOIN chat_nodes n ON n.id=m.node_id WHERE n.tree_id=? AND n.id IN ({','.join('?' for _ in valid_node_ids)}) AND m.id IN ({placeholders})",
                    [tree_id, *valid_node_ids, *source_ids],
                ).fetchall()
                if {row[0] for row in rows} != set(source_ids):
                    raise TreeForbidden("summary source message is outside the active tree scope")
            conn.execute(
                """INSERT INTO summary_nodes(id,summary_tree_id,parent_summary_node_id,node_type,learning_status,title,content,source_message_ids,edited_by_user,locked)
                   VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (node_id, summary_tree_id, parent_id, node_type, status, str(item.get("title", ""))[:200], str(item.get("content", "")), _json(source_ids), int(bool(item.get("edited_by_user"))), int(bool(item.get("locked")))),
            )
            inserted.append({"id": node_id})
        conn.commit()
        return get_summary_tree(summary_tree_id, user_id)
    except Exception:
        conn.rollback(); raise
    finally:
        conn.close()


def get_summary_tree(summary_tree_id: str, user_id: str) -> dict:
    conn = get_conn()
    try:
        row = conn.execute(
            """SELECT s.*, t.user_id FROM summary_trees s JOIN chat_trees t ON t.id=s.chat_tree_id
               WHERE s.id=?""",
            (summary_tree_id,),
        ).fetchone()
        if not row:
            raise TreeNotFound("summary tree not found")
        if row["user_id"] != user_id:
            raise TreeForbidden("summary tree does not belong to user")
        data = dict(row)
        data["nodes"] = [dict(item) for item in conn.execute("SELECT * FROM summary_nodes WHERE summary_tree_id=? AND deleted_at IS NULL", (summary_tree_id,)).fetchall()]
        return data
    finally:
        conn.close()


def get_latest_summary_tree(tree_id: str, user_id: str) -> Optional[dict]:
    conn = get_conn()
    try:
        _owned_tree(conn, tree_id, user_id)
        row = conn.execute("SELECT id FROM summary_trees WHERE chat_tree_id=? ORDER BY version DESC LIMIT 1", (tree_id,)).fetchone()
        return get_summary_tree(row[0], user_id) if row else None
    finally:
        conn.close()


def update_summary_node(summary_node_id: str, user_id: str, *, title: Optional[str] = None,
                        content: Optional[str] = None, learning_status: Optional[str] = None,
                        expected_revision: Optional[int] = None, lock: Optional[bool] = None) -> dict:
    conn = get_conn()
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            """SELECT n.*, t.user_id FROM summary_nodes n
               JOIN summary_trees s ON s.id=n.summary_tree_id JOIN chat_trees t ON t.id=s.chat_tree_id
               WHERE n.id=?""",
            (summary_node_id,),
        ).fetchone()
        if not row:
            raise TreeNotFound("summary node not found")
        if row["user_id"] != user_id:
            raise TreeForbidden("summary node does not belong to user")
        if expected_revision is not None and row["revision"] != expected_revision:
            raise RevisionConflict(f"summary node revision {row['revision']} != {expected_revision}")
        if learning_status is not None and learning_status not in {"explained", "understood", "misconception", "unresolved"}:
            raise ValueError("invalid learning status")
        sets, params = [], []
        if title is not None:
            sets.append("title=?"); params.append(title[:200])
        if content is not None:
            sets.append("content=?"); params.append(content)
        if learning_status is not None:
            sets.append("learning_status=?"); params.append(learning_status)
        if lock is not None:
            sets.append("locked=?"); params.append(int(lock))
        sets += ["edited_by_user=1", "revision=revision+1"]
        params.append(summary_node_id)
        conn.execute(f"UPDATE summary_nodes SET {', '.join(sets)} WHERE id=?", params)
        conn.commit()
        result = conn.execute("SELECT * FROM summary_nodes WHERE id=?", (summary_node_id,)).fetchone()
        return dict(result)
    except Exception:
        conn.rollback(); raise
    finally:
        conn.close()
