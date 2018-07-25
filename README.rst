###################
Tornado Opentracing
###################

This package enables distributed tracing in Tornado projects via `The OpenTracing Project`_. Once a production system contends with real concurrency or splits into many services, crucial (and formerly easy) tasks become difficult: user-facing latency optimization, root-cause analysis of backend errors, communication about distinct pieces of a now-distributed system, etc. Distributed tracing follows a request on its journey from inception to completion from mobile/browser all the way to the microservices.

As core services and libraries adopt OpenTracing, the application builder is no longer burdened with the task of adding basic tracing instrumentation to their own code. In this way, developers can build their applications with the tools they prefer and benefit from built-in tracing instrumentation. OpenTracing implementations exist for major distributed tracing systems and can be bound or swapped with a one-line configuration change.

If you want to learn more about the underlying python API, visit the python `source code`_.

.. _The OpenTracing Project: http://opentracing.io/
.. _source code: https://github.com/opentracing/opentracing-python

Installation
============

Run the following command::

    $ pip install tornado_opentracing

Setting up Tracing for All Requests
===================================

In order to implement tracing in your system (for all the requests), add the following lines of code to your site's ``Application`` constructor to enable tracing:

.. code-block:: python

    import tornado_opentracing

    # Initialize tracing before creating the Application object
    tornado_opentracing.init_tracing()

    # Configure the tracer
    app = Application(
        ''' Other parameters here '''
        opentracing_tracing=tornado_opentracing.TornadoTracing(some_opentracing_tracer),
    )

It is possible to set additional settings, for advanced usage:

.. code-block:: python

    app = Application(
        ''' Other parameters here '''
        opentracing_tracing=tornado_opentracing.TornadoTracing(some_opentracing_tracer),
        opentracing_trace_all=True, # defaults to True.
        opentracing_trace_client=True, # AsyncHTTPClient tracing, defaults to True
        opentracing_traced_attributes=['method'], # only valid if trace_all==True
        opentracing_start_span_cb=my_start_span_cb, # optional start Span callback.
    )


**Note:** Valid request attributes to trace are listed `here <http://www.tornadoweb.org/en/stable/httputil.html#tornado.httputil.HTTPServerRequest>`_. When you trace an attribute, this means that created spans will have tags with the attribute name and the request's value.

Tracing All Requests
====================

In order to trace all requests, set ``opentracing_trace_all=True`` when creating ``Application`` (this is the default value). If you want to trace any attributes for all requests, then add them to ``opentracing_traced_attributes``. For example, if you wanted to trace the uri and method, then set ``opentracing_traced_attributes = ['uri', 'method']``.

``opentracing_start_span_cb`` is a callback invoked after a new ``Span`` has been created, and it must have two parameters: the new ``Span`` and the ``request`` object.

Tracing requires ``init_tracing()`` to be called before ``Application`` is created (which will patch the ``RequestHandler``, ``Application`` and other **Tornado** components).

Tracing Individual Requests
===========================

If you don't want to trace all requests to your site, then you can use function decorators to trace individual functions. This can be done by managing a globally unique ``TornadoTracing`` object yourself, and adding the following lines of code to any get/post/put/delete function of your ``RequestHandler`` sub-classes:

.. code-block:: python

    tracing = TornadoTracing(some_opentracing_tracer)

    class MyRequestHandler(tornado.web.RequestHandler):
        # put the decorator before @tornado.gen.coroutine, if used
        @tracing.trace(['uri', 'method']) # optionally pass a list of traced attributes
        def get(self):
            ... # do some stuff

This tracing usage doesn't consume any ``opentracing_*`` setting defined in ``Application``, and there is not need to call ``init_tracing``.

The optional arguments allow for tracing of request attributes.

Tracing HTTP Client Requests
============================

When tracing all requests, tracing for ``AsyncHTTPClient`` is enabled by default, but this can be disabled by setting ``opentracing_trace_client=False``.

For applications tracing individual requests, or using only the http client (no ``tornado.web`` usage), client tracing can be enabled like this:

.. code-block:: python

    tornado_opentracing.init_client_tracing(some_opentracing_tracer)


``init_client_tracing`` takes an OpenTracing-compatible tracer, and can optionally take a ``start_span_cb`` parameter as callback. Observe this call **is not** required when required when using ``trace_all`` with the ``init_tracing`` initialization.

Examples
========

Here is a `simple example`_ of a **Tornado** application that log all requests:

.. _simple example: https://github.com/carlosalberto/python-tornado/tree/master/examples/simple/

Other examples are included under the examples directrory.

Further Information
===================

If you’re interested in learning more about the OpenTracing standard, please visit `opentracing.io`_ or `join the mailing list`_. If you would like to implement OpenTracing in your project and need help, feel free to send us a note at `community@opentracing.io`_.

.. _opentracing.io: http://opentracing.io/
.. _join the mailing list: http://opentracing.us13.list-manage.com/subscribe?u=180afe03860541dae59e84153&id=19117aa6cd
.. _community@opentracing.io: community@opentracing.io

