import os
import numpy as np
import re
from tqdm import tqdm
import threading
import logging
from evaluation.API.model import APIModel
from concurrent.futures import ThreadPoolExecutor, as_completed
from .prompt import CRITERIA, CRITERIA_BASED_JUDGING_PROMPT, NLI_PROMPT, OUTLINE_EVALUATION_PROMPT, LANGUAGE_EVALUATION_PROMPT, CRITICAL_EVALUATION_PROMPT

logger = logging.getLogger(__name__)

class Judge():
    def __init__(self, jsonl_file: str, model: str, infer_type) -> None:
        self.model = model
        self.api_model = APIModel(self.model, infer_type)
        self.jsonl_file = jsonl_file
        self.input_token_usage, self.output_token_usage = 0, 0

    def __generate_prompt(self, template, paras):
        prompt = template
        for k in paras.keys():
            prompt = prompt.replace(f"[{k}]", paras[k])
        return prompt

    def criteria_based_judging(self, survey, topic, criterion):
        criterion_paras = CRITERIA[criterion]

        content_paras = {
            "TOPIC": topic,
            "SURVEY": survey,
            "Criterion Description": criterion_paras["description"],
            "Score 1 Description": criterion_paras["score 1"],
            "Score 2 Description": criterion_paras["score 2"],
            "Score 3 Description": criterion_paras["score 3"],
            "Score 4 Description": criterion_paras["score 4"],
            "Score 5 Description": criterion_paras["score 5"],
        }
        prompt = self.__generate_prompt(CRITERIA_BASED_JUDGING_PROMPT, content_paras)
        scores = self.api_model.chat(prompt, temperature=0)
        return scores

    def __criteria_based_judging(self, topic, survey, criterion, res_l, idx):
        criterion_paras = CRITERIA[criterion]
        content_paras = {
            "TOPIC": topic,
            "SURVEY": survey,
            "Criterion Description": criterion_paras["description"],
        }
        for score in range(1, 6):
            content_paras[f"Score {score} Description"] = criterion_paras[
                f"score {score}"
            ]
        prompt = self.__generate_prompt(CRITERIA_BASED_JUDGING_PROMPT, content_paras)
        scores = self.api_model.chat(prompt, temperature=0)
        res_l[idx] = self.extract_num(scores)
        return scores

    def extract_num(self, string):
        numbers = re.findall(r"\d+", string)
        if len(numbers) == 0:
            return ""
        return eval(numbers[0])

    def extract_num_addition(self, response: str) -> float:
        match = re.search(r'<SCORE>\s*(\d+(\.\d+)?)\s*</SCORE>', response)
        if match:
            score = float(match.group(1)) 
            if 0 <= score <= 100:
                return float(score)
            else:
                logger.error(f"Invalid score extracted from response: {score}")
                return 0.0 
        else:
            logger.error(f"Failed to extract outline score from response: {response}")
            return 0.0  
        
    def batch_criteria_based_judging(self, survey, topic, criteria):
        thread_l = []
        scores = [0] * len(criteria)
        for i in range(len(criteria)):
            thread = threading.Thread(
                target=self.__criteria_based_judging,
                args=(topic, survey, criteria[i], scores, i),
            )
            thread_l.append(thread)
            thread.start()
        for thread in thread_l:
            thread.join()
        return scores


    def __get_pair_score(self, source, claim, res_l, i, j, citation_idx, raw_claim=''):
        max_model_len = 900000 
        max_estimate_char_len = int(max_model_len * 1.25)
        if len(source) > max_estimate_char_len:
            logger.warning(f"Source is too long({len(source)}), truncated to {max_estimate_char_len} characters")
            source = source[:max_estimate_char_len]
        source = source[:max_estimate_char_len]
        content_paras = {'SOURCE': source, 'CLAIM': claim}
        prompt = self.__generate_prompt(NLI_PROMPT, content_paras)
        try:
            res = self.api_model.chat(prompt, temperature=0)
        except Exception as e:
            logger.error(f"Error occurred while calling chat API: {e}") 
            res_l[i][j] = -1
            return 0
        
        res = self.api_model.chat(prompt, temperature=0)

        if res and "yes" in res.lower():
            res_l[i][j] = citation_idx
            return 1
        else:
            res_l[i][j] = -1
            if raw_claim:
                logger.info(f"Unrelated pair found. \n  claim=[{claim}]\n  raw_claim=[{raw_claim}]\n  citation_idx={citation_idx}\n  source[:1500]={source[:1500]}")
            else:
                logger.info(f"Unrelated pair found. Claim=[{claim}], Source[:1500]={source[:1500]}")
            return 0

    def citation_quality_new(self, survey_with_reference, references):
        survey = survey_with_reference.split("## References")[0]
        survey_sections = survey.split("###")
        citation_pattern = re.compile(r"[^.!?]*\[[^\]]+\][^.!?]*[.!?]")
        sentences = []
        for content in survey_sections:
            sentences += citation_pattern.findall(content)
        raw_claims = []
        claims = []
        sources_ids = []
        for s in sentences:
            sources = re.findall(pattern=r"\[(.*?)\]", string=s)
            if len(sources) > 0:
                source_ids = set()
                for ref in sources:
                    for num in ref.split(","):
                        number = self.extract_num(num)
                        if number != "":
                            source_ids.add(number)
                if len(source_ids) > 0:
                    raw_claims.append(s)
                    claims.append(re.sub(pattern=r'\[(.*?)\]', repl='', string=s))
                    sources_ids.append(list(source_ids))

        paper_infos = self.get_paper_info_from_jsonl(references)

        ids_to_title = {p["title"]: p["title"] for p in paper_infos}
        ids_to_paper = {p["title"]: p["content"] for p in paper_infos}

        index_to_paper = {
            index: ids_to_paper[title] for index, title in enumerate(ids_to_title)
        }
        index_to_titles = {index: title for index, title in enumerate(ids_to_title)}

        logger.info(f"start to eval pair score..")
        thread_l = []
        assert len(claims) == len(sources_ids)
        pair_scores = []
        for i in range(len(claims)):
            pair_scores.append([0] * len(sources_ids[i]))

        
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = []
            for i in range(len(claims)):
                for j in range(len(sources_ids[i])):
                    citation_idx = sources_ids[i][j] - 1
                    source = index_to_paper[citation_idx]
                    futures.append(executor.submit(self.__get_pair_score, source, claims[i], pair_scores, i, j, citation_idx, raw_claims[i]))

            for future in tqdm(as_completed(futures), total=len(futures), desc="Processing threads"):
                future.result()
                

        total_paper_num = len(paper_infos)
        result_dict = {}
        correct_claim_num, total_claim_num = claim_precision(pair_scores)
        result_dict["claim_precision"] = correct_claim_num / total_claim_num
        correct_citation_num, total_citation_num = citation_precision(pair_scores)
        result_dict["citation_precision"] = correct_citation_num / total_citation_num
        result_dict["reference_precision"] = reference_precision(
            pair_scores, total_paper_num
        )
        result_dict["reference_coverage"] = reference_coverage(
            claims, sources_ids, total_paper_num
        )
        result_dict["citation_density"] = citation_density(sources_ids, survey)
        result_dict["avg_citation_per_claim"] = avg_citation_per_claim(
            claims, sources_ids
        )
        print_result(result_dict)

        return result_dict
    
    def citation_quality_num(self, survey_with_reference, references):
        survey = survey_with_reference.split('## References')[0]
        survey_sections = survey.split('###')
        citation_pattern = re.compile(r'[^.!?]*\[[^\]]+\][^.!?]*[.!?]')
        sentences = []
        for content in survey_sections:
            sentences += citation_pattern.findall(content)
        raw_claims=[]
        claims = []
        sources_ids = []
        for s in sentences:
            sources = re.findall(pattern=r'\[(.*?)\]', string=s)
            if len(sources) > 0:
                source_ids = set()
                for ref in sources:
                    for num in ref.split(','):
                        number = self.extract_num(num)
                        if number != '':
                            source_ids.add(number)
                if len(source_ids) > 0:
                    raw_claims.append(s)
                    claims.append(re.sub(pattern=r'\[(.*?)\]', repl='', string=s))
                    sources_ids.append(list(source_ids))

        paper_infos = self.get_paper_info_from_jsonl(references)

        ids_to_title = {p['title']: p['title'] for p in paper_infos}
        ids_to_paper = {p['title']: p['content'] for p in paper_infos}

        index_to_paper = {index: ids_to_paper[title] for index, title in enumerate(ids_to_title)}
        index_to_titles = {index: title for index, title in enumerate(ids_to_title)}

        logger.info(f"start to eval pair score by paper..")
        assert len(claims) == len(sources_ids)
        pair_scores = []
        for i in range(len(claims)):
            pair_scores.append([0] * len(sources_ids[i]))

        thread_l = []
        for i in range(len(claims)):
            for j in range(len(sources_ids[i])):
                citation_idx = sources_ids[i][j] - 1
                source = index_to_paper[citation_idx]
                thread = threading.Thread(target=self.__get_pair_score, args=(source, claims[i], pair_scores, i, j, citation_idx, raw_claims[i]))
                thread_l.append(thread)
                thread.start()
        for thread in tqdm(thread_l):
            thread.join()


        total_paper_num = len(paper_infos)
        result_dict = {}
        correct_claim_num , total_claim_num= claim_precision(pair_scores)
        correct_citation_num, total_citation_num = citation_precision(pair_scores)
        result_dict["correct_claim_num"] = correct_claim_num
        result_dict["total_claim_num"] = total_claim_num
        result_dict["correct_citation_num"] = correct_citation_num
        result_dict["total_citation_num"] = total_citation_num

        return result_dict
        

    def get_paper_info_from_jsonl(self, references):
        paper_infos = []
        for paper in references:
            paper_info = {
                "title": paper.get("title", ""),
                "content": (paper.get("txt") or ""),
            }
            paper_infos.append(paper_info)
        return paper_infos
    
    def evaluate_outline(self, outline: str, topic: str) -> float:
        content_paras = {
            'TOPIC': topic,
            'OUTLINE': outline
        }
        prompt = self.__generate_prompt(OUTLINE_EVALUATION_PROMPT, content_paras)
        response = self.api_model.chat(prompt, temperature=0)
        logger.debug(response)
        score = self._extract_outline_score(response)
        return score

    def _extract_outline_score(self, response: str) -> float:
        match = re.search(r'<SCORE>\s*(\d+(\.\d+)?)\s*</SCORE>', response)
        if match:
            score = float(match.group(1))
            if 0 <= score <= 100:
                return score
            else:
                logger.error(f"Invalid score extracted from response: {score}")
                return 0.0
        else:
            logger.error(f"Failed to extract outline score from response: {response}")
            return 0.0

    def evaluate_section(self, section, topic, prompt_template):
        content_paras = {'TOPIC': topic, 'SECTION': section}
        prompt = self.__generate_prompt(prompt_template, content_paras)
        
        response = self.api_model.chat(prompt, temperature=0)
        
        logger.info(response)
        score = self.extract_num_addition(response)
        return score

    def evaluate_survey_dimension(self, survey, topic, dimension_prompt_template):
        sections = re.findall(
            r'(^## \d+(?:\.\s|\s|$).*?)(?=^## \d+(?:\.\s|\s|$)|^## References|\Z)', 
            survey,
            flags=re.DOTALL | re.MULTILINE
        )
        
        section_scores = []
        thread_l = []
        
        score_results = [None] * len(sections)

        def evaluate_section_thread(i, section):
            score = self.evaluate_section(section.strip(), topic, dimension_prompt_template)
            score_results[i] = score 

        for i, section in enumerate(sections):
            if i == 0 and not section.startswith("##"):
                continue
            
            thread = threading.Thread(target=evaluate_section_thread, args=(i, section))
            thread_l.append(thread)
            thread.start()
        
        for thread in thread_l:
            thread.join()

        section_scores = [score for score in score_results if score is not None]

        if section_scores:
            print(section_scores, flush=True)

            filtered_scores = [score for score in section_scores if score != 0]
            avg_score = np.mean(filtered_scores) if filtered_scores else 0.0
            print(avg_score, flush=True)

        else:
            avg_score = 0.0

        return avg_score

    
    def evaluate_language(self, survey, topic):
        return self.evaluate_survey_dimension(survey, topic, LANGUAGE_EVALUATION_PROMPT)

    def evaluate_critical(self, survey, topic):
        return self.evaluate_survey_dimension(survey, topic, CRITICAL_EVALUATION_PROMPT)

    def evaluate_all_dimensions(self, survey, topic):
        language_score = self.evaluate_language(survey, topic)
        critical_score = self.evaluate_critical(survey, topic)

        return {
            'language_score': language_score,
            'critical_score': critical_score,
        }

        
def claim_precision(pairs):
    total_claim_num = len(pairs)
    correct_claim_num = 0
    for i in range(total_claim_num):
        for j in range(len(pairs[i])):
            if not pairs[i][j] == -1:
                correct_claim_num += 1
                break
    return correct_claim_num, total_claim_num


def citation_precision(pairs):
    total_citation_num = 0
    correct_citation_num = 0
    for i in range(len(pairs)):
        for j in range(len(pairs[i])):
            total_citation_num += 1
            if not pairs[i][j] == -1:
                correct_citation_num += 1
    return correct_citation_num, total_citation_num


def reference_precision(pairs, total_paper_num):
    reference_set = set()
    for i in range(len(pairs)):
        for j in range(len(pairs[i])):
            if not pairs[i][j] == -1:
                reference_set.add(pairs[i][j])
    return len(reference_set) / total_paper_num


def reference_coverage(claims, sources_ids, total_paper_num):
    reference_set = set()
    for i in range(len(claims)):
        for j in range(len(sources_ids[i])):
            citation_idx = sources_ids[i][j] - 1
            reference_set.add(citation_idx)
    return len(reference_set) / total_paper_num


def count_sentences(text):
    sentences = re.split(r"[.!?\n]+(?:\s|\n|$)", text.strip())
    sentences = [s for s in sentences if s]
    return len(sentences)


def citation_density(sources_ids, survey):
    total_citation_num = 0
    for i in range(len(sources_ids)):
        for _ in range(len(sources_ids[i])):
            total_citation_num += 1

    total_sentence_num = count_sentences(survey)
    return total_citation_num / total_sentence_num


def avg_citation_per_claim(claims, sources_ids):
    total_citation_num = 0
    for i in range(len(claims)):
        for _ in range(len(sources_ids[i])):
            total_citation_num += 1
    return total_citation_num / len(claims)


def print_result(result_dict):
    print("########## Metric with Judgement ##########")
    print(f"Claim Precision: {result_dict['claim_precision']}")
    print(f"Citation Precision: {result_dict['citation_precision']}")
    print(f"Reference Precision: {result_dict['reference_precision']}")
    print(f"######## Metric without Judgement #########")
    print(f"Reference Coverage: {result_dict['reference_coverage']}")
    print(f"Citation Density: {result_dict['citation_density']}")
    print(f"Avg Citation per Claim: {result_dict['avg_citation_per_claim']}")
    print(f"Citation Quality: {result_dict['reference_precision'] * result_dict['reference_precision']}")