from .base import PromptsProtocol, PromptManager

_default_manager = PromptManager()

# Group related prompts
GROUP_PROMPT = _default_manager.prompts.GROUP_PROMPT

# Outline related prompts
INIT_OUTLINE_PROMPT = _default_manager.prompts.INIT_OUTLINE_PROMPT
CONCAT_OUTLINE_PROMPT = _default_manager.prompts.CONCAT_OUTLINE_PROMPT
MODIFY_OUTLINE_PROMPT = _default_manager.prompts.MODIFY_OUTLINE_PROMPT
OUTLINE_CONVOLUTION_PROMPT = _default_manager.prompts.OUTLINE_CONVOLUTION_PROMPT
OUTLINE_ENTROPY_PROMPT = _default_manager.prompts.OUTLINE_ENTROPY_PROMPT
RESIDUAL_MODIFY_OUTLINE_PROMPT = _default_manager.prompts.RESIDUAL_MODIFY_OUTLINE_PROMPT

# Digest related prompts
SINGLE_DIGEST_PROMPT = _default_manager.prompts.SINGLE_DIGEST_PROMPT
DIGEST_BASE_PROMPT = _default_manager.prompts.DIGEST_BASE_PROMPT
DIGEST_FREE_PROMPT = _default_manager.prompts.DIGEST_FREE_PROMPT

# Search related prompts
SEARCH_SYSTEM_PROMPT_WITH_ABSTRACT = (
    _default_manager.prompts.SEARCH_SYSTEM_PROMPT_WITH_ABSTRACT
)
SEARCH_SYSTEM_PROMPT_WITHOUT_ABSTRACT = (
    _default_manager.prompts.SEARCH_SYSTEM_PROMPT_WITHOUT_ABSTRACT
)
SEARCH_USER_PROMPT = _default_manager.prompts.SEARCH_USER_PROMPT
QUERY_REFINE_STOP_FLAG = _default_manager.prompts.QUERY_REFINE_STOP_FLAG
USER_CHECK_PROMPT = _default_manager.prompts.USER_CHECK_PROMPT
LLM_CHECK_PROMPT = _default_manager.prompts.LLM_CHECK_PROMPT

# Orchestra related prompts
ORCHESTRA_PROMPT = _default_manager.prompts.ORCHESTRA_PROMPT
SUMMARY_PROMPT = _default_manager.prompts.SUMMARY_PROMPT
POLISH_PROMPT = _default_manager.prompts.POLISH_PROMPT
CHART_PROMPT = _default_manager.prompts.CHART_PROMPT

# Crawl related prompts
CRAWL_FILTER_PROMPT_WITH_TOPIC = _default_manager.prompts.CRAWL_FILTER_PROMPT_WITH_TOPIC
SIMILARITY_PROMPT = _default_manager.prompts.SIMILARITY_PROMPT
GENERATE_TITLE_PROMPT = _default_manager.prompts.GENERATE_TITLE_PROMPT

prompt_manager = _default_manager

__all__ = [
    "GROUP_PROMPT",
    "INIT_OUTLINE_PROMPT",
    "CONCAT_OUTLINE_PROMPT",
    "MODIFY_OUTLINE_PROMPT",
    "OUTLINE_CONVOLUTION_PROMPT",
    "OUTLINE_ENTROPY_PROMPT",
    "RESIDUAL_MODIFY_OUTLINE_PROMPT",
    "SINGLE_DIGEST_PROMPT",
    "DIGEST_BASE_PROMPT",
    "DIGEST_FREE_PROMPT",
    "SEARCH_SYSTEM_PROMPT_WITH_ABSTRACT",
    "SEARCH_SYSTEM_PROMPT_WITHOUT_ABSTRACT",
    "SEARCH_USER_PROMPT",
    "QUERY_REFINE_STOP_FLAG",
    "USER_CHECK_PROMPT",
    "LLM_CHECK_PROMPT",
    "ORCHESTRA_PROMPT",
    "SUMMARY_PROMPT",
    "CHART_PROMPT",
    "CRAWL_FILTER_PROMPT_WITH_TOPIC",
    "SIMILARITY_PROMPT",
    "GENERATE_TITLE_PROMPT",
    "prompt_manager",
    "PromptsProtocol",
]
