.. module:: score.distlock
.. role:: faint
.. role:: confkey

**************
score.distlock
**************

Introduction
============

This module provides means of creating and managing `reentrant mutexes`_ in
multi-server environments. Locks are created in a common database accessible by
all involed parties.

.. _reentrant mutexes: https://en.wikipedia.org/wiki/Reentrant_mutex

Use Case
========

Web applications usually require exclusivity on certain operations, like
changing an object. When one user is in the process of editing a blog entry,
for example, other users should not be able to edit the same document at the
same time. The scenario is supported through authentication tokens in the form
of the following:

Someone acquires the mutex (i.e. a :class:`.Lock`) required to edit an object
via AJAX and receives an authentication token (a hex string) in return. Before
the configured "maxtime" lapses (the time frame, the acquring party is granted
the lock for), the application will send another request extending the
lock—otherwise the lock will expire and another user can edit the
same object. This second request needs to pass the authentication token
received earlier to prove that it is indeed the same user that acquired the
lock in the first place.

Usage
=====

If the mutex is needed for a short operation (i.e. one that will be finished by
the same process that started it, like processing an incoming request), the
preferred way of using this class is via a `with` statement:

>>> with conf.get('mylock') as lock:
...     dosomething()
...     lock.extend()
...     domorethings()
...
>>> # the lock is automatically released at this point

But if the use case is similar to the scenario described earlier, you will need
to call the lock functions manually:

>>> token = conf.acquire('mylock')
>>> lock.extend(token)
>>> lock.release(token)

Configuration
=============

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
====

.. autoclass:: score.distlock.Lock

    .. automethod:: acquire

    .. automethod:: try_acquiring

    .. automethod:: extend

    .. automethod:: release

Exceptions
==========

.. autoclass:: score.distlock.CouldNotAcquireLock

.. autoclass:: score.distlock.LockExpired
