"""
test_redis_connectivity.py — Smoke test for Upstash Redis.
Verifies that the Redis URL and token from Cloud Run env vars
work for PING, HSET, HGETALL, and DELETE.
"""

import asyncio
from upstash_redis.asyncio import Redis


async def main():
    url = "https://civil-ox-146786.upstash.io"
    token = "gQAAAAAAAj1iAAIgcDJiYWY5NmZhN2RiNzc0ZDg4OWI4YTZkNWJmNTU1NDk1Yg"

    r = Redis(url=url, token=token)

    # 1. PING
    ping_result = await r.ping()
    assert ping_result is True or ping_result == "PONG", f"PING failed: {ping_result}"
    print("PASS: PING")

    # 2. HSET (field-by-field, the same pattern now used in botsort_tracker.py)
    await r.hset("test:smoke", "field1", "value1")
    await r.hset("test:smoke", "field2", "value2")
    print("PASS: HSET field-by-field")

    # 3. HGETALL
    data = await r.hgetall("test:smoke")
    assert data == {"field1": "value1", "field2": "value2"}, f"HGETALL mismatch: {data}"
    print(f"PASS: HGETALL — {data}")

    # 4. DELETE / cleanup
    await r.delete("test:smoke")
    remaining = await r.hgetall("test:smoke")
    assert remaining == {}, f"Key not deleted: {remaining}"
    print("PASS: DELETE")

    # 5. TTL / EXPIRE
    await r.hset("test:smoke_ttl", "k", "v")
    await r.expire("test:smoke_ttl", 60)
    ttl = await r.ttl("test:smoke_ttl")
    assert 1 <= ttl <= 60, f"TTL out of range: {ttl}"
    await r.delete("test:smoke_ttl")
    print(f"PASS: EXPIRE (TTL={ttl}s)")

    print("\n=== REDIS SMOKE TEST PASSED ===")


asyncio.run(main())