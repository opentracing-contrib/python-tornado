from tornado import version_info as tornado_version

if tornado_version < (6, 0):
    from opentracing.scope_managers.tornado import (
        tracer_stack_context as tornado_context
    )
else:
    def tornado_context():
        return _NoopContextManager()


class _NoopContextManager(object):
    """
    With Tornado 6 and newer, we use ContextVarsScopeManager
    or AsyncIOScopeManager depending on the Python interpreter version.
    Neither of the two really need the tracer_stack_context context manager
    but to keep the code uniform and not break APIs, we use a
    noop context manager for Tornado 6.
    """

    def __enter__(self):
        pass

    def __exit__(self, *_):
        pass
