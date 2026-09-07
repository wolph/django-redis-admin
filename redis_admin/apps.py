from __future__ import annotations

from django.apps import AppConfig


class RedisAdminConfig(AppConfig):
    # Both attributes are declared on AppConfig, so re-annotating them here
    # would narrow the base class types.
    name = 'redis_admin'
    verbose_name = 'Redis'
