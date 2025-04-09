
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