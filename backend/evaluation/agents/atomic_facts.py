import json
import re
import string
import nltk
import openai
import random
from tqdm import tqdm
import os
import csv
from nltk.tokenize import sent_tokenize
from evaluation.API.model import APIModel
from concurrent.futures import ThreadPoolExecutor, as_completed
from queue import Queue
from .prompt import get_extraction_prompt, get_deduplication_prompt



def clean_claims(claims):
    """
    Clean up claims like 'Claim 1: ' and similar patterns from the start of each claim.
    """
    cleaned_claims = []
    for claim in claims:
        cleaned_claim = re.sub(r'^Claim \d+: ', '', claim)  # Remove 'Claim N: ' at the start
        cleaned_claims.append(cleaned_claim)
    return cleaned_claims

class AtomicFactGenerator(object):
    def __init__(self, demon_dir):
        self.is_bio = True
        self.model = "gemini-2.0-flash-thinking-exp-1219"
        self.infer_type = "OpenAI"
        self.api_model = APIModel(self.model, self.infer_type)
        self.group_size =300

    def _deduplicate_group(self, facts_list: list) -> list:
        if not facts_list:
            return facts_list

        prompt = get_deduplication_prompt(facts_list)
        temperature = 0.0  # Initial temperature
        output = self.send_request(prompt, temperature)
        try:
            indices_to_remove = set(
                int(idx.strip()) - 1
                for idx in output.split(',')
                if idx.strip().isdigit()
            )
            deduped = [
                fact for i, fact in enumerate(facts_list)
                if i not in indices_to_remove
            ]
            return deduped
        except ValueError:
            print("Error parsing indices from output:", output)
            return facts_list

        

    def deduplicate_atomic_facts(self, atomic_facts):
        """
        1) Split into smaller groups.
        2) Perform deduplication on each group.
        3) Cross-group deduplication: Pairwise deduplication between groups.
        4) Merge the groups, removing duplicates from each step.
        """
        
        def get_merged_group(group_i, group_j):
            combined = group_i + group_j
            random.shuffle(combined)
            prompt = get_deduplication_prompt(combined)
            output = self.send_request(prompt, temperature, retries=1)
            remove_set = set(
                int(idx.strip()) - 1
                for idx in output.split(',')
                if idx.strip().isdigit()
            )

            # Separate the removal indices into the correct groups
            len_i = len(group_i)
            new_group_i = [fact for idx, fact in enumerate(group_i) if idx not in remove_set]
            new_group_j = [fact for idx, fact in enumerate(group_j) if (idx + len_i) not in remove_set]
            return new_group_i + new_group_j
    
        if not atomic_facts:
            return []

        group_size = self.group_size
        grouped_facts = [
            atomic_facts[i:i + group_size]
            for i in range(0, len(atomic_facts), group_size)
        ]

        print(f"Grouped {len(atomic_facts)} facts into {len(grouped_facts)} groups")
        deduplicated_groups = Queue()
        with ThreadPoolExecutor() as executor:
            futures = []
            for group in grouped_facts:
                futures.append(executor.submit(self._deduplicate_group, group))
                
            for future in tqdm(as_completed(futures), total=len(futures), desc="Deduplicating each group"):
                deduplicated_groups.put(future.result())
                
        print(f"Finished deduplicating {len(grouped_facts)} groups, start cross-group deduplication")

        # Deduplicate groups in pairs and remove duplicates after each pairwise comparison
        temperature = 0.0  # Initial temperature
        futures = {}
        with ThreadPoolExecutor() as executor:
            while len(futures) > 0 or deduplicated_groups.qsize() > 1:
                while deduplicated_groups.qsize() > 1:
                    group_i = deduplicated_groups.get_nowait()  
                    group_j = deduplicated_groups.get_nowait()
                    
                    if group_i is None or group_j is None:
                        if group_i is not None:
                            deduplicated_groups.put(group_i)
                        if group_j is not None:
                            deduplicated_groups.put(group_j)
                        continue 
                    
                    futures[executor.submit(get_merged_group, group_i, group_j)] = (group_i, group_j)
                
                done_futures = []
                for future in futures.keys():
                    if future.done():
                        done_futures.append(future)
                        try:
                            result = future.result()
                            deduplicated_groups.put(result)
                        except Exception as e:
                            print(f"Error during cross-group deduplication: {e}")
                            group_i, group_j = futures[future]
                            deduplicated_groups.put(group_i)
                            deduplicated_groups.put(group_j)
                
                for future in done_futures:
                    del futures[future]
        print(f"Finished cross-group deduplication, finalizing results")

        assert deduplicated_groups.qsize() == 1, f"Expected 1 group, got {deduplicated_groups.qsize()}"
        final_facts = deduplicated_groups.get()
        return final_facts

    def get_atomic_facts(self, text, cost_estimate=None):
        """
        Directly process the entire text and generate a list of atomic facts
        """
        prompt = get_extraction_prompt(text)

        if cost_estimate:
            total_words_estimate = len(prompt.split())
            return total_words_estimate
        else:
            output = None
            temperature = 0.0  # Initial temperature
            try:
                output = self.send_request(prompt, temperature)
                return text_to_sentences(output)
            except Exception as e:
                return []
        
    def send_request(self, prompt, temperature=0.0, retries = 3):
        
        for _ in range(retries):
            try:
                response = self.api_model.chat(prompt, temperature=temperature)
                return response
            except ValueError as e:
                if "OpenAI API returned empty choices in response" in str(e):
                    print(f"ValueError occurred, retrying {_} times with increased temperature...")
                    temperature += 0.1
                else:
                    print(f"An error occurred: {e}. Retrying...")
            except Exception as e:
                print(f"Error during cross-group deduplication: {e}")
        raise Exception(f"Failed to generate atomic facts after {retries} retries.")

def text_to_sentences(text):
    """
    Use regular expressions to extract "1. xxx" type entries from the model's returned text
    and return a list of each entry.
    """
    sentences = re.findall(r'\d+\.\s*([^\n]+)', text)
    # If the last fact doesn't have a period, add one (optional)
    if len(sentences) > 0 and sentences[-1] and sentences[-1][-1] != '.':
        sentences[-1] = sentences[-1] + '.'
    return sentences


def normalize_answer(s):
    """Lower text and remove punctuation, articles and extra whitespace."""
    import re
    def remove_articles(text):
        regex = re.compile(r'\b(a|an|the)\b', re.UNICODE)
        return re.sub(regex, ' ', text)
    def white_space_fix(text):
        return ' '.join(text.split())
    def remove_punc(text):
        exclude = set(string.punctuation)
        return ''.join(ch for ch in text if ch not in exclude)
    def lower(text):
        return text.lower()
    return white_space_fix(remove_articles(remove_punc(lower(s))))


MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
MONTHS = [m.lower() for m in MONTHS]

def is_num(text):
    try:
        text = int(text)
        return True
    except Exception:
        return False

def is_date(text):
    text = normalize_answer(text)
    for token in text.split(" "):
        if (not is_num(token)) and token not in MONTHS:
            return False
    return True

def extract_numeric_values(text):
    pattern = r'\b\d+\b'  # regular expression pattern for integers
    numeric_values = re.findall(pattern, text)  # find all numeric values in the text
    return set([value for value in numeric_values])  # convert the values to float and return as a list


def detect_entities(text, nlp):
    doc = nlp(text)
    entities = set()

    def _add_to_entities(text):
        if "-" in text:
            for _text in text.split("-"):
                entities.add(_text.strip())
        else:
            entities.add(text)

    for ent in doc.ents:
        # spacy often has errors with other types of entities
        if ent.label_ in ["DATE", "TIME", "PERCENT", "MONEY", "QUANTITY", "ORDINAL", "CARDINAL"]:
            if is_date(ent.text):
                _add_to_entities(ent.text)
            else:
                for token in ent.text.split():
                    if is_date(token):
                        _add_to_entities(token)
        
    for new_ent in extract_numeric_values(text):
        if not any(new_ent in ent for ent in entities):
            entities.add(new_ent)

    return entities


def postprocess_atomic_facts(_atomic_facts, para_breaks, nlp):
    """
    Currently not needed for sentence-level breakdown and postprocessing,
    this function can be kept or simplified as needed.
    """
    verbs = ["born.", " appointed.", " characterized.", " described.", " known.", " member.", " advocate.", "served.", "elected."]
    permitted_verbs = ["founding member."]

    atomic_facts = []
    new_atomic_facts = []
    new_para_breaks = []

    for i, (sent, facts) in enumerate(_atomic_facts):
        sent = sent.strip()
        if len(sent.split())==1 and i not in para_breaks and i > 0:
            assert i not in para_breaks
            atomic_facts[-1][0] += " " + sent
            atomic_facts[-1][1] += facts
        else:
            if i in para_breaks:
                new_para_breaks.append(len(atomic_facts))
            atomic_facts.append([sent, facts])

    for i, (sent, facts) in enumerate(atomic_facts):
        entities = detect_entities(sent, nlp)
        covered_entities = set()
        new_facts = []
        for j, fact in enumerate(facts):
            if any(fact.endswith(verb) for verb in verbs) and not any(fact.endswith(verb) for verb in permitted_verbs):
                if any(fact[:-1] in other_fact for k, other_fact in enumerate(facts) if k != j):
                    continue
            sent_entities = detect_entities(fact, nlp)
            covered_entities |= set(e for e in sent_entities if e in entities)
            new_entities = sent_entities - entities
            if len(new_entities) > 0:
                do_pass = False
                for new_ent in new_entities:
                    pre_ent = None
                    for ent in entities:
                        if ent.startswith(new_ent):
                            pre_ent = ent
                            break
                    if pre_ent is None:
                        do_pass = True
                        break
                    fact = fact.replace(new_ent, pre_ent)
                    covered_entities.add(pre_ent)
                if do_pass:
                    continue
            if fact in new_facts:
                continue
            new_facts.append(fact)
        try:
            assert entities == covered_entities
        except Exception:
            new_facts = facts  # If spacy entity linking fails, retain original facts

        new_atomic_facts.append((sent, new_facts))

    return new_atomic_facts, new_para_breaks

def ensure_directory_exists(filepath):
    """Ensure the directory for the given filepath exists."""
    directory = os.path.dirname(filepath)
    if directory and not os.path.exists(directory):
        os.makedirs(directory)

def process_section(section, fact_generator):
    atomic_facts = fact_generator.get_atomic_facts(section)
    total_sentences = len(sent_tokenize(section)) 

    atomic_facts = clean_claims(atomic_facts)

    return atomic_facts, total_sentences

def extract_and_deduplicate_facts(survey, topic):
    fact_generator = AtomicFactGenerator("demos")

    sections = re.findall(
        r'(^## \d+(?:\.\s|\s|$).*?)(?=^## \d+(?:\.\s|\s|$)|^## References|\Z)',
        survey,
        flags=re.DOTALL | re.MULTILINE
    )

    total_sentences = 0
    all_atomic_facts = []

    print(f"Processing {len(sections)} sections for topic: {topic}, start get facts")
    with ThreadPoolExecutor() as executor:
        futures = []
        for section in sections:
            futures.append(executor.submit(process_section, section, fact_generator))

        for future in tqdm(as_completed(futures), total=len(futures), desc=f"Processing {topic} sections into atomic facts"):
            section_atomic_facts, section_sentences = future.result()
            all_atomic_facts.extend(section_atomic_facts)
            total_sentences += section_sentences
    print(f"Finished processing {len(sections)} sections for topic: {topic}")

    claims_before_dedup = len(all_atomic_facts)
    density_before_dedup = claims_before_dedup / total_sentences if total_sentences else 0
    print(f"[{topic}] Claims Before Dedup: {claims_before_dedup}, Density Before: {density_before_dedup:.4f}")

    deduplicated_facts = fact_generator.deduplicate_atomic_facts(all_atomic_facts)
    deduplicated_facts = clean_claims(deduplicated_facts)

    claims_after_dedup = len(deduplicated_facts)
    density_after_dedup = claims_after_dedup / total_sentences if total_sentences else 0

    print(f"[{topic}] Claims After Dedup: {claims_after_dedup}, Density After: {density_after_dedup:.4f}")

    return {
        "total_sentences": total_sentences,
        "claims_before_dedup": claims_before_dedup,
        "claim_density_before_dedup": round(density_before_dedup, 4),
        "claims_after_dedup": claims_after_dedup,
        "claim_density_after_dedup": round(density_after_dedup, 4),
        "compression_ratio": round(claims_after_dedup / claims_before_dedup, 4)
    }