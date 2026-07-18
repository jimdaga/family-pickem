"""Test package for the pickem API application.

The legacy test module is re-exported so existing dotted test labels such as
``pickem_api.tests.TenantDomainModelTest`` remain valid after adding focused
test modules.
"""

from .legacy import *  # noqa: F401,F403
