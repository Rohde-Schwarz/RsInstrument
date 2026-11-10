"""
Cached discovery with Discovery and optional file store.
"""

from pathlib import Path

from RsInstrument import Discovery, FileDiscoveryCache

# In-memory TTL cache (default 30 s)
discovery = Discovery(identify=False, ttl_s=30.0)
result = discovery.get()
print(f"source={result.source}, count={len(result.snapshot.instruments)}")

# Second call within TTL hits the cache
cached = discovery.get()
print(f"source={cached.source}")

# Force a live rescan
live = discovery.refresh()
print(f"source={live.source}")

# Optional: persist across process restarts with a JSON file cache
file_cache = FileDiscoveryCache(Path.home() / ".cache" / "rsinstrument" / "discovery.json")
persistent = Discovery(ttl_s=60.0, cache=file_cache)
print(persistent.get().source)
