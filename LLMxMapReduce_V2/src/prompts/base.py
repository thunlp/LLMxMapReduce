import os
import logging
from typing import Protocol
from importlib import import_module

logger = logging.getLogger(__name__)


class PromptsProtocol(Protocol):
    """Protocol defining all required prompts for the survey writing system"""

    # Group related prompts
    GROUP_PROMPT: str

    # Outline related prompts
    INIT_OUTLINE_PROMPT: str
    CONCAT_OUTLINE_PROMPT: str
    MODIFY_OUTLINE_PROMPT: str
    OUTLINE_CONVOLUTION_PROMPT: str
    OUTLINE_ENTROPY_PROMPT: str
    RESIDUAL_MODIFY_OUTLINE_PROMPT: str

    # Digest related prompts
    SINGLE_DIGEST_PROMPT: str
    DIGEST_BASE_PROMPT: str
    DIGEST_FREE_PROMPT: str

    # Orchestra related prompts
    ORCHESTRA_PROMPT: str
    SUMMARY_PROMPT: str
    POLISH_PROMPT: str
    CHART_PROMPT: str

    # Search related prompts
    QUERY_EXPAND_PROMPT_WITH_ABSTRACT: str
    QUERY_EXPAND_PROMPT_WITHOUT_ABSTRACT: str
    LLM_CHECK_PROMPT: str
    SNIPPET_FILTER_PROMPT: str

    # Crawl related prompts
    PAGE_REFINE_PROMPT: str
    SIMILARITY_PROMPT: str


class PromptManager:
    _instance = None
    _initialized = False
    DEFAULT_LANGUAGE = "en"
    ENV_VAR_NAME = "PROMPT_LANGUAGE"

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not PromptManager._initialized:
            # 从环境变量读取语言设置,如果未设置则使用默认值
            self.language = os.getenv(self.ENV_VAR_NAME, self.DEFAULT_LANGUAGE)
            self._load_prompts()
            PromptManager._initialized = True

    def _load_prompts(self):
        """Load prompts based on language setting"""
        try:
            module = import_module(f".prompts_{self.language}", package="src.prompts")
            self._prompts = module
        except ImportError:
            logger.warning(
                f"Unsupported language: {self.language}, falling back to {self.DEFAULT_LANGUAGE}"
            )
            # 如果指定语言不可用,回退到默认语言
            self.language = self.DEFAULT_LANGUAGE
            module = import_module(
                f".prompts_{self.DEFAULT_LANGUAGE}", package="src.prompts"
            )
            self._prompts = module

    @property
    def prompts(self) -> PromptsProtocol:
        return self._prompts


# 创建默认实例
_default_manager = PromptManager()


# 不再需要 init_prompts 函数,因为语言设置现在从环境变量获取
def __getattr__(name: str):
    return getattr(_default_manager.prompts, name)
