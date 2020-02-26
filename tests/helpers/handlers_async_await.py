import asyncio

import tornado.web

from . import tracing


class AsyncScopeHandler(tornado.web.RequestHandler):
    async def do_something(self):
        tracing = self.settings.get('opentracing_tracing')
        with tracing.tracer.start_active_span('Child'):
            tracing.tracer.active_span.set_tag('start', 0)
            await asyncio.sleep(0)
            tracing.tracer.active_span.set_tag('end', 1)

    async def get(self):
        tracing = self.settings.get('opentracing_tracing')
        span = tracing.get_span(self.request)
        assert span is not None
        assert tracing.tracer.active_span is span

        await self.do_something()

        assert tracing.tracer.active_span is span
        self.write('{}')


class DecoratedAsyncHandler(tornado.web.RequestHandler):
    @tracing.trace('protocol', 'doesntexist')
    async def get(self):
        await asyncio.sleep(0)
        self.set_status(201)
        self.write('{}')


class DecoratedAsyncErrorHandler(tornado.web.RequestHandler):
    @tracing.trace()
    async def get(self):
        await asyncio.sleep(0)
        raise ValueError('invalid value')


class DecoratedAsyncScopeHandler(tornado.web.RequestHandler):
    async def do_something(self):
        with tracing.tracer.start_active_span('Child'):
            tracing.tracer.active_span.set_tag('start', 0)
            await asyncio.sleep(0)
            tracing.tracer.active_span.set_tag('end', 1)

    @tracing.trace()
    async def get(self):
        span = tracing.get_span(self.request)
        assert span is not None
        assert tracing.tracer.active_span is span

        await self.do_something()

        assert tracing.tracer.active_span is span
        self.set_status(201)
        self.write('{}')
