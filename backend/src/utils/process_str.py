import re
import logging
from difflib import SequenceMatcher
from src.exceptions import MdNotFoundError, BibkeyNotFoundError

logger = logging.getLogger(__name__)

def parse_md_content(raw_content, label="markdown"):
    raw_content = re.sub(r"```LABEL\s*?```LABEL".replace("LABEL", label), f"```{label}", raw_content)
    content_reg = re.compile(
        r"```LABEL\n(.*?)\n```".replace("LABEL", label) , re.DOTALL
    )
    md_content = content_reg.search(raw_content)
    if md_content:
        md_content = md_content.group(1).strip()
    else:
        raise MdNotFoundError(raw_content=raw_content)
    if "```" in md_content:
        raise MdNotFoundError(raw_content=raw_content)
    return md_content

def get_section_title(content):
    title_match = re.match(r"^(#+)\s*[\d\.]*\s+(.*)", content)
    if title_match:
        hashes, title = title_match.groups()
        title = remove_illegal_bibkeys(title, [], raise_error=False, raise_warning=False)
    else:
        hashes, title = "", ""
    return len(hashes), title

def str2list(raw_str):
    str_list = raw_str.split(",")
    str_list = [s.replace("[", "").replace("]", "").replace("\'", "").replace("\"", "").strip() for s in str_list]
    str_list = [s for s in str_list if s]
    return str_list

def list2str(str_list):
    str_list = [f"'{s}'" for s in str_list if s]
    if len(str_list) == 0:
        return ""
    else:
        return "[" + ", ".join(str_list) + "]"
    
def remove_illegal_bibkeys(content, legal_bibkeys, raise_error=False, raise_warning=True):
    def get_rest_bibkeys(content, references_reg):
        current_bibkeys = set()
        for match in references_reg.finditer(content):
            bibkey_str = match.group(1)
            bibkey_list = str2list(bibkey_str)
            for bibkey in bibkey_list:
                current_bibkeys.add(bibkey.strip())

        rest_bibkeys = current_bibkeys - set(legal_bibkeys)
        return rest_bibkeys

    # 保存数学公式
    math_placeholders = {}
    math_count = 0
    
    # 处理块级公式
    block_math_pattern = r'\$\$[^\$]+\$\$'
    for match in re.finditer(block_math_pattern, content):
        placeholder = f'MATH_PLACEHOLDER_{math_count}'
        math_placeholders[placeholder] = match.group(0)
        content = content.replace(match.group(0), placeholder)
        math_count += 1
    
    # 处理行内公式
    inline_math_pattern = r'\$[^\$]+\$'
    for match in re.finditer(inline_math_pattern, content):
        placeholder = f'MATH_PLACEHOLDER_{math_count}'
        math_placeholders[placeholder] = match.group(0)
        content = content.replace(match.group(0), placeholder)
        math_count += 1
    
    # 原有的引用处理逻辑
    references_reg = re.compile(r"(\[.*?\])", re.DOTALL)
    content = references_reg.sub(lambda m: m.group(0).replace("-", "_").replace("'", "'").replace("'", "'"), content)
    
    rest_bibkeys = get_rest_bibkeys(content, references_reg)
    
    for rest_bibkey in list(rest_bibkeys):
        for legal_bibkey in legal_bibkeys:
            if SequenceMatcher(None, rest_bibkey, legal_bibkey).ratio() > 0.8:
                content = content.replace(rest_bibkey, legal_bibkey)
                rest_bibkeys.remove(rest_bibkey)
                break
    
    if rest_bibkeys and raise_error:
        raise BibkeyNotFoundError(bibkeys=rest_bibkeys, content=content, legal_bibkeys=legal_bibkeys)
    elif rest_bibkeys:
        if raise_warning:
            logger.warning(f"Remove illegal bibkeys: {rest_bibkeys}, \nall legal bibkeys: {legal_bibkeys}")
        ref_lists = references_reg.findall(content)
        if ref_lists:
            for ref_str in set(ref_lists):
                ref_result = str2list(ref_str)
                for ref in ref_result[:]:
                    if ref in rest_bibkeys:
                        ref_result.remove(ref)
                ref_result = list(set(ref_result))
                content = content.replace(ref_str, list2str(ref_result))
    
    content = process_bibkeys(content)
    
    # 还原数学公式
    for placeholder, math_content in math_placeholders.items():
        content = content.replace(placeholder, math_content)
    
    return content

def process_bibkeys(raw_content):
    raw_content = re.sub(r'\[\s*\]', '', raw_content)
    references_reg = re.compile(r"(\[.*?\])", re.DOTALL)
    bibkeys = references_reg.findall(raw_content)
    bibkeys = set([bibkey for bibkey in bibkeys])
    for bibkey in bibkeys:
        new_bibkey = list2str(str2list(bibkey))
        if new_bibkey != bibkey:
            raw_content = raw_content.replace(bibkey, new_bibkey)
    return raw_content

def remove_brackets_and_content(text):
    # Use regex to match brackets and their content
    cleaned_text = re.sub(r'\[.*?\]', '', text)
    # Remove any extra spaces left behind after removing brackets
    cleaned_text = re.sub(r'\s+\.', '.', cleaned_text)  # Ensure space before period is removed
    cleaned_text = re.sub(r'\s{2,}', ' ', cleaned_text)  # Replace multiple spaces with a single space
    return cleaned_text.strip()

def proc_title_to_str(origin_title):
    title = origin_title.lower().strip()
    title = title.replace("-", "_")
    title = re.sub(r'[^\w\s\_]', '', title)
    title = title.replace(" ", "_")
    title = re.sub(r'_{2,}', '_', title)
    return title