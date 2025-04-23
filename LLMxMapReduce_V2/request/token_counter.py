import logging
from tabulate import tabulate

logger = logging.getLogger(__name__)


def track_completion_calls(cls):
    original_completion = cls.completion

    def _completion_counter():
        cls._calls_count += 1
        logger.info(f"Current total count of openai api calls: {cls._calls_count}")
        return
    
    def token_logger(self, *args, **kwargs):
        answer = original_completion(self, *args, **kwargs)
        _completion_counter()
        table_data = []
        for count, token_usage in enumerate(cls._token_usage_history):
            if token_usage is None:
                token_usage_info = "missing"
            else:
                token_usage_info = (
                    f"(completion_tokens={token_usage.completion_tokens}, "
                    f"prompt_tokens={token_usage.prompt_tokens}, "
                    f"total_tokens={token_usage.total_tokens})"
                )
            table_data.append([count+1, token_usage_info])
        logger.info(tabulate(
            table_data, 
            headers=["Index", "Token Usage"], 
            tablefmt="grid"
        ))
        return answer

    cls.completion = token_logger
    return cls
