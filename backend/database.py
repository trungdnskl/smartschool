"""
Classroom Engagement System — Database Facade
==============================================
Thin re-export layer so ALL existing imports like:
    from database import get_sessions, init_db, ...
continue to work without changes.

Actual implementations live in db/ sub-modules:
    db/connection.py  — get_db_path, get_db, init_db, migrations
    db/teachers.py    — Teacher + Subject CRUD
    db/classes.py     — Class CRUD
    db/sessions.py    — Session lifecycle + summaries
    db/students.py    — Student CRUD + consents
    db/engagement.py  — Engagement logs, attendance, alerts
    db/auth.py        — User/auth CRUD
    db/maintenance.py — Recovery, cleanup, dashboard stats
"""

# ── Connection & init ─────────────────────────────────────────
from db.connection import get_db_path, get_db, init_db          # noqa: F401

# ── Teachers & Subjects ──────────────────────────────────────
from db.teachers import (                                        # noqa: F401
    create_teacher, get_teachers, get_teacher_by_id,
    update_teacher, delete_teacher,
    create_subject, get_subjects, delete_subject,
)

# ── Classes ──────────────────────────────────────────────────
from db.classes import (                                         # noqa: F401
    create_class, get_classes, get_class_by_id,
    update_class, delete_class,
    get_class_students, update_class_student_count,
)

# ── Sessions ─────────────────────────────────────────────────
from db.sessions import (                                        # noqa: F401
    create_session, end_session, get_active_session,
    get_sessions, get_sessions_count, get_session_by_id,
    save_session_summary, get_session_summary,
)

# ── Students ─────────────────────────────────────────────────
from db.students import (                                        # noqa: F401
    enroll_student, get_students, delete_student,
    get_student_by_id, update_student,
    add_parent_consent, get_parent_consents,
)

# ── Engagement / Attendance / Alerts ─────────────────────────
from db.engagement import (                                      # noqa: F401
    insert_engagement_log, get_engagement_timeline,
    get_student_engagement_history,
    upsert_attendance, get_attendance,
    insert_alert, get_alerts, mark_alert_read, mark_all_alerts_read,
)

# ── Auth ─────────────────────────────────────────────────────
from db.auth import (                                            # noqa: F401
    get_user_by_username, create_user,
    update_user_password, list_users, deactivate_user,
)

# ── Maintenance ──────────────────────────────────────────────
from db.maintenance import (                                     # noqa: F401
    recover_stuck_sessions, get_dashboard_stats,
    cleanup_expired_data,
)
