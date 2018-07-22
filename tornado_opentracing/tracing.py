import functools
import wrapt

import opentracing
from opentracing.scope_managers.tornado import tracer_stack_context

from ._constants import SCOPE_ATTR


class TornadoTracing(object):
    '''
    @param tracer the OpenTracing tracer to be used
    to trace requests using this TornadoTracing
    '''
    def __init__(self, tracer, trace_all=False, trace_client=False,
                 start_span_cb=None):
        self._tracer = tracer
        self._trace_all = trace_all
        self._trace_client = trace_client
        self._start_span_cb = start_span_cb

    @property
    def tracer(self):
        return self._tracer

    def get_span(self, request):
        '''
        @param request 
        Returns the span tracing this request
        '''
        scope = getattr(request, SCOPE_ATTR, None)
        return None if scope is None else scope.span

    def trace(self, *attributes):
        '''
        Function decorator that traces functions
        NOTE: Must be placed before the Tornado decorators
        @param attributes any number of request attributes
        (strings) to be set as tags on the created span
        '''

        @wrapt.decorator
        def wrapper(wrapped, instance, args, kwargs):
            if self._trace_all:
                return wrapped(*args, **kwargs)

            handler = instance

            with tracer_stack_context():
                try:
                    self._apply_tracing(handler, list(attributes))

                    # Run the actual function.
                    result = wrapped(*args, **kwargs)

                    # if it has `add_done_callback` it's a Future,
                    # else, a normal method/function.
                    if callable(getattr(result, 'add_done_callback', None)):
                        callback = functools.partial(
                                self._finish_tracing_callback,
                                handler=handler)
                        result.add_done_callback(callback)
                    else:
                        self._finish_tracing(handler)

                except Exception as exc:
                    self._finish_tracing(handler, error=exc)
                    raise

            return result

        return wrapper

    def _get_operation_name(self, handler):
        full_class_name = type(handler).__name__
        return full_class_name.rsplit('.')[-1] # package-less name.

    def _finish_tracing_callback(self, future, handler):
        error = future.exception()
        self._finish_tracing(handler, error=error)

    def _apply_tracing(self, handler, attributes):
        '''
        Helper function to avoid rewriting for middleware and decorator.
        Returns a new span from the request with logged attributes and 
        correct operation name from the func.
        '''
        operation_name = self._get_operation_name(handler)
        headers = handler.request.headers
        request = handler.request

        # start new span from trace info
        span = None
        try:
            span_ctx = self._tracer.extract(opentracing.Format.HTTP_HEADERS,
                                            headers)
            scope = self._tracer.start_active_span(operation_name,
                                                   child_of=span_ctx)
        except (opentracing.InvalidCarrierException,
                opentracing.SpanContextCorruptedException):
            scope = self._tracer.start_active_span(operation_name)

        # add span to current spans 
        setattr(request, SCOPE_ATTR, scope)

        # log any traced attributes
        scope.span.set_tag('component', 'tornado')
        scope.span.set_tag('http.method', request.method)
        scope.span.set_tag('http.url', request.uri)

        for attr in attributes:
            if hasattr(request, attr):
                payload = str(getattr(request, attr))
                if payload:
                    scope.span.set_tag(attr, payload)

        # invoke the start span callback, if any
        if self._start_span_cb is not None:
            self._start_span_cb(scope.span, request)

        return scope

    def _finish_tracing(self, handler, error=None):
        scope = getattr(handler.request, SCOPE_ATTR, None)
        if scope is None:
            return

        delattr(handler.request, SCOPE_ATTR)

        if error is not None:
            scope.span.set_tag('error', 'true')
            scope.span.set_tag('error.object', error)

        scope.span.set_tag('http.status_code', handler.get_status())
        scope.close()
