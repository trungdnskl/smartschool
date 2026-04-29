"""
db/ — Database package (refactored from monolithic database.py)

All public functions are re-exported here so existing imports
like `from database import get_sessions` continue to work
via the facade in database.py.

Internal sub-modules:
  - connection.py  : get_db_path(), get_db(), init_db(), migrations
  - teachers.py    : Teacher + Subject CRUD
  - classes.py     : Class CRUD
  - sessions.py    : Session lifecycle + summaries
  - students.py    : Student CRUD + consents
  - engagement.py  : Engagement logs, attendance, alerts
  - auth.py        : User/auth CRUD
  - maintenance.py : Recovery, cleanup, dashboard stats
"""
