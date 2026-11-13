"""Imports every model module so Base.metadata knows all tables.

Alembic's env.py and the tests import this. Add new model modules here.
"""

from app import models  # noqa: F401
from app.capture import models as capture_models  # noqa: F401
from app.ifs import models as ifs_models  # noqa: F401
from app.usage import models as usage_models  # noqa: F401
