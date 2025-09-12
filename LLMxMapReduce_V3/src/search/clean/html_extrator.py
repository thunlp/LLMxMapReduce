# Copyright (c) 2025, NVIDIA CORPORATION.  All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


import os
import json
import subprocess
import unicodedata
import warnings
from abc import ABC, abstractmethod
from copy import deepcopy
from logging import Logger
from typing import Literal
from urllib.parse import urlparse

import justext
import lxml
import pycld2 as cld2
from charset_normalizer import detect
from resiliparse.extract.html2text import extract_plain_text



class DocumentExtractor(ABC):
    """Abstract class for extracting text from records read from disk"""

    def __init__(self):
        super().__init__()

    @abstractmethod
    def extract(self, content: str) -> dict[str, str]:
        pass

NON_SPACED_LANGUAGES = ["THAI", "CHINESE", "JAPANESE", "KOREAN"]


def decode_html(html_bytes: bytes) -> str | None:
    # Convert from bytes to text using utf-8 encoding
    try:
        return html_bytes.decode("utf-8")
    except UnicodeDecodeError:
        # If utf-8 fails, try to find a different encoding
        return try_decode_with_detected_encoding(html_bytes)


def try_decode_with_detected_encoding(html_bytes: bytes) -> str | None:
    detected_encoding = detect(html_bytes)["encoding"]
    bad_detection = not detected_encoding or detected_encoding == "utf-8"
    if bad_detection:
        return None
    try:
        return html_bytes.decode(detected_encoding)
    except:  # noqa: E722
        return None


def lang_detect(decoded_html: str) -> str:
    try:
        details = cld2.detect(decoded_html)[2]
    except Exception:  # noqa: BLE001
        # Remove control characters
        cleaned_html = "".join(i for i in decoded_html if unicodedata.category(i)[0] != "C")
        details = cld2.detect(cleaned_html)[2]

    return details[0][0].upper()


class HTMLExtractorAlgorithm(ABC):
    @abstractmethod
    def extract_text(self, html: str, stop_words: frozenset[str], language: str) -> list[str] | None:
        pass


class JusTextExtractor(HTMLExtractorAlgorithm):
    def __init__(  # noqa: PLR0913
        self,
        length_low: int = 70,
        length_high: int = 200,
        stopwords_low: float = 0.30,
        stopwords_high: float = 0.32,
        max_link_density: float = 0.1,
        max_heading_distance: int = 200,
        no_headings: bool = False,
        is_boilerplate: bool | None = None,
        logger: Logger | None = None,
    ):
        """
        Initialize the jusText text extraction algorithm with specified parameters.

        jusText is a tool for removing boilerplate content, such as navigation links, headers, and footers from HTML pages.
        It is designed to preserve mainly text containing full sentences and it is therefore well suited for creating linguistic resources such as Web corpora.
        The key idea is that long blocks can often be classified with high confidence, while shorter blocks require context-based adjustments.

        Here is an overview of the jusText algorithm:
            • Segmentation: The document is split into textual blocks based on HTML tags that typically define separate sections (e.g., <div>, <p>, <table>).
            • Preprocessing: Contents of <header>, <style>, and <script> tags are removed.
                Certain elements (e.g., <select>, copyright symbols) are immediately classified as boilerplate.
            • Context-Free Classification: Each block is classified as:
                - Bad (boilerplate) if it has high link density.
                - Short if it is too small to be classified reliably.
                - Near-Good if it has a moderate density of stopwords.
                - Good (main content) if it is long and contains many stopwords.
            • Context-Sensitive Classification: Blocks that were classified as short or near-good are reclassified based on surrounding blocks.
                The assumption is that main content clusters together, as does boilerplate.
            • Headings Processing: Header elements (e.g., <h1>, <h2>) are treated separately to ensure useful headings are preserved.
                Short headers near good content may be reclassified as near-good or good.

        Please refer to the jusText documentation for more details: https://corpus.tools/wiki/Justext/Algorithm

        Args:
            length_low: Minimum length of text to be considered for extraction.
            length_high: Maximum length of text to be considered for extraction.
            stopwords_low: Minimum proportion of stopwords in the text to be considered for extraction.
            stopwords_high: Maximum proportion of stopwords in the text to be considered for extraction.
            max_link_density: Maximum allowed link density in the text.
            max_heading_distance: Maximum distance from a heading to consider text for extraction.
            no_headings: If True, text extraction will ignore headings.
            is_boilerplate: If True, text extraction will ignore boilerplate content.
                Default is True for space-separated languages and False for non-space-separated languages
                (Thai, Chinese, Japanese, and Korean).
            logger: Optional logger instance for logging messages.

        """
        self.length_low = length_low
        self.length_high = length_high
        self.stopwords_low = stopwords_low
        self.stopwords_high = stopwords_high
        self.max_link_density = max_link_density
        self.max_heading_distance = max_heading_distance
        self.no_headings = no_headings
        self.is_boilerplate = is_boilerplate
        self.logger = logger

    def extract_text(self, html: str, stop_words: frozenset[str], language: str) -> list[str] | None:
        # Segment the HTML into paragraphs
        # import pdb; pdb.set_trace()
        try:
            # Form the DOM tree
            dom = justext.core.html_to_dom(html)
            cleaned_dom = justext.core.preprocessor(dom)
            # Get the paragraphs from the DOM
            handler = justext.core.ParagraphMaker()
            lxml.sax.saxify(cleaned_dom, handler)
        except (lxml.etree.ParserError, ValueError, Exception):
            # Return nothing when we cannot segment the document
            if self.logger is not None:
                self.logger.info("Could not segment paragaphs in the document")
            return None
        # paragraphs为空
        paragraphs = handler.paragraphs

        # Context free classification
        justext.core.classify_paragraphs(
            paragraphs,
            stop_words,
            self.length_low,
            self.length_high,
            self.stopwords_low,
            self.stopwords_high,
            self.max_link_density,
            self.no_headings,
        )

        # Copy the context free class to the class_style
        # This handles the headings as described in the
        # documentation
        for paragraph in paragraphs:
            paragraph.class_type = paragraph.cf_class

        # Context sensitive classification
        justext.core.revise_paragraph_classification(
            paragraphs,
            self.max_heading_distance,
        )

        if self.is_boilerplate is None:
            if language in NON_SPACED_LANGUAGES:
                warnings.warn("Disabling is_boilerplate check for jusText extraction.", stacklevel=2)
                is_boilerplate = False
            else:
                is_boilerplate = True

        else:
            is_boilerplate = self.is_boilerplate

        if is_boilerplate:
            return [p.text for p in paragraphs if not p.is_boilerplate]

        else:
            return [p.text for p in paragraphs]


class ResiliparseExtractor(HTMLExtractorAlgorithm):
    def __init__(
        self,
        required_stopword_density: float = 0.32,
        main_content: bool = True,
        alt_texts: bool = False,
    ):
        """
        Initialize the Resiliparse text extraction algorithm with specified parameters.

        The Resiliparse algorithm extracts structural or semantic information from noisy raw web data for further processing,
        such as (main) content extraction / boilerplate removal, schema extraction, general web data cleansing, and more.

        It is implemented via the `extract_plain_text` function in the `resiliparse.extract.html2text` module.
        Resiliparse HTML2Text is a very fast and rule-based plain text extractor for HTML pages which uses the Resiliparse DOM parser.
        The `extract_plain_text` function extracts all visible text nodes inside the HTML document's <body>.
        Only <script>, <style> and a few other (generally) invisible elements are skipped and very basic ASCII formatting is applied.

        Please refer to the Resiliparse documentation for more details: https://resiliparse.chatnoir.eu/en/latest/man/extract/html2text.html

        NeMo Curator has added a stopword density filter to the Resiliparse extraction process, which requires that a paragraph contains a certain proportion of stopwords.

        Args:
            required_stopword_density: Proportion of stopwords required preserve an extracted paragraph.
                Studies on stopword lists and their distribution in various text corpora often
                suggest that around 30-40% of a typical English text consists of stopwords.
            main_content: Whether to apply simple heuristics for extracting only "main-content" elements.
            alt_texts: Whether to preserve alternative text descriptions (e.g., for images).

        """
        self.required_stopword_density = required_stopword_density
        self.main_content = main_content
        self.alt_texts = alt_texts

    def extract_text(self, html: str, stop_words: frozenset[str], language: str) -> list[str] | None:
        # import pdb; pdb.set_trace()
        text = extract_plain_text(html, main_content=self.main_content, alt_texts=self.alt_texts)

        paragraphs = list(filter(None, text.split("\n")))

        if language in NON_SPACED_LANGUAGES:
            warnings.warn("stopword_density is ignored for non-space-separated languages.", stacklevel=2)
            result = paragraphs
        else:
            result = []

            for paragraph in paragraphs:
                words = paragraph.split()
                length = len(words)

                if length == 0:
                    continue

                stopwords = [word for word in words if word in stop_words]
                stopword_density = len(stopwords) / length

                if stopword_density >= self.required_stopword_density:
                    result.append(paragraph)

        return result

def get_stop_list_dict(languages: list[str] | None = None) -> dict[str, frozenset[str]]:
    if languages is None:
        languages = []

    # Name mapping for language names from CLD2 (values)
    # and jusText (keys)
    lang_map = {
        "Haitian": "HAITIAN_CREOLE",
        "Norwegian_Bokmal": "NORWEGIAN",
        "Norwegian_Nynorsk": "NORWEGIAN_N",
        "Waray_Waray": "WARAY_PHILIPPINES",
    }

    # List obtained from https://github.com/stopwords-iso/stopwords-ja
    from ja_stopwords import ja_stopwords

    # List obtained from https://github.com/stopwords-iso/stopwords-th
    from th_stopwords import th_stopwords

    # List obtained from https://github.com/stopwords-iso/stopwords-zh
    from zh_stopwords import zh_stopwords

    from en_stopwords import en_stopwords

    custom_stopwords = {
        "THAI": th_stopwords,
        "CHINESE": zh_stopwords,
        "JAPANESE": ja_stopwords,
        "ENGLISH": en_stopwords,
    }

    if len(languages) == 0:
        languages = justext.get_stoplists()

        # Remove Latin as it yields a lot of low quality documents
        languages = list(languages)
        languages.remove("Latin")

        # Manually add Thai, Chinese, and Japanese
        languages.append("THAI")
        languages.append("CHINESE")
        languages.append("JAPANESE")
        languages.append("ENGLISH")

        languages = frozenset(languages)

    stop_list_dict = {}
    for language in languages:
        lang_key = lang_map[language] if language in lang_map else language.upper()

        if lang_key in custom_stopwords:
            stop_list_dict[lang_key] = custom_stopwords[lang_key]
        else:
            stop_list_dict[lang_key] = justext.get_stoplist(language)
    return stop_list_dict


def get_all_stop_words() -> frozenset[str]:
    stop_words = set()
    for language in justext.get_stoplists():
        stop_words.update(justext.get_stoplist(language))

    return frozenset(stop_words)



class CommonCrawlWARCExtractor(DocumentExtractor):
    def __init__(
        self,
        algorithm: HTMLExtractorAlgorithm | None = None,
        stop_lists: dict[str, frozenset[str]] | None = None,
    ):
        if algorithm is None:
            algorithm = JusTextExtractor()

        if stop_lists is not None:
            self._stop_lists = stop_lists
        else:
            self._stop_lists = get_stop_list_dict()

        self.algorithm = algorithm
        super().__init__()

    def extract(self, content: str) -> dict[str, str] | None:
        content = bytes(content, "utf-8")
        html = decode_html(content)
        # html = content
        if html is not None:
            # Language detection and HTML extraction
            lang = lang_detect(html)
            text = None
            print(lang)
            # import pdb; pdb.set_trace()
            if lang in self._stop_lists:
                text = self.algorithm.extract_text(html, self._stop_lists[lang], lang)
            if text is not None:
                if len(text) > 0:
                    text = "\n\n".join(text)
                    return {"language": lang, "text": text}
                else:
                    # print(f"提取内容为空: {html}")
                    return None
        return None
