import sys

from tornado import version_info as tornado_version


# Use asyncio compatible tracing when running tornado 5 or above
# on Python3.5 or above. Older version continue to use the
# old tornado tracing based on tornado.stack_context.

use_async_tracing = sys.version_info >= (3, 5) and tornado_version >= (5, 0)

if use_async_tracing:
    from ._tracing_async import AsyncTornadoTracing as TornadoTracing  # noqa
else:
    from ._tracing import BaseTornadoTracing as TornadoTracing  # noqa
