# Copyright © 2015,2016 STRG.AT GmbH, Vienna, Austria
#
# This file is part of the The SCORE Framework.
#
# The SCORE Framework and all its parts are free software: you can redistribute
# them and/or modify them under the terms of the GNU Lesser General Public
# License version 3 as published by the Free Software Foundation which is in the
# file named COPYING.LESSER.txt.
#
# The SCORE Framework and all its parts are distributed without any WARRANTY;
# without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
# PARTICULAR PURPOSE. For more details see the GNU Lesser General Public
# License.
#
# If you have not received a copy of the GNU Lesser General Public License see
# http://www.gnu.org/licenses/.
#
# The License-Agreement realised between you as Licensee and STRG.AT GmbH as
# Licenser including the issue of its valid conclusion and its pre- and
# post-contractual effects is governed by the laws of Austria. Any disputes
# concerning this License-Agreement including the issue of its valid conclusion
# and its pre- and post-contractual effects are exclusively decided by the
# competent court, in whose district STRG.AT GmbH has its registered seat, at
# the discretion of STRG.AT GmbH also the competent court, in whose district the
# Licensee has his registered seat, an establishment or assets.

import binascii
from datetime import datetime, timedelta
import random
from score.init import ConfiguredModule, parse_time_interval
from sqlalchemy import Column, String, Integer, DateTime, engine_from_config
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import weakref


defaults = {
    'maxtime': '1m',
}


def init(confdict):
    """
    Initializes this module acoording to :ref:`our module initialization
    guidelines <module_initialization>` with the following configuration keys:

    :confkey:`sqlalchemy.*`
        All configuration values under this key will be passed to
        :func:`sqlalchemy.engine_from_config`, which in turn calls
        :func:`sqlalchemy.create_engine` with these configuration values as
        keyword arguments. Usually the following is sufficient::

            sqlalchemy.url = postgresql://dbuser@localhost/projname

    :confkey:`maxtime` :confdefault:`1m`
        Maximum time frame a lock can be held without being updated. Any
        lock older than this time frame is considered expired.

    """
    conf = defaults.copy()
    conf.update(confdict)
    engine = engine_from_config(conf)
    maxtime = parse_time_interval(conf['maxtime'])
    return ConfiguredDistlockModule(engine, maxtime)


class CouldNotAcquireLock(Exception):
    """
    Thrown when a lock could not be acquired.
    """
    pass


class LockExpired(Exception):
    """
    Thrown when a lock expired unexpectedly.
    """
    pass


def mktoken():
    """
    Generates a random token that is required for manipulating an existing lock.
    """
    return binascii.hexlify(bytearray(random.getrandbits(8)
                                      for _ in range(128))).decode('ascii')


class Lock:
    """
    Allows manipulating a single named lock.

    This object can also be used as a context generator for `with` statements:

    .. code-block:: python

        with lock:
            do_something()
    """

    def __init__(self, conf, name):
        self.conf = conf
        self.name = name
        self.token = None

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, type, value, traceback):
        self.release()

    def acquire(self):
        """
        Acquires the lock or raises :class:`.CouldNotAcquireLock`.

        Returns an authentication token on success, that needs to be passed to
        various other functions if the lock will be managed by a different
        process. See the :mod:`narrative documentation <score.distlock>` for an
        explanation of the resulting token.
        """
        token = self.try_acquiring()
        if not token:
            raise CouldNotAcquireLock(self.name)
        return token

    def extend(self, token=None):
        """
        Extends the lock.

        See the :mod:`narrative documentation <score.distlock>` for an
        explanation of the *token* parameter.

        If this function is successfull, the lock will be valid for another
        "maxtime" seconds.
        """
        token = self._get_token(token)
        session = self.conf.Session()
        lock = self._get_lock(session, token)
        if not lock:
            session.rollback()
            raise LockExpired(self.name, token)
        lock.updated = datetime.now()
        session.flush()
        session.commit()

    def release(self, token=None, ignore_expired=False):
        """
        Releases this lock, others may acquire it immediately.

        See the :mod:`narrative documentation <score.distlock>` for an
        explanation of the *token* parameter.

        Unless the *ignore_expired* parameter is passed a truthy value, the
        function will raise :class:`.LockExpired` if the user is no longer
        holding the lock.
        *token* parameter.
        """
        token = self._get_token(token)
        self.token = None
        session = self.conf.Session()
        lock = self._get_lock(session, token)
        if not lock:
            session.rollback()
            if ignore_expired:
                return
            raise LockExpired(self.name, token)
        session.delete(lock)
        session.flush()
        session.commit()

    def try_acquiring(self):
        """
        Tries to acquire the lock and returns an authentication token on
        success, or `None` if the lock could not be acquired.

        Returns an authentication token on success, that needs to be passed to
        various other functions if the lock will be managed by a different
        process. See the :mod:`narrative documentation <score.distlock>` for an
        explanation of the resulting token.
        """
        session = self.conf.Session()
        lock = self.conf.lock_cls(name=self.name,
                                  acquired=datetime.now(),
                                  updated=datetime.now(),
                                  token=mktoken())
        self.conf.vacuum(session)
        session.add(lock)
        try:
            session.flush()
            session.commit()
            self.token = lock.token
            return lock.token
        except IntegrityError:
            session.rollback()
            return None

    def _get_token(self, token):
        if token:
            return token
        if self.token is None:
            raise ValueError('Token required if the lock was not '
                             'acquired by this process')
        return self.token

    def _get_lock(self, session, token):
        cls = self.conf.lock_cls
        threshold = datetime.now() - timedelta(seconds=self.conf.maxtime)
        return session.query(cls).\
            filter(cls.name == self.name).\
            filter(cls.token == token).\
            filter(cls.updated >= threshold).\
            first()


class ConfiguredDistlockModule(ConfiguredModule):
    """
    This module's :class:`configuration class
    <score.init.ConfiguredModule>`.
    """

    def __init__(self, engine, maxtime):
        import score.distlock
        super().__init__(score.distlock)
        self.engine = engine
        self.maxtime = maxtime
        self.Session = sessionmaker(bind=engine)
        Base = declarative_base()
        Base.metadata.bind = engine
        self.lock_cls = type('Distlock', (Base,), {
            '__tablename__': '_score_distlock',
            'id': Column(Integer, primary_key=True),
            'name': Column(String, unique=True, nullable=False),
            'acquired': Column(DateTime, nullable=False),
            'updated': Column(DateTime, nullable=False),
            'token': Column(String(256), nullable=False),
        })
        Base.metadata.create_all()
        self.locks = {}

    def get(self, name):
        """
        Provides the :class:`.Lock` with given *name*.

        Keeps a weak reference to the Lock internally and will return the same
        object on consecutive calls (as long as the object is not
        garbage-collected in the mean time.)
        """
        if name in self.locks:
            lock = self.locks[name]()
            if lock is not None:
                return lock
        lock = Lock(self, name)
        self.locks[name] = weakref.ref(lock)
        return lock

    def acquire(self, name):
        """
        Convenient access to :meth:`.Lock.acquire`.
        """
        return self.get(name).acquire()

    def try_acquiring(self, name):
        """
        Convenient access to :meth:`.Lock.try_acquiring`.
        """
        return self.get(name).try_acquiring()

    def extend(self, name, token=None):
        """
        Convenient access to :meth:`.Lock.extend`.
        """
        return self.get(name).extend(token)

    def release(self, name, token=None):
        """
        Convenient access to :meth:`.Lock.release`.
        """
        return self.get(name).release(token)

    def vacuum(self, session=None):
        """
        Cleans up all expired locks from the database, speeding up all future
        lock operations.

        There is no need to call this function manually, it will be invoked on
        each attempt t acquire a lock.
        """
        commit = False
        if not session:
            session = self.Session()
            commit = True
        threshold = datetime.now() - timedelta(seconds=self.maxtime)
        session.query(self.lock_cls).\
            filter(self.lock_cls.updated < threshold).\
            delete()
        if commit:
            session.commit()
        for name in list(self.locks.keys()):
            if self.locks[name]() is None:
                del self.locks[name]
