"""Queue dependency probes, without a broker or external provider requests.

Real delivery remains covered by test_analysis_runs_integration.py. These probes
catch the metadata/transport mismatch before a worker opens a Redis connection.
"""

from importlib.metadata import requires, version

import pytest
import redis
from kombu.transport.redis import Channel
from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet


@pytest.mark.parametrize(
    ("distribution", "tested_series"),
    [("celery", ">=5.7.0,<5.8"), ("kombu", ">=5.7.0,<5.8"), ("redis", ">=8.1.0,<8.2")],
)
def test_queue_uses_the_reviewed_maintained_series(distribution, tested_series):
    assert version(distribution) in SpecifierSet(tested_series)


def test_redis_satisfies_installed_queue_transport_extras():
    for distribution in ("celery", "kombu"):
        for raw_requirement in requires(distribution):
            requirement = Requirement(raw_requirement)
            if requirement.name != "redis":
                continue
            if requirement.marker and not requirement.marker.evaluate({"extra": "redis"}):
                continue
            assert requirement.specifier.contains(version("redis")), (
                f"{distribution} {version(distribution)} requires {requirement}; "
                f"installed redis-py is {version('redis')}"
            )


def test_kombu_can_select_the_real_redis_client_without_connecting():
    # Avoid Channel.__init__, which opens a broker connection. Do not mock the
    # transport's actual redis-py version guard or client-selection implementation.
    channel = Channel.__new__(Channel)
    channel.global_keyprefix = ""
    assert channel._get_client() is redis.Redis
