import sys

import tornado.web


class noopHandler(tornado.web.RequestHandler):
    def get(self):
        pass


if sys.version_info > (3, 5):
    from .handlers_async_await import (
        AsyncScopeHandler,
        DecoratedAsyncHandler,
        DecoratedAsyncScopeHandler,
        DecoratedAsyncErrorHandler
    )
else:
    AsyncScopeHandler = noopHandler
    DecoratedAsyncHandler = noopHandler
    DecoratedAsyncScopeHandler = noopHandler
    DecoratedAsyncErrorHandler = noopHandler
