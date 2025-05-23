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

# 导入数据库管理器
try:
    from src.database import mongo_manager
    DATABASE_AVAILABLE = True
except ImportError as e:
    logger.warning(f"数据库模块不可用，将仅使用文件存储: {str(e)}")
    DATABASE_AVAILABLE = False

logger = logging.getLogger(__name__)


class DecodePipeline(Sequential):
    def __init__(self, config, output_file=None, worker_num=10, use_database=True):
        worker_num = worker_num * 10
        self.config = config
        self.output_file = output_file
        self.use_database = use_database and DATABASE_AVAILABLE
        
        # 如果使用文件存储，确保输出文件路径正确
        if self.output_file and not os.path.dirname(self.output_file):
            self.output_file = os.path.join(os.getcwd(), os.path.basename(self.output_file))
        
        self.dict_semaphore = Semaphore(1)
        self.executing_survey = {}  # title: survey

        # 如果启用数据库，尝试连接
        if self.use_database:
            try:
                if mongo_manager.connect():
                    logger.info("DecodePipeline: 数据库连接成功，将使用数据库存储")
                else:
                    logger.warning("DecodePipeline: 数据库连接失败，回退到文件存储")
                    self.use_database = False
            except Exception as e:
                logger.warning(f"DecodePipeline: 数据库初始化失败，回退到文件存储: {str(e)}")
                self.use_database = False

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
        self.cite_node = Node(
            self.change_bibkey_to_index, worker_num=worker_num, queue_size=worker_num
        )
        self.chart_module = FigureModule(self.config)
        self.chart_node = Node(
            self.chart_module, worker_num=worker_num, queue_size=worker_num
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

            content_section.content = remove_illegal_bibkeys(
                content_section.content, legal_bibkeys=bibkeys
            )
            content_section.content = cite_reg.sub(
                replace_bibkey, content_section.content
            )

        # 统计没有被引用的论文比例
        not_cited_count = sum(1 for count in bibkey_count_dict.values() if count == 0)
        survey.cite_ratio = 1 - not_cited_count / len(bibkey_count_dict)

        ref_sec = "## References\n"
        for i, paper in enumerate(survey.papers.values()):
            ref_sec += f"[{i+1}] {paper['title']} {paper.get('url', '')}\n\n"
        survey.ref_str = ref_sec

        return survey

    def save_survey(self, survey):
        """保存survey，优先使用数据库，文件存储作为备选方案"""
        survey_data = survey.to_dict()
        saved_to_database = False
        
        # 尝试保存到数据库
        if self.use_database and survey.task_id:
            try:
                if mongo_manager.save_survey(survey.task_id, survey_data):
                    logger.info(f"Survey保存到数据库成功: task_id={survey.task_id}, title={survey.title}")
                    saved_to_database = True
                else:
                    logger.warning(f"Survey保存到数据库失败: task_id={survey.task_id}, title={survey.title}")
            except Exception as e:
                logger.error(f"数据库保存异常: task_id={survey.task_id}, error={str(e)}")
        
        # 如果数据库保存失败或未启用数据库，使用文件存储
        if not saved_to_database and self.output_file:
            try:
                os.makedirs(os.path.dirname(self.output_file), exist_ok=True)
                with FileObject(self.output_file, "a") as survey_file:
                    survey_file.write(json.dumps(survey_data, ensure_ascii=False))
                    survey_file.write("\n")
                    logger.info(f"Survey保存到文件成功: file={self.output_file}, title={survey.title}")
            except Exception as e:
                logger.error(f"文件保存失败: file={self.output_file}, title={survey.title}, error={str(e)}")
        
        # 如果两种方式都失败，记录警告
        if not saved_to_database and not self.output_file:
            logger.warning(f"Survey未能保存（数据库和文件都不可用）: title={survey.title}")

    def set_output_file(self, output_file):
        """设置输出文件路径（向后兼容）"""
        self.output_file = output_file
        if output_file and not os.path.dirname(output_file):
            self.output_file = os.path.join(os.getcwd(), os.path.basename(output_file))
        logger.info(f"输出文件路径已设置: {self.output_file}")
