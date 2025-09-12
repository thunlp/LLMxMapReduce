import os
import logging
from typing import Protocol
from importlib import import_module
logger = logging.getLogger(__name__)
import json

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

    # Search related prompts
    SEARCH_SYSTEM_PROMPT_WITH_ABSTRACT: str
    SEARCH_SYSTEM_PROMPT_WITHOUT_ABSTRACT: str
    SEARCH_USER_PROMPT: str
    QUERY_REFINE_STOP_FLAG: str
    USER_CHECK_PROMPT: str
    LLM_CHECK_PROMPT: str

    # Orchestra related prompts
    ORCHESTRA_PROMPT: str
    SUMMARY_PROMPT: str
    POLISH_PROMPT: str
    CHART_PROMPT: str

    # Crawl related prompts
    CRAWL_FILTER_PROMPT_WITH_TOPIC: str
    SIMILARITY_PROMPT: str
    GENERATE_TITLE_PROMPT: str

    # LLM_search_prompts
    QUERY_EXPAND_PROMPT_WITH_ABSTRACT: str
    QUERY_EXPAND_PROMPT_WITHOUT_ABSTRACT: str
    SNIPPET_FILTER_PROMPT: str


class PromptManager:
    _instance = None
    _initialized = False
    DEFAULT_LANGUAGE = "en"
    config_file = "config/unified_config.json"

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not PromptManager._initialized:
            with open(self.config_file, 'r') as f:
                config = json.load(f)
            self.language = config.get("prompt_language", self.DEFAULT_LANGUAGE)
            
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

            self.language = self.DEFAULT_LANGUAGE
            module = import_module(
                f".prompts_{self.DEFAULT_LANGUAGE}", package="src.prompts"
            )
            self._prompts = module

    @property
    def prompts(self) -> PromptsProtocol:
        return self._prompts


_default_manager = PromptManager()

def __getattr__(name: str):
    return getattr(_default_manager.prompts, name)
