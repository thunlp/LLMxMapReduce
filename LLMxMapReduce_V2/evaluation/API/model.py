from request import RequestWrapper
import logging
logger = logging.getLogger(__name__)

class APIModel:
    def __init__(self, model, infer_type):
        self.model = model
        self.request = RequestWrapper(model, infer_type)
        
    def __req(self, text, temperature=0):
        result = None
        retry = 3
        while retry > 0:
            try:
                result = self.request.completion(text, temperature=temperature)
                break
            except ValueError as e:
                temperature += 0.1
                logger.warning(f"RequestException: {e} ")
                retry -= 1

        return result
 
    def chat(self, text, temperature=0):
        response = self.__req(text, temperature=temperature)
        return response
