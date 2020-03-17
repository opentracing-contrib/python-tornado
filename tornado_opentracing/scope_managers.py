import sys
from tornado import version_info as tornado_version

# - For Tornado 5 and older, we continue to use the old TornadoScopeManager
# based on tornado.stack_context which was removed in Tornado6.
# - For Tornado 6 and newer, we use the ContextVarsScopeManager based on
# the new contextvars module introduced in Python3.7.
# - For Tornado 6 and newer running on Python 3.6 and older, we use the
# AsyncIOScopeManager which implements context propagation using a custom
# mechanism built on top of the asyncio module.

if tornado_version >= (6, 0):
    if sys.version_info >= (3, 7):
        from opentracing.scope_managers.contextvars import (
            ContextVarsScopeManager as TornadoScopeManager  # noqa
        )
    else:
        from opentracing.scope_managers.asyncio import (
            AsyncioScopeManager as TornadoScopeManager  # noqa
        )
else:
    from opentracing.scope_managers.tornado import TornadoScopeManager  # noqa
