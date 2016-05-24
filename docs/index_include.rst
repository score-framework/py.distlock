.. module:: score.distlock
.. role:: confkey
.. role:: confdefault

**************
score.distlock
**************

This module provides means of creating and managing `reentrant mutexes`_ in
multi-server environments. Locks are created in a common database accessible by
all involed parties.

.. _reentrant mutexes: https://en.wikipedia.org/wiki/Reentrant_mutex

Quickstart
==========

Acquire the lock "mylock" for the duration of the ``dosomething()`` call:

>>> with conf.get('mylock') as lock:
...     dosomething()
...
>>> # the lock is automatically released at this point

No other process can acquire the same lock "mylock" while ``dosomething()`` is
running. If the ``dosomething()`` operation takes a long time, your lock might
expire in the mean time. You should occasionally call :meth:`Lock.extend` in
such cases:

>>> with conf.get('mylock') as lock:
...     do_part_of_something()
...     lock.extend()
...     do_more_things()
...

Details
=======

Tokens
------

If a lock is to be held even after the process has finished, it can ben
converted into a token:

>>> token = conf.acquire('mylock')
>>> token
b'0f5ba13b1a9d2c9951b29352af619534c0f1487c5a9b5b7e0a6d64042fe8fa15aad37be9d5fae35217381e2fffbdb25c1787a572a89b0ce98eaa509ed8f3346b8fabc82deb625542b2e29c9d26f301906fd1d3bd026bf816faa60180374a077146f08d0995e3dbd84726754c9e9f9080404a6283a8d78c41f2d1ac5cd0aa6c62'

As long as you do not hit a timeout, this token represents the hold on the
:class:`Lock` "mylock". You can use this token to control your lock from
another process:

>>> conf.release('mylock', token)

Timeouts
--------

Since it is possible to keep a lock after leaving a python process, all locks
will expire automatically after a certain time frame to prevent process
starvation. If you want to keep a lock for a longer duration than the
configured *maxtime*, you should :meth:`extend <Lock.extend>` your lock before
it expires:

>>> conf.extend('mylock', token)

API
===

Configuration
-------------

.. autofunction:: score.distlock.init

.. autoclass:: score.distlock.ConfiguredDistlockModule

    .. attribute:: engine

        The SQLAlchemy :class:`Engine <sqlalchemy.engine.Engine>` that will
        provide the connection to the common database.

    .. attribute:: maxtime

        The configured maximum age of a :class:`.Lock`.

    .. automethod:: get

    .. automethod:: acquire

    .. automethod:: try_acquiring

    .. automethod:: extend

    .. automethod:: release

    .. automethod:: vacuum

Lock
----

.. autoclass:: score.distlock.Lock

    .. automethod:: acquire

    .. automethod:: try_acquiring

    .. automethod:: extend

    .. automethod:: release

Exceptions
----------

.. autoclass:: score.distlock.CouldNotAcquireLock

.. autoclass:: score.distlock.LockExpired
