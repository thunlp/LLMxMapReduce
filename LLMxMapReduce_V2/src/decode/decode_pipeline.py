import json
import os
import re
import gevent
from async_d import Node
from async_d import Sequential
from gevent.fileobject import FileObject
from gevent.lock import Semaphore
from gevent import sleep
import logging
from src.data_structure import Survey
from src.data_structure.content import ContentNode
from .orchestra_module import OrchestraModule
from .figure_module import FigureModule
from src.utils.process_str import str2list, remove_illegal_bibkeys

logger = logging.getLogger(__name__)


class DecodePipeline(Sequential):
    def __init__(self, config, output_file, worker_num=10):
        worker_num = worker_num * 10
        self.config = config
        self.output_file = output_file
        self.dict_semaphore = Semaphore(1)
        self.executing_survey = {}  # title: survey

        self.register_node = Node(
            self.register_survey,
            discard_none_output=True,
            worker_num=worker_num,
            queue_size=worker_num,
        )
        self.unpack_node = Node(
            self.unpack_survey, worker_num=worker_num, queue_size=worker_num
        )
        self.orchestra_module = OrchestraModule(self.config)
        self.orchestra_node = Node(self.orchestra_module, worker_num=worker_num)
        self.assemble_node = Node(
            self.assemble_survey,
            worker_num=worker_num,
            queue_size=worker_num,
            discard_none_output=True,
        )
        self.chart_module = FigureModule(self.config)
        self.chart_node = Node(
            self.chart_module, worker_num=worker_num, queue_size=worker_num
        )
        self.cite_node = Node(
            self.change_bibkey_to_index, worker_num=worker_num, queue_size=worker_num
        )
        self.save_node = Node(
            self.save_survey,
            no_output=True,
            worker_num=worker_num,
            queue_size=worker_num,
        )
        super().__init__(
            [
                self.register_node,
                self.unpack_node,
                self.orchestra_node,
                self.assemble_node,
                self.cite_node,
                self.chart_node,
                self.save_node,
            ]
        )
        self.unpack_task = gevent.spawn(self._get_data_from_registered_survey)

    def register_survey(self, survey: Survey):
        survey.init_content()
        with self.dict_semaphore:
            self.executing_survey[survey.survey_label] = (survey, iter(survey.content))
        logger.info(f"Register survey: {survey.survey_label}")

    def _get_data_from_registered_survey(self):
        while True:
            with self.dict_semaphore:
                for survey in self.executing_survey.values():
                    try:
                        content = next(survey[1])
                        if content:
                            self.unpack_node.put(content)
                    except StopIteration:
                        pass
            sleep(1)

    def unpack_survey(self, content: ContentNode):
        if content:
            logger.info(
                f"Unpack section: '{content.title(with_index=True)}' of '{content.survey_title}'"
            )
        return content

    def assemble_survey(self, content_node: ContentNode):
        survey = self.executing_survey[content_node.survey_label][0]
        survey.add_content(content_node)
        if survey.is_content_generate_finish:
            with self.dict_semaphore:
                self.executing_survey.pop(content_node.survey_label)
            logger.info(f"Assemble finished: Survey {survey.survey_label}.")
            return survey

    def assemble_criteria(self, survey):
        if survey is None:
            return False
        elif isinstance(survey, Survey):
            return True
        else:
            raise ValueError(f"Invalid survey type, current data type {type(survey)}")

    def change_bibkey_to_index(self, survey):
        cite_reg = re.compile(r"\[([^\]]+)\]")
        bibkeys = list(survey.papers.keys())
        bibkey_count_dict = {bibkey: 0 for bibkey in bibkeys}
        for content_section in survey.content.root.all_section:
            def replace_bibkey(match):
                bibkey_str = match.group(1)
                bibkey_list = str2list(bibkey_str)
                indices = []
                for bibkey in bibkey_list:
                    bibkey = bibkey.strip().replace("-", "_")
                    try:
                        bibkey_count_dict[bibkey] += 1
                        indices.append(bibkeys.index(bibkey) + 1)
                    except Exception as e:
                        pass
                indices = list(set(indices))
                indices = sorted(indices)
                indices = [str(index) for index in indices]
                if indices:
                    return f"[{','.join(indices)}]"
                else:
                    return ""

            content_section.content = remove_illegal_bibkeys(content_section.content, legal_bibkeys=bibkeys)
            content_section.content = cite_reg.sub(
                replace_bibkey, content_section.content
            )

        # 统计没有被引用的论文比例
        not_cited_count = sum(1 for count in bibkey_count_dict.values() if count == 0)
        survey.cite_ratio = 1 - not_cited_count / len(bibkey_count_dict)

        ref_sec = "## References\n"
        for i, paper in enumerate(survey.papers.values()):
            print(str(paper))
            ref_sec += f"[{i+1}] {paper['title']} {paper.get('url', '')}\n\n"
        survey.ref_str = ref_sec

        return survey

    def save_survey(self, survey):
        os.makedirs(os.path.dirname(self.output_file), exist_ok=True)
        with FileObject(self.output_file, "a") as survey_file:
            survey_file.write(json.dumps(survey.to_dict(), ensure_ascii=False))
            survey_file.write("\n")
            logger.info(f"Survey {survey.title} saved.")
