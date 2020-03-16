"""
This module implements AsyncTornadoTracing for Python3.5 and above.
The module must be only imported when running on Python3.5 and newer.
Importing it on older version of Python will result in SyntaxError
exception.
The module is suffixed with "_py35" to indicate to python tooling
such as linters that it should be only be taken into account
for Python3.5 and above.
"""

import inspect
import functools

from ._tracing import BaseTornadoTracing


class AsyncTornadoTracing(BaseTornadoTracing):

    def trace(self, *attributes):
        """
        Function decorator that traces functions
        NOTE: Must be placed before the Tornado decorators
        @param attributes any number of request attributes
        (strings) to be set as tags on the created span.

        This decorator support async functions in addition to regular ones.
        This is needed for tornado to work correctly with async handlers.

        We use a descriptor here as we need reference to the instance of the
        method being decorated which is not possible to do with a simple
        decorator.

        We don't use wrapt.decorator as it does not work uniformly with
        both async and regular functions, and we cannot selectively export
        an async or a regular decorator using wrapt as it's not possible
        to determine if the function being wrapped is async or not before
        the decorator is applied.
        """
        tracing = self

        class Descriptor(object):
            def __init__(self, wrapped):
                self.wrapped = wrapped

            async def __call__(self, handler, *args, **kwargs):
                if tracing._trace_all:
                    return self.wrapped(handler, *args, **kwargs)

                try:
                    tracing._apply_tracing(handler, list(attributes))

                    result = self.wrapped(handler, *args, **kwargs)
                    if result is not None and inspect.isawaitable(result):
                        result = await result
                    tracing._handle_wrapped_result(handler, result)

                except Exception as exc:
                    tracing._finish_tracing(handler, error=exc)
                    raise

            def __get__(self, instance, owner):
                return functools.partial(self.__call__, instance)

        return Descriptor
