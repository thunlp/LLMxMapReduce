from typing import List
from src.data_structure.digest import Digest
import re
from ..utils.process_str import remove_illegal_bibkeys

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
