from typing import List, Type, TypeVar
from src.data_structure.digest import Digest
import re
from ..utils.process_str import remove_illegal_bibkeys
import json
T = TypeVar('T', bound='Feedback')

import logging

logger = logging.getLogger(__name__)


class Feedback:

    def __init__(
            self,
            src_outline: str,
            content: str,
            digests: List[Digest],
    ):
        self.src_outline = src_outline
        self.digests = digests
        self.score = 0
        self.content = self._remove_not_exist_bibkey(content)
        self.eval_detail = None

    def _remove_not_exist_bibkey(self, content):
        bibkeys = set()
        for digest in self.digests:
            bibkeys.update(digest.bibkeys)

        cite_reg = re.compile(r"\[([^\]]+)\]")
        for match in cite_reg.finditer(self.src_outline):
            bibkey_str = match.group(1)
            bibkey_list = bibkey_str.split(",")
            for bibkey in bibkey_list:
                bibkeys.add(bibkey.strip())

        content = remove_illegal_bibkeys(content, bibkeys)
        return content

    def to_json(self) -> str:
        data = {
            "src_outline": self.src_outline,
            "content": self.content,
            "score": self.score,
            "eval_detail": self.eval_detail,
            "digests": [json.loads(digest.to_json()) for digest in self.digests]  # 使用 Digest 的 to_json()
        }
        
        data = {k: v for k, v in data.items() if v is not None}
        
        try:
            return json.dumps(data, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"JSON 序列化失败: {e}")
            return "{}"

    @classmethod
    def from_json(cls: Type[T], json_str: str) -> T:
        try:
            data = json.loads(json_str)

            digests = [Digest.from_json(json.dumps(digest_data)) for digest_data in data.get("digests", [])]

            instance = cls(
                src_outline=data.get("src_outline", ""),
                content=data.get("content", ""),
                digests=digests
            )

            instance.score = data.get("score", 0)
            instance.eval_detail = data.get("eval_detail", None)
            
            return instance
            
        except Exception as e:
            logger.error(f"JSON 反序列化失败: {e}")
            raise ValueError("无效的 JSON 格式") from e