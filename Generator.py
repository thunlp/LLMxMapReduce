from calendar import c
import copy
from pyexpat import model
from typing import List, Optional, Tuple, Any
import json
from unittest import result
from openai import OpenAI
import tiktoken
from vllm import SamplingParams
from transformers import AutoTokenizer

import os
import re
import random
from tenacity import (
    retry,
    stop_after_attempt,
    wait_random_exponential, stop_after_delay,
)
from utils import get_openai_batch_reply, print_intermediate_output,  run_thread_pool_sub, split_list_of_docs, thread_function


class Generator:
    def __init__(
        self,
        config: dict, 
        tokenizer=None,
        print_intermediate_path=None,
        doc_id=None
    ):


        self.first_prompt = config['map_prompt']
        self.gen_args = config.get('gen_args', {})
        
        self.config = config
        self.max_work_count = config.get('max_work_count', 4)
        
        self.use_openai_api = config.get('use_openai_api', False)
        if self.use_openai_api:
            self.openai_key = config.get('openai_api', {}).get('api_key', None)
            self.openai_base_url = config.get('openai_api', {}).get(
                'base_url', 'https://api.openai.com/v1')
            self.openai_client = OpenAI(
                api_key=self.openai_key, base_url=self.openai_base_url) # OpenAI API client
            self.openai_model = config.get('openai_api', {}).get('model', 'text-davinci-003')
            self.is_vllm_sever = config.get('openai_api', {}).get('is_vllm_sever', False)
            if self.is_vllm_sever:
                self.tokenizer = AutoTokenizer.from_pretrained(
                    config['openai_api']['name_or_path'])
            else:
                self.tokenizer = tiktoken.encoding_for_model(self.openai_model)
        else:
            
            self.url = config.get('llm', {}).get('url', 'http://localhost:5002/infer')
            self.tokenizer = AutoTokenizer.from_pretrained(
            config['llm']['name_or_path'])
        
        self.print_intermediate_path = print_intermediate_path
        self.doc_id = doc_id
        


    def build_message(self, prompt, input_dict):

        message = [{'role': 'user', 'content': prompt.format(**input_dict)}]
        message_str = self.tokenizer.apply_chat_template(
            conversation=message, tokenize=False, add_generation_prompt=True)
        return message_str

    def split_list_to_chunks(self, lst: list, chunk_num):
        '''Divide the list into chunk_num parts'''
        length = len(lst)
        if len(lst) <= chunk_num:
            return lst

        chunk_size = length // chunk_num
        result = [lst[i * chunk_size:(i + 1) * chunk_size]
                  for i in range(chunk_num - 1)]
        # The last block contains all the remaining elements
        result.append(lst[(chunk_num - 1) * chunk_size:])
        assert len(result) == chunk_num
        assert sum([len(i) for i in result]) == length
        return result

    def mr_map(self, context: list[str], question) -> list[str]:
        prompt = self.config['map_prompt']
        print("=====Map=====")

        batch = []
        intermediate_input = []
        for i, item in enumerate(context):
            if self.use_openai_api:
                messages = [{'role': 'user', 'content':prompt.format_map(
                {"question": question, "context": item}) }]
            else:
                messages = self.build_message(
                    prompt, {"question": question, "context": item})

            intermediate_input.append(prompt.format_map(
                {"question": question, "context": item}))

            batch.append(messages)
        if self.use_openai_api:
            para = copy.deepcopy(self.gen_args)
            para['model'] = self.openai_model
            res = get_openai_batch_reply(
                batch, self.max_work_count, self.openai_client, para)
        else:
            res = self.get_batch_reply(batch)
        print('map result:')
        print(res)
        if self.print_intermediate_path != None:
            print_intermediate_output(
                self.print_intermediate_path, intermediate_input, res, 'map', doc_id=self.doc_id)
        return res

    def get_batch_reply(self, batch):
        chunk_req = self.split_list_to_chunks(batch, self.max_work_count)

        result_map = {}
        res = []
        for i, result_list in run_thread_pool_sub(
            thread_function, self.url, chunk_req, self.gen_args, min(
                len(batch), self.max_work_count)
        ):
            if i not in result_map:
                result_map[i] = []
            result_map[i].extend(result_list)
        for i in range(len(chunk_req)):
            res.extend(result_map[i])
        return res

    def split_sentences(self, text, spliter):
        # Split by punctuation and keep punctuation
        text = text.strip()
        sentence_list = re.split(spliter, text)

        # Rearrange sentences and punctuation
        if spliter != ' ':
            sentences = ["".join(i) for i in zip(
                sentence_list[0::2], sentence_list[1::2])]
            if len(sentence_list) % 2 != 0 and sentence_list[-1] != '':
                sentences.append(sentence_list[-1])
        else:
            sentences = [i+' ' for i in sentence_list if i != '']
            sentences[-1] = sentences[-1].strip()
        return sentences

    def split_into_chunks(self, text, chunk_size, spliter=r'([。！？；.?!;])'):
        # Split by punctuation and keep punctuation
        # Rearrange sentences and punctuation
        sentences = self.split_sentences(text, spliter)

        chunks = []
        current_chunk = ""

        for s_idx, sentence in enumerate(sentences):
            sentence_length = self.get_prompt_length(sentence)

            if self.get_prompt_length(current_chunk) + sentence_length <= chunk_size:
                current_chunk += sentence
            else:
                if current_chunk:
                    if self.get_prompt_length(current_chunk) <= chunk_size:
                        chunks.append(current_chunk)
                    else:
                        if spliter != ' ':  # Avoid infinite loops
                            chunks.extend(self.split_into_chunks(
                                current_chunk, chunk_size=chunk_size, spliter=' '))
                current_chunk = sentence

        if current_chunk != '':
            if self.get_prompt_length(current_chunk) <= chunk_size:
                chunks.append(current_chunk)
            else:
                if spliter != ' ':  # Avoid infinite loops
                    chunks.extend(self.split_into_chunks(
                        current_chunk, chunk_size=chunk_size, spliter=' '))
        # Re-segment the last two blocks
        
        if len(chunks) > 1 and self.get_prompt_length(chunks[-1]) < chunk_size//2:
            last_chunk = chunks.pop()
            penultimate_chunk = chunks.pop()
            combined_text = penultimate_chunk + last_chunk

            new_sentences = self.split_sentences(combined_text, spliter)

            # Reallocate sentence using double pointer
            new_penultimate_chunk = ""
            new_last_chunk = ""
            i, j = 0, len(new_sentences) - 1

            while i <= j and len(new_sentences) != 1:
                flag = False
                if self.get_prompt_length(new_penultimate_chunk + new_sentences[i]) <= chunk_size:
                    flag = True
                    new_penultimate_chunk += new_sentences[i]
                    if i == j:
                        break  
                    i += 1
                if self.get_prompt_length(new_last_chunk + new_sentences[j]) <= chunk_size:
                    new_last_chunk = new_sentences[j] + new_last_chunk
                    j -= 1
                    flag = True
                if flag == False:
                    break
            if i < j:
                # If there is any unallocated part, split it by punctuation or space and then allocate it
                remaining_sentences = new_sentences[i:j+1]
                if remaining_sentences:
                    remaining_text = "".join(remaining_sentences)
                    words = remaining_text.split(' ')
                    end_index = len(words)-1
                    for index, w in enumerate(words):
                        if self.get_prompt_length(' '.join([new_penultimate_chunk, w])) <= chunk_size:
                            new_penultimate_chunk = ' '.join(
                                [new_penultimate_chunk, w])
                        else:
                            end_index = index
                            break
                    if end_index != len(words)-1:
                        new_last_chunk = ' '.join(
                            words[end_index:]) + ' ' + new_last_chunk
            if len(new_sentences) == 1:
                chunks.append(penultimate_chunk)
                chunks.append(last_chunk)
            else:
                chunks.append(new_penultimate_chunk)
                chunks.append(new_last_chunk)

        return chunks

    def chunk_docs(self, doc: str, chunk_size: int, separator='\n', chunk_overlap=0, question=None) -> list[str]:

        chunk_size = chunk_size - \
            self.get_prompt_length(self.first_prompt) - \
            self.gen_args.get('max_tokens', 300)
        if question != None:
            chunk_size = chunk_size - self.get_prompt_length(question)
        splits = doc.split(separator)
        splits = [s for s in splits if s != '']
        separator_len = self.get_prompt_length_no_special(separator)

        docs = []
        current_doc: List[str] = []
        total = 0
        for d in splits:
            _len = self.get_prompt_length_no_special(d)
            if (
                total + _len + (separator_len if len(current_doc) > 0 else 0)
                > chunk_size
            ):
                if total > chunk_size:
                    print(
                        f"Created a chunk of size {total}, "
                        f"which is longer than the specified {chunk_size}"
                    )
                    

                    if len(current_doc) == 1:  # if one chunk is too long

                        split_again = self.split_into_chunks(
                            current_doc[0], chunk_size)
                        docs.extend(split_again)
                        current_doc = []
                        total = 0

                if len(current_doc) > 0:
                    doc = separator.join(current_doc)
                    if doc is not None:
                        docs.append(doc)
                    # Keep on popping if:
                    # - we have a larger chunk than in the chunk overlap
                    # - or if we still have any chunks and the length is long
                    while total > chunk_overlap or (
                        total + _len +
                            (separator_len if len(current_doc) > 0 else 0)
                        > chunk_size
                        and total > 0
                    ):
                        total -= self.get_prompt_length_no_special(current_doc[0]) + (
                            separator_len if len(current_doc) > 1 else 0
                        )
                        current_doc = current_doc[1:]

            current_doc.append(d)
            total += _len + (separator_len if len(current_doc) > 1 else 0)
        # Check if the last one exceeds
        if self.get_prompt_length_no_special(current_doc[-1]) > chunk_size and len(current_doc) == 1:
            split_again = self.split_into_chunks(current_doc[0], chunk_size)
            docs.extend(split_again)
            current_doc = []
        else:
            doc = separator.join(current_doc)
            if doc is not None:
                docs.append(doc)
        docs = [d for d in docs if d.strip() != ""]
        return docs

    def get_prompt_length(self, prompt, **kwargs: Any) -> int:
        if isinstance(prompt, list):
            prompt = self.join_docs(prompt)
        return len(self.tokenizer.encode(prompt, **kwargs))

    def get_prompt_length_format(self, prompt, **kwargs: Any) -> int:
        # Calculate the length after formatting
        if isinstance(prompt, list):
            prompt = ''.join(self.format_chunk_information(prompt))
        return len(self.tokenizer.encode(prompt, **kwargs))

    def get_prompt_length_no_special(self, prompt, **kwargs: Any) -> int:
        if isinstance(prompt, list):
            prompt = self.join_docs(prompt)
        if not isinstance(self.tokenizer, tiktoken.core.Encoding):
            return len(self.tokenizer.encode(prompt, add_special_tokens=False, **kwargs))
        else:
            return len(self.tokenizer.encode(prompt, disallowed_special='all', ** kwargs))

    def join_docs(self, docs: list[str]) -> str:
        if isinstance(docs, str):
            return docs
        return '\n\n'.join(docs)

    def format_chunk_information(self, docs):
        if self.config.get('zh_chunk', False) == False:
        # format chunk
            new_docs = [
                f'Information of Chunk {index}:\n{d}\n' for index, d in enumerate(docs)]
            return new_docs
        else:
            new_docs = [
                f'第{index}号块的信息:\n{d}\n' for index, d in enumerate(docs)]
            return new_docs

    def mr_collapse(
        self,
        docs: list[str],
        question: str,
        token_max: Optional[int] = None,
        max_retries: Optional[int] = None,
    ) -> list[str]:
        result_docs = docs

        prompt = self.config['collapse_prompt']
        num_tokens = self.get_prompt_length_format(result_docs)
        prompt_len = self.get_prompt_length(prompt)
        _token_max = token_max - prompt_len - \
            self.gen_args.get('max_tokens', 300)  # or self.chunk_size
        retries: int = 0
        while num_tokens is not None and num_tokens > _token_max:
            new_result_doc_list = split_list_of_docs(
                result_docs, self.get_prompt_length_format, _token_max,
            )
            result_docs = []
            current_batch = []
            intermediate_input = []
            for index, docs in enumerate(new_result_doc_list):
                # new_doc = collapse_chain.invoke(
                #     {"context": self.join_docs(docs), "question": question})
                if self.use_openai_api:
                    messages = [{'role': 'user', 'content': prompt.format_map(
                        {"question": question, "context": self.join_docs(docs)})}]
                else:
                    messages = self.build_message(
                        prompt, {"context": self.join_docs(docs), "question": question})
                current_batch.append(messages)
                #!--------
                intermediate_input.append(prompt.format_map(
                    {"question": question, "context": self.join_docs(docs)}))
                #!--------
            if self.use_openai_api:
                para = copy.deepcopy(self.gen_args)
                para['model'] = self.openai_model
                result_docs = get_openai_batch_reply(
                    current_batch, self.max_work_count, self.openai_client, para)
            else:
                result_docs = self.get_batch_reply(current_batch)
            #!--------
            if self.print_intermediate_path != None:
                print_intermediate_output(
                    self.print_intermediate_path, intermediate_input, result_docs, 'collapse', doc_id=self.doc_id)
            #!---------
            num_tokens = self.get_prompt_length_format(result_docs)
            retries += 1
            if max_retries and retries == max_retries:
                raise ValueError(
                    f"Exceed {max_retries} tries to \
                        collapse document to {_token_max} tokens."
                )
        print("=====Collapse=====")
        print(result_docs)
        return result_docs

    def mr_reduce(self, context: list[str], question):
        # Reduce
        prompt = self.config['reduce_prompt']
        context = ''.join(self.format_chunk_information(context))
        print("=====Reduce=====")

        if self.use_openai_api:
            messages = [{'role': 'user', 'content': prompt.format_map({"context": context, "question": question})}]
            para = copy.deepcopy(self.gen_args)
            para['model'] = self.openai_model
            result = get_openai_batch_reply(
                [messages], self.max_work_count, self.openai_client, para)
        else:
            messages = self.build_message(
                prompt, {"context": context, "question": question})
            result = self.get_batch_reply([messages])
        result = result[0]
        print("input")
        print({"context": context, "question": question})
        print('output')
        print(result)
        if self.print_intermediate_path != None:
            print_intermediate_output(
                self.print_intermediate_path, prompt.format_map({"context": context, "question": question}), result, 'reduce', doc_id=self.doc_id)
        return result


