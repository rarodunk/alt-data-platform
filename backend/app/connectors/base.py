from abc import ABC, abstractmethod
import logging
import json
import os
import hashlib
from datetime import datetime
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class BaseConnector(ABC):
    """Abstract base for all data source connectors."""

    name: str = "base"
    cache_dir: str = "/tmp/altdata_cache"
    cache_ttl_hours: int = 6

    def __init__(self):
        os.makedirs(self.cache_dir, exist_ok=True)

    def _cache_key(self, params: Dict) -> str:
        key = f"{self.name}_{json.dumps(params, sort_keys=True)}"
        return hashlib.md5(key.encode()).hexdigest()

    def _read_cache(self, params: Dict) -> Optional[Any]:
        path = os.path.join(self.cache_dir, f"{self._cache_key(params)}.json")
        if not os.path.exists(path):
            return None
        mtime = os.path.getmtime(path)
        if datetime.now().timestamp() - mtime > self.cache_ttl_hours * 3600:
            return None
        with open(path) as f:
            return json.load(f)

    def _write_cache(self, params: Dict, data: Any):
        path = os.path.join(self.cache_dir, f"{self._cache_key(params)}.json")
        with open(path, "w") as f:
            json.dump(data, f)

    @abstractmethod
    def fetch(self, **kwargs) -> List[Dict[str, Any]]:
        pass

    def fetch_with_cache(self, **kwargs) -> List[Dict[str, Any]]:
        cached = self._read_cache(kwargs)
        if cached is not None:
            logger.info(f"[{self.name}] Cache hit for {kwargs}")
            return cached
        result = self.fetch(**kwargs)
        if result:
            self._write_cache(kwargs, result)
        return result
