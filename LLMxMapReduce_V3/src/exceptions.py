
class BibkeyNotFoundError(Exception):
    def __init__(self, bibkeys, content, legal_bibkeys):
        self.bibkeys = bibkeys
        super().__init__(f"Illegal bibkeys: {bibkeys}, all legal bibkeys: {legal_bibkeys}\n from content \n{content}")

class StructureNotCorrespondingError(Exception):
    pass

class MdNotFoundError(Exception):
    
    def __init__(self, raw_content):
        self.raw_content = raw_content
        super().__init__(f"Markdown code block not found in \n{raw_content}")

class HumanInteractionError(Exception):
    # BUG: 需要根据human交互时的情况设计一个human相关的异常类
    pass
    # def __init__(self, message="Human input is required to proceed."):
        # super().__init__(message)