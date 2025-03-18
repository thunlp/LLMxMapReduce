from Generator import Generator


class BasePipeline:
    def __init__(self, config, print_intermediate_path=None,doc_id=None):

        self.generator = Generator(
            config, print_intermediate_path=print_intermediate_path, doc_id=doc_id)
        
    def remove_chunk(self, chunks: list, irrelevant_note=['[NOT MENTIONED]'], question=''):
        # Remove the element corresponding to index in chunk
        new_chunks = []
        # If the topic is not mentioned
        for q in question:
            for note in irrelevant_note:
                if note.upper() in q.upper():
                    return chunks

        for chunk in chunks:
            flag = False
            for note in irrelevant_note:
                if note.upper() in chunk.upper():
                    flag = True
                    break
            if not flag:
                new_chunks.append(chunk)
        return new_chunks


    def run(self, doc, question, chunk_size):
        split_docs = self.generator.chunk_docs(doc, chunk_size,question=question)
        contexts = split_docs

        map_result = self.generator.mr_map(split_docs,  question)
        map_result = self.remove_chunk(
            map_result, question=question, irrelevant_note=['[NO INFORMATION]'])
        collapse_result = self.generator.mr_collapse(
            map_result, question, token_max=chunk_size)
        collapse_result = self.remove_chunk(
            collapse_result, question=question, irrelevant_note=['[NO INFORMATION]'])
        
        reduce_result = self.generator.mr_reduce(collapse_result, question)
        return reduce_result


