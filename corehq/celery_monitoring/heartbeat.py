from __future__ import absolute_import
from __future__ import print_function

import datetime

from celery.task import periodic_task
from django.core.cache import cache

from corehq.util.datadog.gauges import datadog_gauge


HEARTBEAT_FREQUENCY = datetime.timedelta(seconds=10)
HEARTBEAT_CACHE_TIMEOUT = datetime.timedelta(days=2)


class HeartbeatNeverRecorded(Exception):
    pass


class HeartbeatCache(object):
    def __init__(self, queue):
        self.queue = queue

    def _cache_key(self):
        return 'heartbeat:{}'.format(self.queue)

    def get(self):
        return cache.get(self._cache_key())

    def set(self, value):
        cache.set(self._cache_key(), value, timeout=HEARTBEAT_CACHE_TIMEOUT.total_seconds())

    def delete(self):
        cache.delete(self._cache_key())


class Heartbeat(object):
    def __init__(self, queue):
        self.queue = queue
        self._heartbeat_cache = HeartbeatCache(queue)

    def get_last_seen(self):
        value = self._heartbeat_cache.get()
        if value is None:
            raise HeartbeatNeverRecorded()
        else:
            return value

    def mark_seen(self):
        self._heartbeat_cache.set(datetime.datetime.utcnow())

    def clear_last_seen(self):
        """Only used in tests"""
        self._heartbeat_cache.delete()

    def get_blockage_duration(self):
        """
        Estimate the amount of time the queue has been blocked

        :returns a timedelta or raises HeartbeatNeverRecorded
        """
        # Subtract off the time between heartbeats
        # since we don't know how long it's been since the last heartbeat
        return max(datetime.datetime.utcnow() - self.get_last_seen() - HEARTBEAT_FREQUENCY,
                   datetime.timedelta(seconds=0))

    @property
    def periodic_task_name(self):
        return 'heartbeat__{}'.format(self.queue)

    def make_periodic_task(self):
        """
        Create a heartbeat @periodic_task specifically for self.queue

        This is called on python startup so should avoid network calls
        and anything else slow.
        """
        def heartbeat():
            try:
                datadog_gauge(
                    'commcare.celery.heartbeat.blockage_duration',
                    self.get_blockage_duration(),
                    tags=['celery_queue:{}'.format(self.queue)]
                )
            except HeartbeatNeverRecorded:
                pass
            self.mark_seen()

        heartbeat.func_name = self.periodic_task_name
        heartbeat.__name__ = self.periodic_task_name

        heartbeat = periodic_task(run_every=HEARTBEAT_FREQUENCY, queue=self.queue)(heartbeat)
        return heartbeat
