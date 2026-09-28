import hashlib
import time
from typing import Any, Dict, Tuple
from app.schemas.product import ProductInput

class ComplianceResponseCache:
    def __init__(self, ttl_seconds: int = 300):
        self.ttl_seconds = ttl_seconds
        # key -> (response_dict, expiry_time)
        self._cache: Dict[str, Tuple[dict, float]] = {}

    def _generate_key(self, product: ProductInput) -> str:
        norm_cat = (product.category or "").lower().strip()
        norm_subcat = (product.sub_category or "").lower().strip()
        norm_mat = ",".join(sorted([m.lower().strip() for m in (product.materials or [])]))
        norm_scale = product.manufacturer_scale.lower()
        norm_import = str(product.is_imported)
        norm_lang = product.lang.lang_code.lower()

        raw_str = f"{norm_cat}|{norm_subcat}|{norm_mat}|{norm_scale}|{norm_import}|{norm_lang}"
        return hashlib.sha256(raw_str.encode("utf-8")).hexdigest()

    def get(self, product: ProductInput) -> dict | None:
        key = self._generate_key(product)
        now = time.time()
        if key in self._cache:
            resp_dict, expiry = self._cache[key]
            if now < expiry:
                return resp_dict
            else:
                del self._cache[key]
        return None

    def set(self, product: ProductInput, response_dict: dict):
        # Cache must NOT apply if unverified_claims is non-empty
        if response_dict.get("unverified_claims"):
            return
        key = self._generate_key(product)
        expiry = time.time() + self.ttl_seconds
        self._cache[key] = (response_dict, expiry)

    def clear(self):
        self._cache.clear()

response_cache = ComplianceResponseCache(ttl_seconds=300)
