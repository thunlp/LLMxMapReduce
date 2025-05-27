GROUP_PROMPT = """You are a professional academic assistant tasked with helping researchers conduct literature reviews based on provided materials.

# Background:
I am in the process of writing an academic survey on the **topic** \"{survey_title}\". All relevant reference **paper titles** have been provided, and your responsibility is to group these papers for writing digests based on these materials.

# Task Description:
Group all the provided papers in an objective and logical manner. Each group should signify a general research direction. Avoid creating overly small groups; ensure that each group has substantial support. If there are papers with few related counterparts, consider merging them into other similar-themed groups. Note that each bibkey can only be assigned to one group.

# Input Materials
## **Survey topic**
\"{survey_title}\"

## **Paper titles**
{titles}

# Output Requirements
## Format Requirements
1. You need to output Group Result with delimiters ```markdown\\n```.
2. Each group of reference paper bibkeys must be enclosed within a pair of brackets. Cite specific papers' bibkey rather than using general terms like \"all papers\" or \"all sections\". Cite the paper bibkey, not the paper title. If there are no suitable papers to cite in a description, write the sentences without any citation. Do not leave empty brackets [] at the end of sentences.

## Format Example
Rationale:
Think step-by-step about how to group the papers together.

Group Result:
```markdown
Group 1:
Papers: [\"BIBKEY1\", \"BIBKEY2\"]
Reason: Explain why you grouped these papers together
Group 2:
Papers: [\"BIBKEY3\", \"BIBKEY4\"]
Reason: Explain why you grouped these papers together
...
Group n:
Papers: [\"BIBKEYM\", \"BIBKEYN\"]
Reason: Explain why you grouped these papers together
```
"""

INIT_OUTLINE_PROMPT = """You are a professional academic assistant tasked with helping researchers conduct literature reviews based on provided materials.

# Background
I need to develop an academic survey outline on the topic \"{title}\", using the provided reference papers. Due to the challenge of fully processing all reference papers, I rely on the outline to guide information extraction. This involves identifying relevant content and using it logically and critically to compose the final academic survey, ensuring its structure, analytical rigor, and contribution to the field. These papers have been carefully selected and confirmed to be relevant to the survey topic.

# Task Description
YOUR TASK is to construct the outline of the survey based on the provided **paper abstracts**. Each outline section should have a systematic and detailed description. The description consists of two parts:
- Digest Construction: Determine the information to be gleaned from the provided reference full papers for creating a digest. This digest will be used in the subsequent Digest Analysis to write a logical, critical, and insightful academic survey section. The focus is on the reference papers, not the outline or the survey itself. Instead of focusing on a single paper, direct your attention to a particular topic and perspective. For example, "To facilitate the construction of the corresponding section in the final survey, the digest should extract the main content, research methods, results, conclusions, and limitations of the reference papers."
- Digest Analysis: Explain how to use the extracted information to organize and analyze the papers with executable steps. Avoid merely listing the information; instead, analyze and synthesize it to form a coherent and well-structured narrative. For example, extract common patterns, conflicts, or evolutionary trends (e.g., "Method X yields divergent results in Studies A and B due to dataset biases"), propose representative viewpoints (e.g., "While mainstream research emphasizes Factor Y, emerging studies question its long-term validity"), provide actionable guidance for literature review writing, such as: "Compare the experimental designs of Study A (2018) and Study B (2022) to explain potential reasons for divergent conclusions.", "Summarize the common limitations of the 7 studies and propose an improved framework.", and highlight unresolved issues or interdisciplinary opportunities (e.g., "Integrating Computational Model X with Empirical Approach Y could overcome current bottlenecks").

You can follow the principles below to generate a high-quality outline:
1. **Systematic**:
Comprehensively cover all relevant aspects of the topic to form a complete and rigorous knowledge framework, enabling readers to grasp the overall picture of the topic. The content of each part should be arranged in a reasonable logical order, such as chronological order, causal order or order of importance. Moreover, the outline should have a clear hierarchical structure, accurately dividing different levels through multi-level headings to facilitate readers' understanding of the organization and logical relationship of the content. Each section needs to have an appropriate number of sub-sections.
2. **Targeted**: 
Each item of the outline must be closely related to the survey topic, precisely locating the core points and key issues of the topic, and excluding any irrelevant content to ensure the purity and focus of the outline. 
3. **Objective**: 
The wording and content arrangement of the outline should not carry personal subjective biases or emotional tendencies. The display of various research results and different academic viewpoints should be fair and objective to ensure the authenticity and reliability of the content. For controversial academic viewpoints or research results, the outline should truthfully reflect the main contents of different stances, including their viewpoints, arguments, research methods and logic, presenting an objective and comprehensive picture of the academic controversy.

# Input Materials
## **Paper Abstracts**
{abstracts}

# Output Requirements
## Format Requirements
1. The output **Skeleton** must be in markdown format, with the topic as the first-level heading. The **Skeleton** should enclose with delimiters ```markdown\\n```.
2. Each section description should cite appropriate paper bibkeys. If you believe that the content of a particular section can draw on certain abstracts, you should include the corresponding bibkeys at the end of the sentence.
3. Each section must contain suitable sub-sections, and it is recommended to use markdown headings to represent the hierarchical structure. Don't add Reference section.
4. Each group of reference paper bibkeys must be enclosed within a pair of brackets. Cite specific papers' bibkey rather than using general terms like \"all papers\" or \"all sections\". Cite the paper abstracts bibkeys, not the index themselves. If there are no suitable papers to cite in a description, write the sentences without any citation. 

## Format Example
```markdown
# {title}
## Section A
Digest Construction:
Write about what information should be extracted from the full paper in this section.
Digest Analysis: 
Write about how to organize and analyse papers [\"BIBKEY1\", \"BIBKEY2\"] with executable step.
## Section B
Digest Construction:
Write about what information should be extracted from the full paper in this section.
Digest Analysis: 
Write about how to organize and analyse papers [\"BIBKEY1\", \"BIBKEY2\"] with executable step.
### Subsection A
Digest Construction:
Write about what information should be extracted from the full paper in this section.
Digest Analysis: 
Write about how to organize and analyse papers [\"BIBKEY1\", \"BIBKEY2\"] with executable step.
### Subsection B
Digest Construction:
Write about what information should be extracted from the full paper in this section.
Digest Analysis: 
Write about how to organize and analyse papers [\"BIBKEY1\", \"BIBKEY2\"] with executable step.
#### Subsubsection A
Digest Construction:
Write about what information should be extracted from the full paper in this section.
Digest Analysis: 
Write about how to organize and analyse papers [\"BIBKEY1\", \"BIBKEY2\"] with executable step.
## Section C
Digest Construction:
Write about what information should be extracted from the full paper in this section.
Digest Analysis: 
Write about how to organize and analyse papers [\"BIBKEY1\", \"BIBKEY2\"] with executable step.
```
"""

CONCAT_OUTLINE_PROMPT = """You are a professional academic assistant tasked with helping researchers conduct literature reviews based on provided materials.

# Background
I am required to write an academic survey outline about topic \"{title}\" based on the provided **initial outlines**. These outlines, which are organized according to different reference paper abstracts, offer diverse perspectives on the topic. Due to the challenge of fully processing all reference papers, I rely on the outline to guide information extraction. This involves identifying relevant content and using it logically and critically to compose the final academic survey, ensuring its structure, analytical rigor, and contribution to the field.

# Task Description
Given that there may be overlaps and conflicts among the outlines, you need to comprehensively consider these suggestions, reorganize them, and generate a new and improved outline. It should distill the common elements from the provided outlines, try to include all sections in provided initial outlines, rather than emphasizing a single one, and revolve around the section title. 

## Think Principles
Each outline section should have a systematic and detailed description. The description consists of two parts:
- Digest Construction: Determine the information to be gleaned from the provided reference full papers for creating a digest. This digest will be used in the subsequent Digest Analysis to write a logical, critical, and insightful academic survey section. The focus is on the reference papers, not the outline or the survey itself. Instead of focusing on a single paper, direct your attention to a particular topic and perspective. For example, "To facilitate the construction of the corresponding section in the final survey, the digest should extract the main content, research methods, results, conclusions, and limitations of the reference papers."
- Digest Analysis: Explain how to use the extracted information to organize and analyze the papers with executable steps. Avoid merely listing the information; instead, analyze and synthesize it to form a coherent and well-structured narrative. For example, extract common patterns, conflicts, or evolutionary trends (e.g., "Method X yields divergent results in Studies A and B due to dataset biases"), propose representative viewpoints (e.g., "While mainstream research emphasizes Factor Y, emerging studies question its long-term validity"), provide actionable guidance for literature review writing, such as: "Compare the experimental designs of Study A (2018) and Study B (2022) to explain potential reasons for divergent conclusions.", "Summarize the common limitations of the 7 studies and propose an improved framework.", and highlight unresolved issues or interdisciplinary opportunities (e.g., "Integrating Computational Model X with Empirical Approach Y could overcome current bottlenecks").

# Input Materials
## **Initial Outlines**
{outlines}

# Output Requirements
## Format Requirements
1. The output **New Skeleton** must be in markdown format, with the topic as the first-level heading. The **New Skeleton** should enclose with delimiters ```markdown\\n```.
2. Each section description should cite appropriate paper bibkeys. If you believe that the content of a particular section can draw on certain abstracts, you should include the corresponding bibkeys at the end of the sentence.
3. Each section must contain suitable sub-sections, and it is recommended to use markdown headings to represent the hierarchical structure. Don't add Reference section.
4. Each group of reference paper bibkeys must be enclosed within a pair of brackets. Cite specific papers' bibkey rather than using general terms like \"all papers\" or \"all sections\". Cite the papers that are mentioned in the descriptions of the initial outlines, not the index themselves. If there are no suitable papers to cite in a description, write the sentences without any citation. 

## Format Example
```markdown
# {title}
## Section A
Digest Construction:
Write about what information should be extracted from the full paper in this section.
Digest Analysis: 
Write about how to organize and analyse papers [\"BIBKEY1\", \"BIBKEY2\"] with executable step.
## Section B
Digest Construction:
Write about what information should be extracted from the full paper in this section.
Digest Analysis: 
Write about how to organize and analyse papers [\"BIBKEY1\", \"BIBKEY2\"] with executable step.
### Subsection A
Digest Construction:
Write about what information should be extracted from the full paper in this section.
Digest Analysis: 
Write about how to organize and analyse papers [\"BIBKEY1\", \"BIBKEY2\"] with executable step.
### Subsection B
Digest Construction:
Write about what information should be extracted from the full paper in this section.
Digest Analysis: 
Write about how to organize and analyse papers [\"BIBKEY1\", \"BIBKEY2\"] with executable step.
#### Subsubsection A
Digest Construction:
Write about what information should be extracted from the full paper in this section.
Digest Analysis: 
Write about how to organize and analyse papers [\"BIBKEY1\", \"BIBKEY2\"] with executable step.
## Section C
Digest Construction:
Write about what information should be extracted from the full paper in this section.
Digest Analysis: 
Write about how to organize and analyse papers [\"BIBKEY1\", \"BIBKEY2\"] with executable step.
```
"""

SINGLE_DIGEST_PROMPT = """You are a professional academic assistant specializing in literature reviews, supporting researchers in efficiently synthesizing relevant research.

# Background
Currently, you are assisting with the writing of an academic survey. Since directly incorporating full papers can be overwhelming, the first step is to distill each paper into a concise **paper digest**. This digest should capture the essential information from the paper necessary and give critical analysis of current paper for constructing the survey. This paper has been determined to be relevant to the current review topic through preliminary work, so there should have a section in the outline that is relevant for this paper.

# Task Description
**YOUR TASK** is to create this digest for the provided **reference paper** based on the pre-defined **outline** of the survey. You must follow the instruction in section description to extract information from full content of reference paper. The resulting digest will act as a representative summary of the reference paper, enabling its use in the broader survey development process. Besides, based on the full paper, you need to provide suggestions to improve the outline quality. 

## Digest Think Principles
**Please follow these principles to generate the paper digest**:
1. **Identify Relevant Sections**: Begin by reviewing the outline and identifying which sections are most pertinent to the content of the reference paper. Not all sections (or sub-sections) of the outline will be relevant to the paper. You may omit sections or sub-sections that do not directly apply to the content of the reference paper. But you should ensure that every level of the outline is preserved. Do not alter the structure of the outline. You must not add new sub-sections under existing sections. Fill in the relevant content within the structure provided.
2. **Condense Content**: When dealing with relevant sections, strictly adhere to the guidance provided in the section description. Condense the paper's content to present the essential information for the survey. Base this critical analysis and insights on the entire content of the paper. In the process, summarize the challenges in the current field and reflect on the deficiencies of the current paper. A critical assessment of the extracted data is necessary. This includes evaluating aspects such as the uniqueness and generalizability of research methods, the representativeness and limitations of samples, the rationality of experimental design, the completeness and innovativeness of the theoretical framework, the depth of result interpretation and discussion, as well as the limitations and prospects of the research. The results of this work will be utilized in the academic survey to conduct a comprehensive analysis of the paper.
3. **Faithfulness**: Throughout this process, make sure not to introduce any new facts or interpretations that are not supported by the original paper. Stay true to the original paper's findings and avoid any content that is not actually in the paper, i.e., do not produce hallucinated content. Encourage the extraction of experimental results, important formulas, etc from the original text to enhance the amount of information of the materials. Don't extract whole table and chart. Instead, extract the main content of the table and chart.

## Suggestions Think Principles
1. If this article is not suitable for any part of the outline, please provide suggestions for modifying the outline structure or title so that this article can be included. When making revisions, it is necessary to comprehensively consider the compatibility between the core content of this article and the existing outline framework, so that the new outline structure or title can accurately reflect the position and role of this article in the research topic.
2. If the information in this article is insufficient to fill in the outline content, please provide suggestions for modifying the outline description to better utilize this article. When modifying the outline description, it should be based on a deep exploration of the content of this article, so that the scope of the outline description matches the information provided in this article, and avoid the inability to effectively integrate the content of this article due to the outline requirements being too high or too low.
3. Based on the full text and the summarized information above, provide innovative and executable suggestions to address the challenges in the current field and the shortcomings of current work. Give a prediction about the future research direction to address the shortcomings of the current work. The future directions should be concrete rather than generic.

# Input Materials
## Bibkey of the Reference Paper
['{paper_bibkey}']

## Initial Skeleton
```markdown
{survey_outline}
```

## Reference Paper
{paper_content}

## Initial Skeleton
```markdown
{survey_outline}
```

# Output Requirements
## Format Requirements
1. **Output Format**: The digest must be in markdown format. Use a first-level title marked with one "#" for the topic and enclose the content in ```markdown\\n```. All section titles from the outline must appear in the digest at the same level; do not skip or omit any sections. The section title must the same with the outline, don't modify any words in the section title. Neglect the structure and title from reference paper, only focus on the content of the paper and follow the outline structure.
2. **Citation Format**: You need to place ['{paper_bibkey}'] at the end of the sentence to specify the source of the information. If the information is not directly from the paper, you can write the sentence without any citation. You should write citation in both digest and suggestion.
3. **Formula Format**: If there are formulas in the output, please use LaTeX format to represent them. For example, $y = x^2$ for inline formulas and $$y = x^2$$ for block formulas. Don't quote the formula with ```<FORMULA>```, replace it with $$<FORMULA>$$.
4. **Suggestion Format**: Suggestion should be quoted by ```suggestion```. You only need to provide suggestions, no need to provide the modified new outline. Suggestion should have suitable citation to the paper bibkey.

## Format Example
Paper Digest:
```markdown
{outline_example}
```

Suggestion:
```suggestion
Give your outline modification suggestion for better use this paper as a reference.
```
"""

DIGEST_BASE_PROMPT = """You are a professional academic assistant tasked with helping researchers conduct literature reviews based on provided materials.

# Background
The academic survey topic is \"{title}\". As an academic literature review architect, your task is to refine the theoretical framework based on the initial outline and paper digests (containing technical details, field challenges, critiques of existing works, and proposed solutions). The outline consists of 3 parts: Structure, Digest Construction, and Digest Analysis. The Structure part provides a high-level overview of the survey, while the Digest Construction and Digest Analysis parts guide the extraction and analysis of information from the full papers. You need to give modification suggestion about these three parts. The goal is to ensure the outline is logically rigorous, critically insightful, and academically forward-looking. After paper digests, there are some suggestions based on full papers, you need to take them into account and integrate them into a better suggestion. 

# Task Description:
The final goal is to build up a comprehensive and critical domain analysis framework based on reference papers, and based on the framework, analyse current shortage, domain challenge, finally give promising research direction and executable solutions. To achieve this, you need to follow these principles:
1. Content Check:
- Verify whether the outline encompasses all essential theoretical aspects of the survey topic. If any crucial theoretical components are missing, suggest new sections or sub-sections to bridge these gaps. Assert the description in outline has enough citation to specify the source of the information. Digest Analysis must clearly indicate which papers to compare and analyze with clear citations.
- Ensure that all relevant papers in the digests can be incorporated into the outline. If a paper does not fit into any section of the outline, provide suggestions for modifying the outline structure or title to include it.
- Confirm that all important information can be extracted from the full reference papers following the Digest Construction instructions. If the information is insufficient to fill in the outline, suggest modifications to the Digest Construction for better utilization of the information. Encourage the extraction of specific details such as experimental tables and comparative data from the papers, rather than relying on vague summarizations, to better support the Digest Analysis.
- Check if the guidance for identifying the limitations, deficiencies, and potential flaws in the full reference papers, as well as analyzing the challenges in this field, is clear and actionable. If not, propose modifications to the Digest Construction to rectify the existing issues, such as adding a defect label to guide from which perspective to consider the shortcomings of the current work by setting a label.
- Ascertain that all important information in the digests has been utilized in the outline. If the information is insufficient for the outline content, suggest adjustments to the Digest Analysis to make better use of it.
2. Integration:
- Instead of merely enumerating information, seamlessly integrate the findings from digests into the existing analysis structure. Clearly demarcate the theme of each section and synthesize relevant content to construct a coherent and well-structured narrative. Each parent chapter should lay a narrative foundation for its child chapters, while the child chapters are expected to offer specific and detailed content to support the parent chapter.
- For the overall outline, a complete and all-encompassing main perspective is indispensable. There should be a natural sequence between chapters, a logical progression, and no disruptions in the reader's cognitive flow. Approach the current topic from multiple vantage points and integrate diverse viewpoints.
- In the parent chapter, a clear-cut and explicit theme is essential. Comprehensively expound on the core content of the sub-chapters, integrate, compare, and dissect their content. Summarize the commonalities among them, contrast their differences, and prognosticate possible future development trajectories. Minimize the overlap between sub-chapters to ensure that each sub-chapter presents its own distinct content. Systematically summarize the current challenges in the research field. Highlight limitations in existing studies, including sample size limitations, methodological constraints, or unaddressed research questions. Considering emerging trends and technological advancements in the field, propose specific and actionable potential areas for future research.
- In the sub-chapters, more precise themes are required. Conduct an in-depth analysis of relevant work within the current thematic context. Compare specific methods, experimental outcomes, advantages, and drawbacks. Integrate papers with congruent perspectives and make distinct comparisons between papers with divergent perspectives. Highlight the unique contributions of each paper and contrast the conflicts and contradictions between different papers. Based on all relevant papers on the current topic, explore the projection of future development directions and practicable solutions to extant problems. Thoroughly analyze the nuanced differences in methods and critically appraise the specific research results of each cited source. Clearly accentuate the contrasting points and engender novel perspectives. Deeply integrating different perspectives to generate new viewpoints necessitates more analytical statements rather than merely descriptive ones. Conduct in-depth research on subtle differences or debates in literature.
3. Challenge and Solution:
- Based on the analysis framework, integrate the challenges confronted by various sub-fields and the deficiencies of current methods. Systematically organize the work proposed to tackle these issues and challenges, and conduct a comprehensive analysis of their strengths and weaknesses. It is crucial to delve into the underlying causes of the challenges and deficiencies, rather than merely listing the problems.  Deeply analyze the reason of challenges and problems. From an interdisciplinary perspective, examine the current research issues and offer a broader perspective for consideration.
- In response to the summarized challenges and deficiencies, predict future research directions aimed at rectifying the shortcomings of current work. Adopt a holistic perspective. Propose innovative solutions within a comprehensive analytical framework to address the current challenges in the field, rather than being confined to a solution for a single problem. The future directions should be specific and actionable, not just general statements. The solutions should be innovative and analyse how these solutions will effect the current challenges and problems. You can put forward possible solutions by considering the adoption of methods from other fields or disciplines and by summarizing the successful methodologies in the history of your own discipline. 

# Input Materials
## **Initial Skeleton**: 
```markdown
{outline}
```

## **Paper Digests**:
{digests}

# Output Requirements
## Format requirements:
1. All suggestions must be quoted by one pair of ```suggestion\\n```. Don't give the modified outline example in the output. Don't allowed multiple ```suggestion\\n``` in the output. 
2. Each group of reference paper bibkeys must be enclosed within a pair of brackets. Cite specific papers' bibkey rather than using general terms like \"all papers\" or \"all sections\". Cite the papers that are mentioned in the descriptions of initial outline and paper digests, not the index themselves. If there are no suitable papers to cite in a description, write the sentences without any citation. 
3. The suggestions should be actionable and closely aligned with the survey's objectives. If necessary, do not hesitate to propose significant changes to the outline, as a complete overhaul might be exactly what is required to enhance the quality and effectiveness of the survey. Don't just simply list all suggestions, but provide a clear-cut direction, with sufficient representativeness and conciseness. Each modification requires sufficient evidence and argumentation. Suggestion should have suitable citation to the paper bibkey.
4. If there are formulas in the output, please use LaTeX format to represent them. For example, $y = x^2$ for inline formulas and $$y = x^2$$ for block formulas. Don't quote the formula with ```<FORMULA>```, replace it with $$<FORMULA>$$.
5. Don't add Reference section.

## Format Example
```suggestion
1. Describe the core objective of this group of suggestions:
- Specific suggestion about how to modify initial outline about current core objective [\"BIBKEY1\", \"BIBKEY2\",...].
- Specific suggestion about how to modify initial outline about current core objective [\"BIBKEY1\", \"BIBKEY2\",...].
- Specific suggestion about how to modify initial outline about current core objective [\"BIBKEY1\", \"BIBKEY2\",...].

2. Describe the core objective of this group of suggestions:
- Specific suggestion about how to modify initial outline about current core objective [\"BIBKEY1\", \"BIBKEY2\",...].
- Specific suggestion about how to modify initial outline about current core objective [\"BIBKEY1\", \"BIBKEY2\",...].
- Specific suggestion about how to modify initial outline about current core objective [\"BIBKEY1\", \"BIBKEY2\",...].

3. Describe the core objective of this group of suggestions:
- Specific suggestion about how to modify initial outline about current core objective [\"BIBKEY1\", \"BIBKEY2\",...].
- Specific suggestion about how to modify initial outline about current core objective [\"BIBKEY1\", \"BIBKEY2\",...].
- Specific suggestion about how to modify initial outline about current core objective [\"BIBKEY1\", \"BIBKEY2\",...].
```
"""

DIGEST_FREE_PROMPT = """You are a professional academic assistant tasked with helping researchers conduct literature reviews based on provided materials.

# Background
The academic survey topic is \"{title}\". As an academic literature review architect, your task is to refine the theoretical framework based on the initial outline. The outline consists of 3 parts: Structure, Digest Construction, and Digest Analysis. The Structure part provides a high-level overview of the survey, while the Digest Construction and Digest Analysis parts guide the extraction and analysis of information from the full papers. You need to give modification suggestion about these three parts. The goal is to ensure the outline is logically rigorous, critically insightful, and academically forward-looking.

# Task Description:
To provide effective suggestions for refining the initial outline, please follow these principles:
1. **Logical Coherence**:
- Thoroughly review each chapter in the outline. Analyze the content volume and scope of each chapter to ensure a balanced distribution of information across the entire review. Add explicit transitional phrases at the beginning of each section to enhance the logical flow between chapters.
- The outline structure needs to be clear and concise, and excessive redundancy is not allowed. A chapter is not allowed to have more than 10 sub chapters. It is not allowed to have only one sub chapter, nor is it allowed to have too many sub chapters under one chapter. For chapters with an excessive amount of content, break them down into multiple sub-chapters. Each sub-chapter should have a clear and distinct focus, and the division should be based on logical sub-themes within the original chapter. New sub-section must have its Digest Construction and Digest Analysis. If there are sub-chapters with very little content and no related sibling sub-chapters, delete it and merge it back into its parent chapters to improve the integrity of the outline. Don't allow to have single sub-section in a section and a chapter is only related to one literature.
- Identify chapters with similar content and merge them. Eliminate redundant information during the consolidation process to streamline the overall structure of the review. 
- Rearrange the order of chapters to improve the narrative logic. Ensure that the flow of ideas from one chapter to the next is smooth and coherent. For example, place more fundamental or introductory chapters earlier in the outline.
- Evaluate the content of the initial outline to enhance its informativeness. Refine section titles to be more specific. For example, change "Datasets" to "Datasets for [specific task]". Conduct a critical analysis of the current landscape, taking into account relevant factors and trends within the field.
2. **Systematic**:
- Within each Digest Analysis in each section, reflect on the current analytical framework to better conduct a comparison and contrast analysis.  Revise the wording to integrate the extracted but unused information from Digest Construction into the existing analysis framework.
- Think about the logicality, integration, and criticality of the current framework. Better analysis all provided information instead of simply list all information. Highlight how the findings of one study either corroborate or conflict with others. Pinpoint the similarities and differences between various studies or approaches. Seek out overarching patterns or trends that surface across the digests. Summarize the collective knowledge in a way that enhances the overall understanding of the research area. 
- Based on the digests analysis in the current description, identify the gaps in the existing body of knowledge. Indicate areas where research is insufficient or inconclusive. Subsequently, make projections regarding future research directions. 
3. Challenge and Solution:
- Based on the analysis framework, integrate the challenges confronted by various sub-fields and the deficiencies of current methods. Systematically organize the work proposed to tackle these issues and challenges, and conduct a comprehensive analysis of their strengths and weaknesses. It is crucial to delve into the underlying causes of the challenges and deficiencies, rather than merely listing the problems. From an interdisciplinary perspective, examine the current research issues and offer a broader perspective for consideration.es and shortcomings, rather than just listing the problems. From an interdisciplinary perspective, consider current research issues and provide a broader perspective to think about.
- In response to the summarized challenges and deficiencies, predict future research directions aimed at rectifying the shortcomings of current work. Adopt a holistic perspective. Propose innovative solutions within a comprehensive analytical framework to address the current challenges in the field, rather than being confined to a solution for a single problem. The future directions should be specific and actionable, not just general statements. The solutions should be innovative. You can put forward possible solutions by considering the adoption of methods from other fields or disciplines and by summarizing the successful methodologies in the history of your own discipline.

# Input Materials
## **Initial Skeleton**: 
```markdown
{outline}
```
## **Evaluation Result**:
{eval_detail}

# Output Requirements
## Format requirements:
1. All suggestions must be quoted by one pair of ```suggestion\\n```. Don't give the modified outline example in the output. Don't allowed multiple ```suggestion\\n``` in the output. 
2. If there are formulas in the output, please use LaTeX format to represent them. For example, $y = x^2$ for inline formulas and $$y = x^2$$ for block formulas. Don't quote the formula with ```<FORMULA>```, replace it with $$<FORMULA>$$.
3. Don't add Reference section.

## Format Example
```suggestion
1. Describe the core objective of this group of suggestions:
- Specific suggestion about how to modify initial outline about current core objective [\"BIBKEY1\", \"BIBKEY2\",...].
- Specific suggestion about how to modify initial outline about current core objective [\"BIBKEY1\", \"BIBKEY2\",...].
- Specific suggestion about how to modify initial outline about current core objective [\"BIBKEY1\", \"BIBKEY2\",...].

2. Describe the core objective of this group of suggestions:
- Specific suggestion about how to modify initial outline about current core objective [\"BIBKEY1\", \"BIBKEY2\",...].
- Specific suggestion about how to modify initial outline about current core objective [\"BIBKEY1\", \"BIBKEY2\",...].
- Specific suggestion about how to modify initial outline about current core objective [\"BIBKEY1\", \"BIBKEY2\",...].

3. Describe the core objective of this group of suggestions:
- Specific suggestion about how to modify initial outline about current core objective [\"BIBKEY1\", \"BIBKEY2\",...].
- Specific suggestion about how to modify initial outline about current core objective [\"BIBKEY1\", \"BIBKEY2\",...].
- Specific suggestion about how to modify initial outline about current core objective [\"BIBKEY1\", \"BIBKEY2\",...].
```
"""

OUTLINE_CONVOLUTION_PROMPT = """You are a professional academic assistant tasked with helping researchers conduct literature reviews based on provided materials.

# Background:
The academic survey topic is \"{title}\". An initial outline for this survey has been developed and has received independent reviews from multiple reference papers perspectives. As a result, a diverse range of individual suggestions has been collected, each accompanied by an evaluation result. You need to fully integrate these suggestions to adapt to the current logical framework of the Skeleton. The outline consists of 3 parts: Structure, Digest Construction, and Digest Analysis. The Structure part provides a high-level overview of the survey, while the Digest Construction and Digest Analysis parts guide the extraction and analysis of information from the full papers. You need to give modification suggestion about these three parts. The goal is to ensure the outline is logically rigorous, critically insightful, and academically forward-looking. 

# Task Description:
To integrate the group of suggestions, please follow these principles:
1. Systematic Integration
- Comprehend the existing analysis framework and suggestions. Integrate various one-sided suggestions into a comprehensive proposal. Merge suggestions with similar themes. Analyze the operations of a particular part from different perspectives and put forward a new modification plan after integration. Each modification must be supported by sufficient evidence and argumentation. This process demands both strategic planning and meticulous attention to detail. It is essential to analyze the advantages and disadvantages of individual tasks.
- Retain the conflicts, comparisons, commonalities, and differences of viewpoints in the reference papers associated with different suggestions. Emphasize the academic differences in each section of the outline analysis to reinforce it. Thoroughly analyze the subtle differences in methods and critically evaluate the specific research results of each cited source. Clearly highlight the contrasting points and generate new perspectives. Conduct in-depth research on subtle differences or debates in literature. Retain the compared and contrasted paper citation in the suggestion description.
- Hierarchical Structure: Categorize the suggestions into high-level (strategic level) and low-level (operational level) to ensure that each suggestion has a distinct position and function. Each low-level suggestion must have suitable citation to support the modification. The high-level suggestions should be more general and strategic, while the low-level suggestions should be more specific and operational. The high-level suggestions should guide the overall direction of the outline, while the low-level suggestions should provide detailed guidance on how to implement the high-level suggestions. 
- Each suggestion will be evaluated. You are required to incorporate the feedback of corresponding suggestions, and suggestions with higher scores should carry greater weights. The evaluation results should be considered when integrating the suggestions. 
- The outline structure needs to be clear and concise, and excessive redundancy is not allowed. A chapter is not allowed to have more than 10 sub chapters. For instance, if multiple suggestions call for the addition of a new chapter, and each only involves one reference yet has a similar theme, you should analyze the themes and types of these references and integrate them into a single new chapter to prevent an overly fragmented structure, and leave all bibkeys in the suggestion description.
2. Challenge and Solution
- Based on the analysis framework, integrate the challenges confronted by various sub-fields and the deficiencies of current methods. Systematically organize the work proposed to tackle these issues and challenges, and conduct a comprehensive analysis of their strengths and weaknesses. It is crucial to delve into the underlying causes of the challenges and deficiencies, rather than merely listing the problems. From an interdisciplinary perspective, examine the current research issues and offer a broader perspective for consideration.es and shortcomings, rather than just listing the problems. From an interdisciplinary perspective, consider current research issues and provide a broader perspective to think about.
- In response to the summarized challenges and deficiencies, predict future research directions aimed at rectifying the shortcomings of current work. Adopt a holistic perspective. Propose innovative solutions within a comprehensive analytical framework to address the current challenges in the field, rather than being confined to a solution for a single problem. The future directions should be specific and actionable, not just general statements. The solutions should be innovative. You can put forward possible solutions by considering the adoption of methods from other fields or disciplines and by summarizing the successful methodologies in the history of your own discipline.

# Input Materials:
1. Initial outline: The current version of the survey outline that needs refinement.
2. Individual suggestions: Feedback from several expert reviewers, each including an evaluation about the effectiveness score of the suggestion along with a reason for the score. When aggregating the suggestions, please prioritize those with higher scores. It is essential to consider both the evaluation results and the reasoning behind them, ensuring that the strengths of the suggestions are emphasized while avoiding their weaknesses.

## Initial Skeleton
```markdown
{outline}
```

## Individual Suggestions
{suggestions}

# Output Requirements
## Format requirements:
1. All suggestions must be quoted by one pair of ```suggestion\\n```. Don't give the modified outline example in the output. Don't allowed multiple ```suggestion\\n``` in the output. 
2. Each group of reference paper bibkeys must be enclosed within a pair of brackets. Cite specific papers' bibkey rather than using general terms like \"all papers\" or \"all sections\". Cite the papers that are mentioned in the descriptions of initial outline and paper digests, not the index themselves. If there are no suitable papers to cite in a description, write the sentences without any citation. 
3. The suggestions should be actionable and closely aligned with the survey's objectives. If necessary, do not hesitate to propose significant changes to the outline, as a complete overhaul might be exactly what is required to enhance the quality and effectiveness of the survey. Don't just simply list all suggestions, but provide a clear-cut direction, with sufficient representativeness and conciseness. Each modification requires sufficient evidence and argumentation. Suggestion should have suitable citation to the paper bibkey.
4. If there are formulas in the output, please use LaTeX format to represent them. For example, $y = x^2$ for inline formulas and $$y = x^2$$ for block formulas. Don't quote the formula with ```<FORMULA>```, replace it with $$<FORMULA>$$.

## Format Example
```suggestion
1. Describe the core objective of this group of suggestions:
- Specific suggestion about how to modify initial outline about current core objective [\"BIBKEY1\", \"BIBKEY2\",...].
- Specific suggestion about how to modify initial outline about current core objective [\"BIBKEY1\", \"BIBKEY2\",...].
- Specific suggestion about how to modify initial outline about current core objective [\"BIBKEY1\", \"BIBKEY2\",...].

2. Describe the core objective of this group of suggestions:
- Specific suggestion about how to modify initial outline about current core objective [\"BIBKEY1\", \"BIBKEY2\",...].
- Specific suggestion about how to modify initial outline about current core objective [\"BIBKEY1\", \"BIBKEY2\",...].
- Specific suggestion about how to modify initial outline about current core objective [\"BIBKEY1\", \"BIBKEY2\",...].

3. Describe the core objective of this group of suggestions:
- Specific suggestion about how to modify initial outline about current core objective [\"BIBKEY1\", \"BIBKEY2\",...].
- Specific suggestion about how to modify initial outline about current core objective [\"BIBKEY1\", \"BIBKEY2\",...].
- Specific suggestion about how to modify initial outline about current core objective [\"BIBKEY1\", \"BIBKEY2\",...].
```
"""

MODIFY_OUTLINE_PROMPT = """You are a professional academic assistant tasked with helping researchers conduct literature reviews based on provided materials.

# Background
You are tasked with writing an academic survey outline on the topic \"{title}\" based on the provided Initial Skeleton. These outlines, structured according to different reference paper abstracts, present various perspectives on the topic.

# Task Description
Given the initial outline and the modification suggestions, your task is to create a new version of the outline. Cite the suggestion citations within the corresponding modified section descriptions. Each section description should provide a detailed and logical account of the content to be included in that section. Focus solely on presenting the outline, without adding any descriptions of the reasons for modifying the section. Incorporate each suggestion into the new outline, and output a complete outline enclosed with delimiters ```markdown\\n```. In modified sections, ensure that the citations in corresponding suggestions are correctly integrated into the descriptions. 

Each outline section should have a systematic and detailed description. The description consists of two parts:
- Digest Construction: Determine the information to be gleaned from the provided reference full papers for creating a digest. This digest will be used in the subsequent Digest Analysis to write a logical, critical, and insightful academic survey section. The focus is on the reference papers, not the outline or the survey itself. Instead of focusing on a single paper, direct your attention to a particular topic and perspective. For example, "To facilitate the construction of the corresponding section in the final survey, the digest should extract the main content, research methods, results, conclusions, and limitations of the reference papers."
- Digest Analysis: Explain how to use the extracted information to organize and analyze the papers with executable steps. Avoid merely listing the information; instead, analyze and synthesize it to form a coherent and well-structured narrative. For example, extract common patterns, conflicts, or evolutionary trends (e.g., "Method X yields divergent results in Studies A and B due to dataset biases"), propose representative viewpoints (e.g., "While mainstream research emphasizes Factor Y, emerging studies question its long-term validity"), provide actionable guidance for literature review writing, such as: "Compare the experimental designs of Study A (2018) and Study B (2022) to explain potential reasons for divergent conclusions.", "Summarize the common limitations of the 7 studies and propose an improved framework.", and highlight unresolved issues or interdisciplinary opportunities (e.g., "Integrating Computational Model X with Empirical Approach Y could overcome current bottlenecks").

# Input Materials
## **Initial Skeleton**
```markdown
{old_outline}
```

## **Modify Suggestions**
{outlines}

# Output Requirements
## Format Requirements
1. The output **New Skeleton** must be in markdown format, with the topic as the first-level heading. The **New Skeleton** should enclose with delimiters ```markdown\\n```.
2. Each section description should cite appropriate paper bibkeys. If you believe that the content of a particular section can draw on certain abstracts, you should include the corresponding bibkeys at the end of the sentence.
3. Each section can contain sub-sections, and it is recommended to use markdown headings to represent the hierarchical structure.
4. Each group of reference paper bibkeys must be enclosed within a pair of brackets. Cite specific papers' bibkey rather than using general terms like \"all papers\" or \"all sections\". Cite the papers that are mentioned in the descriptions of initial outline and modify suggestions, not the index themselves. If there are no suitable papers to cite in a description, write the sentences without any citation. 
5. If there are formulas in the output, please use LaTeX format to represent them. For example, $y = x^2$ for inline formulas and $$y = x^2$$ for block formulas. Don't quote the formula with ```<FORMULA>```, replace it with $$<FORMULA>$$.

## Format Example
```markdown
# {title}
## Section A
Digest Construction:
Write about what information should be extracted from the full paper in this section.
Digest Analysis: 
Write about how to organize and analyse papers [\"BIBKEY1\", \"BIBKEY2\"] with executable step.
## Section B
Digest Construction:
Write about what information should be extracted from the full paper in this section.
Digest Analysis: 
Write about how to organize and analyse papers [\"BIBKEY1\", \"BIBKEY2\"] with executable step.
### Subsection A
Digest Construction:
Write about what information should be extracted from the full paper in this section.
Digest Analysis: 
Write about how to organize and analyse papers [\"BIBKEY1\", \"BIBKEY2\"] with executable step.
### Subsection B
Digest Construction:
Write about what information should be extracted from the full paper in this section.
Digest Analysis: 
Write about how to organize and analyse papers [\"BIBKEY1\", \"BIBKEY2\"] with executable step.
#### Subsubsection A
Digest Construction:
Write about what information should be extracted from the full paper in this section.
Digest Analysis: 
Write about how to organize and analyse papers [\"BIBKEY1\", \"BIBKEY2\"] with executable step.
## Section C
Digest Construction:
Write about what information should be extracted from the full paper in this section.
Digest Analysis: 
Write about how to organize and analyse papers [\"BIBKEY1\", \"BIBKEY2\"] with executable step.
```
"""

OUTLINE_ENTROPY_PROMPT = """
You are a professional academic assistant tasked with helping researchers conduct literature reviews based on provided materials.

# Background
I am currently engaged in writing an academic survey on the topic \"{title}\" using the provided papers. I have already developed an Skeleton. I need you to conduct a detailed analysis and evaluation of this outline from the perspective of outline information entropy. Provide a score in a rigorous manner. There is no need to consider the content of the provided papers. The formats of Digest Construction and Digest Analysis are inherent and should not result in point deductions.

The outline entropy consists of two components:
1. **Title Structure Information Entropy**: Evaluate the logical coherence, generality, and thematic coverage of the title from three aspects: within-chapter analysis, between-chapter analysis, and overall structural analysis.
2. **Chapter Description Information Entropy**: Evaluate the literature integration capabilities, the depth of summarization, logical consistency, and descriptive accuracy of the chapter content.
After the analysis, provide a final overall score at the end.

# Task Description:
You need to estimate the outline information entropy from following aspect, point out the shortage, and give a score out of 10:
## Information Entropy of Structure
1. Logicality and Generality within Chapters 
- Each chapter follows a hierarchical structure: there is one core theme per section, buttressed by appropriate subsections and sub-subsections with in-depth analysis. The main chapter offers a comprehensive analytical framework from the current perspective. Sub-chapters are specific and detailed, meticulously analyzing multiple related works. Clearly contrast the advantages and disadvantages of different approaches and explore novel perspectives. To avoid focusing on a single paper within a chapter, ensure comprehensiveness and thoroughness. Minimize redundancy within chapters.
- Subsections are arranged in a logical sequence (such as chronological, methodological, or thematic progression). There is no overlapping content between sub-chapters, the logic is seamless, and there are appropriate guiding elements to link them. There should be no filler content; all subsections must directly contribute to the core theme of the section.
- Each chapter analyzes the challenges and problems within the current chapter's theme and proposes future research directions and solutions. Consider the current research problem comprehensively and offer a broader perspective for contemplation.
2. Redundancy and Complementarity between Chapters 
- Chapters explore distinct aspects of the survey topic (e.g., theoretical, empirical, technical, societal).
- Minimize overlap; any intentional repetition (such as for foundational concepts) should serve to reinforce the theme.
- The outline structure needs to be clear and concise, and excessive redundancy is not allowed. A chapter is not allowed to have more than 10 sub chapters. It is not allowed to have only one sub chapter, nor is it allowed to have too many sub chapters under one chapter.
3. Overall Theme Coverage and Logicality 
- The entire article constructs a comprehensive framework to introduce the current survey topic. The entire article has a novel perspective and comprehensive content, with both a comprehensive summary and detailed analysis and comparison. 
- The logicality of the entire article is strong, with a clear logical relationship between chapters, a smooth transition, and no cognitive barriers. 
- Include various perspectives and viewpoints, and analyze the advantages and disadvantages of different perspectives. Think about ethical impacts, challenges in this field and potential solution. The article is not only a simple summary of the current research status, but also a forward-looking analysis of the future research direction and solution. 
## Information Entropy of Chapter Descriptions
1. Single-Article Extraction: Evaluate the Digest Construction part of section description
- Encompass the essential elements necessary for crafting a summary and performing subsequent analysis.
- The extracted information should be applicable and valuable in the Digest Analysis section. The description in outline has enough citation to specify the source of the information. Digest Analysis must clearly indicate which papers to compare and analyze with clear citations.
- Provide readers with clear and actionable steps on handling papers, enabling them to effectively construct abstracts and conduct analyses based on the given content.
- Facilitate in-depth thinking for summary construction and analysis. Avoid superficiality; instead, conduct a thorough exploration of each information element. For example, consider how different research methods might impact results and conclusions.
2. Analysis of Relationships among Cited Articles: Evaluate the Digest Analysis part of section description
- Build up a \"What-Why-How\" analysis framework to cover all related work, including their methods, challenges, shoratges and solution. In leaf-level sections, delve into the key information in a paper. Don't merely scratch the surface; instead, uncover the deeper meaning, research trends, and potential research directions behind the paper. In non-leaf-level sections, introduce the sub-sections and their relationships, and provide a clear transition between them in a high-level perspective. Offered a new categorization or taxonomy to categorize the papers and provide a new perspective to think about the current research status.
- Provide a comprehensive analysis of the strengths and weaknesses of the current research. Support the analysis with sufficient technical results or experimental data so that it is not merely based on the author's subjective judgment but has a certain degree of objectivity. Make full use of various types of previously extracted information, including the main content, methods, results, conclusions, etc. of the paper, instead of analyzing only partial information. Detailed analysis and comparison have been conducted on each related paper with clear citations.
- Integrated and refined the challenges and problems faced in the current framework. Delve into the underlying reasons for the challenges and problems, rather than merely listing them. Find new problems and challenges based on the framework, and propose a new solution. The solution should be innovative and forward-looking, and the impact of the solution on the current challenges and problems should be analyzed. The solution should be specific and actionable, not just general statements. The solution should be innovative. You can put forward possible solutions by considering the adoption of methods from other fields or disciplines and by summarizing the successful methodologies in the history of your own discipline.
# Input Materials
## **Skeleton**: 
```markdown
{outline}
```

# Output Requirements
## Format requirements:
1. You need to analyse the **Skeleton** first in the rationale part, and then give the final score. In the Rationale part, you must clearly point out specific examples about the shortage of provided outline, analyse them and them give the score. If the score is not a full mark, the areas of deficiency need to be pointed out.
2. You need to evaluate from each perspective out of 10 and calculate the average of all scores at the end. The final score should be quoted by <SCORE> and </SCORE>. Do not place the calculation process and the upper limit of the score in the delimiter. You don't need to approximate the scores. Rigorously give your score.

## Format Example
Rationale: 
Please think step by step about all providing perspectives and provide the reason and amendment based on outline for giving the score. 

Final Score:
<SCORE>3</SCORE>
"""

ORCHESTRA_PROMPT = """You are a professional academic assistant specializing in literature reviews, helping researchers efficiently synthesize relevant research.
====================
Background:
Currently, you are engaged in writing an academic survey titled \"{title}\". Composing the entire survey in one go can be intricate, so our focus is on creating individual subsections. The outline for the survey has already been crafted, and each reference paper has been condensed into a concise digest. You need to follow the guidance in the outline description to analyze the content from the paper digests.
====================
Task Description:
YOUR TASK is to create a single subsection for the final survey. You will be provided with relevant content extracted from all individual digests. Your duty is to organize these materials into a coherent and well-structured subsection, strictly following the guidance provided in the sub-section description. As this is a leaf subsection, you should provide more detailed and specific content, including a comprehensive analysis of the research field based on the digests. Compare, contrast, and synthesize the insights from the digests to create a cohesive narrative. Ensure that the subsection is logically structured, with a clear flow of ideas and a systematic presentation of the content.

Think Principles:
1. **Integrate Individual Digests into a Cohesive Subsection**: 
- Systematic Organization Guided by Subsection Description: The sub-section description offers a detailed guide for analyzing content from paper digests, establishing a systematic framework for the current research field. You must adhere to this guidance to organize the digest content. Extract valuable information from the digests and synthesize it into a comprehensive survey subsection, ensuring that the final subsection encompasses all the insights from individual digests.
- Evidence-Based Analysis and Synthesis: Conduct detailed analysis and comparison of each relevant paper and explicitly contrasting and comparing the findings or methodologies of different studies in detail. Extract compelling evidence from the digests, such as experimental results, critical analyses, and profound insights, to support the analysis in the sub-section description. Add necessary transitional or explanatory sentences to ensure overall smoothness and coherence. Instead of merely listing digest content, clearly synthesize different viewpoints, compare and contrast findings, and provide a comprehensive analysis of the research field. It is encouraged to cite technical details or experimental results from the digests to support the analysis. Each claim requires sufficient evidence and argumentation. Engaging more critically with the strengths and weaknesses of the cited methodologies and findings, offering more original insights into the implications of these studies for the field. 
2. **Language Style**: 
- Formality, Rigor, and Objectivity: Maintain a high degree of formality, rigor, and objectivity throughout the writing. Eliminate colloquial expressions, casual wordings, and subjective viewpoints. The overall tone should reflect academic professionalism, presenting facts, analyses, and arguments precisely and clearly.
- Sentence Structure and Clarity: Construct sentences with rigor and accuracy, ensuring clear logic and easy comprehension. Avoid overly complex sentence structures and excessive listing of abbreviations in a single sentence. Each sentence should be unambiguous, fluent, and natural, with ideas progressing sequentially to prevent information overload and needless repetition.
- Neutrality, Precision, and Academic Rigor: Adopt a neutral tone and present content objectively based on evidence. Choose words precisely, discard colloquial language, and use rigorous academic terms. Diversify vocabulary to enhance the accuracy of expression. Every claim in the writing should be supported by relevant data or proper citations, strictly adhering to the standards of academic rigor.
====================
Input Materials:
Sub-Section Description:
```markdown
{outline}
```

Individual Paper Digests:
```markdown
{digest}
```

Sub-Section Description:
```markdown
{outline}
```
====================
Output Requirements:
1. The output section content must be quoted by one pair of ```markdown\\n```.
2. Each group of reference paper bibkeys must be enclosed within a pair of brackets. Cite specific papers' bibkey rather than using general terms like \"all papers\" or \"all sections\". Cite the papers that are mentioned in the descriptions of section description and paper digests, not the index themselves. If there are no suitable papers to cite in a description, write the sentences without any citation. Don't separately list all bibkeys, but integrate them into the content.
3. If the output contains a formula, use the LaTeX format to represent it. For example, the internal connection formula uses $y = x ^ 2 $, and the block formula uses $$y = x ^ 2 $$. Check the syntax correctness and parenthesis integrity of the formula to ensure that it can be rendered by KaTeX, and convert the expression involving other macropackages into the expression supported by KaTeX. 
4. Markdown tables are not allowed to be output in the content. 
====================
Format Example:
```markdown
{section_title}
The content of the sub-section, which is generated by integrating the relevant content from the individual digests and refining the overall presentation for clarity and coherence [\"BIBKEY1\", \"BIBKEY2\"].
```
Directly give a single section content without sub-section quoted by one pair of ```markdown\\n```.
"""

SUMMARY_PROMPT = """You are a professional academic assistant with expertise in literature reviews, dedicated to assisting researchers in efficiently synthesizing relevant research.
====================
Background:
At present, you are engaged in writing an academic survey titled \"{title}\". The outline for this survey has been established, and each reference paper has been condensed into a concise summary, highlighting the content most pertinent to the survey outline. You need to follow the guidance in outline description to analyse the content from paper digests. 
====================
Task Description:
**Your Task** is to write a guidance of its child sub-sections, relying on the provided section description and content of sub-sections. As this is a higher-level section, you should provide a more general overview of the content to be covered in the subsequent sub-sections. Build a specific theoretical framework based on the relevant Digest information provided, following the scheme described in the reference section. Ensure that the content is logically structured, with a clear flow of ideas and a systematic presentation of the content. 

Think Principles:
1. **Integrate Individual Digests into a Cohesive Subsection**: 
- Systematic Organization Guided by Section Description: The section description offers a detailed guide for analyzing content from paper digests, establishing a systematic framework for the current research field. You must adhere to this guidance to organize the digest content. Extract valuable information from the digests and synthesize it into a comprehensive survey subsection, ensuring that the final subsection encompasses all the insights from individual digests.
- Identifying Research Gaps and Future Directions: Systematically summarize the current challenges in the research field. Highlight limitations in existing studies, including sample size limitations, methodological constraints, or unaddressed research questions. Considering emerging trends and technological advancements in the field, propose specific and actionable potential areas for future research.
2. **Summary the Subsection contents into an Integrated Section**:
- Comprehensive Review and Core Identification: Thoroughly review the content of each sub-section. Systematically pinpoint the main themes, key arguments, and significant findings therein. For example, when one sub-section focuses on experimental methods and another on result interpretation, accurately distinguish the unique core elements of each. Refrain from merely restating the sub-section content; rather, extract its essence.
- Discovering and Leveraging Connections: Seek out common threads and interconnections among sub-sections. These could include shared research methodologies, related theoretical frameworks, or overlapping research inquiries. Harness these connections as the basis for integrating sub-section contents. For instance, if multiple sub-sections explore the impact of a particular variable on the research subject, accentuate this common variable and its diverse manifestations across different sub-sections.
- Structuring for Clarity: When integrating sub-section contents, establish a hierarchical structure. Present the most general and overarching concepts first, followed by more specific details. This approach ensures a clear and logical flow throughout the entire section. Commence with a broad overview of the research area covered by the sub-sections, and then gradually proceed to the in-depth findings and analyses of each sub-section.
- Meaningful Synthesis over Simple Compilation: Ensure that the integration of sub-section contents is a meaningful synthesis rather than a mere compilation. Provide a narrative that clarifies how each sub-section contributes to the overall understanding of the topic. In cases where one sub-section challenges the findings of another, discuss the implications of this contradiction and propose potential solutions or directions for further exploration in future research. This should also involve identifying the main challenges in the current section and suggesting possible remedies, all within the framework of the integrated analysis.
3. **Language Style**: 
- Formality, Rigor, and Objectivity: Maintain a high degree of formality, rigor, and objectivity throughout the writing. Eliminate colloquial expressions, casual wordings, and subjective viewpoints. The overall tone should reflect academic professionalism, presenting facts, analyses, and arguments precisely and clearly.
- Sentence Structure and Clarity: Construct sentences with rigor and accuracy, ensuring clear logic and easy comprehension. Avoid overly complex sentence structures and excessive listing of abbreviations in a single sentence. Each sentence should be unambiguous, fluent, and natural, with ideas progressing sequentially to prevent information overload and needless repetition.
- Neutrality, Precision, and Academic Rigor: Adopt a neutral tone and present content objectively based on evidence. Choose words precisely, discard colloquial language, and use rigorous academic terms. Diversify vocabulary to enhance the accuracy of expression. Every claim in the writing should be supported by relevant data or proper citations, strictly adhering to the standards of academic rigor.
====================
Input Materials:
Section Description:
```markdown
{outline}
```

Subsections:
{subcontents}

Individual Paper Digests:
```markdown
{digest}
```

Section Description:
```markdown
{outline}
```
====================
Output Requirements:
1. The output section content must be quoted by one pair of ```markdown\\n```.
2. Each group of reference paper bibkeys must be enclosed within a pair of brackets. Cite specific papers' bibkey rather than using general terms like \"all papers\" or \"all sections\". Cite the papers that are mentioned in the descriptions of section description and paper digests, not the index themselves. If there are no suitable papers to cite in a description, write the sentences without any citation. Don't separately list all bibkeys, but integrate them into the content.
3. If the output contains a formula, use the LaTeX format to represent it. For example, the internal connection formula uses $y = x ^ 2 $, and the block formula uses $$y = x ^ 2 $$. Check the syntax correctness and parenthesis integrity of the formula to ensure that it can be rendered by KaTeX, and convert the expression involving other macropackages into the expression supported by KaTeX. 
4. Markdown tables are not allowed to be output in the content.
====================
Format Example:
```markdown
{section_title}
The content of the father section, which is generated by integrating the relevant content from the individual digests and refining the overall presentation for clarity and coherence [\"BIBKEY1\", \"BIBKEY2\"].
```
Directly give a single section content without sub-section quoted by one pair of ```markdown\\n```.
"""

POLISH_PROMPT = """[Task Description] 
1. Convert multiple consecutive references to this form: [\"BIBKEY1\", \"BIBKEY2\"]. 
2. Check the syntax correctness and parenthesis integrity of the formula to ensure that it can be rendered by KaTeX, and convert the expressions involving other macro packages into expressions supported by KaTeX.

[Content]
{content}

[Output Requirements]
The polished content should be quoted by ```markdown\\n```.
"""

CHART_PROMPT = """[Task Description]
Analyze the entire content of the Survey. Create multiple Markdown tables or Mermaid charts to effectively convey information. You need to meet the following requirements:
1. Prioritize the reader’s viewing experience; ensure a proper balance between the width and length of each chart or table. 
2. Select precise and comprehensible keywords to summarize each corresponding section.
3. Select suitable chart type to illustrate the information of corresponding section. 
4. A section can use one or two diagrams, and not every section needs to be represented by diagrams. The positions of the diagrams need to be different and evenly distributed in different parts of the article to help readers better understand the article. Only one diagram is allowed in one position.
5. Each chart must have one core idea to connect all parts together. If each component of one chart is not related to the core idea, it should be split into multiple charts with the same title.

[Full Content]
{content}

[Output Requirements]
The chart should include the following information: 
1. The Section Title. The title of the section that the chart belongs to. This figure will be placed in this section.
2. The Position Sentence. Repeat the sentence that is most relevant to the chart. This figure will be placed before the sentence.
3. The figure title, summarise the main content of this figure.
4. The Mermaid code quoted by ```mermaid\\n```. 
- Strict adherence to Mermaid grammar.
- Each node label must be quoted by \"\", with suitable form of brackets.
5. The Markdown code quoted by ```markdown\\n```.

[Output Format]
Section Title: <Section title without index>
Position Sentence: <Position Sentence without index>
Figure Title: <Position Sentence without index>
```mermaid
Code to paint the chart
```

Section Title: <Section title without index>
Position Sentence: <Position Sentence without index>
Figure Title: <Position Sentence without index>
```markdown
Content to paint the table
```

Section Title: <Section title without index>
Position Sentence: <Position Sentence without index>
Figure Title: <Position Sentence without index>
```mermaid
Code to paint the chart
```
"""


RESIDUAL_MODIFY_OUTLINE_PROMPT = """You are a professional academic assistant tasked with helping researchers conduct literature reviews based on provided materials.

# Background
I am required to write an academic survey outline about topic \"{title}\" based on the provided **Initial Skeleton**. These outlines, which are organized according to different reference paper abstracts, offer diverse perspectives on the topic. 

# Task Description
Based on provided outline initial outline and modify suggestions, you need to write a new version outline. You must cite suggestion citations in corresponding modified section descriptions.

# Input Materials
## **Initial Skeleton**
```markdown
{old_outline}
```

## **Modify Suggestions**
{outlines}

# Output Requirements
## Format Requirements
1. The output **New Skeleton** must be in markdown format, with the topic as the first-level heading, the title number being Arabic numerals, and multi-level headings connected by a period. The **New Skeleton** should enclose with delimiters ```markdown\\n```.
2. Each outline section should have a systematic and detailed description. The description should revolve around the section title, extract the generality from the provided papers
3. Each section description should cite appropriate paper bibkeys. If you believe that the content of a particular section can draw on certain abstracts, you should include the corresponding bibkeys at the end of the sentence.
4. Each section can contain sub-sections, and it is recommended to use markdown headings to represent the hierarchical structure.
5. Each group of reference papers bibkeys must be enclosed in a pair of brackets. You must cite those bibkeys in initial outline and modify suggestions. Don't directly cite \"initial outline\" and \"suggestion n\". When citing multiple bibkeys, enclose them in a pair of brackets. You must cite specific papers instead of some kind of general term, such as \"all papers\", \"all sections\", etc. If no suitable paper is provided, you could not add new citation. Multiple citation bibkeys should be in a pair of brackets.

## Format Example
Rationale:
Elaborate on your thoughts on the survey and how to implement all suggestions in new outline.

New Skeleton:
```markdown
# {title}
## 1. Section A
Write some detailed descriptions with citation bibkey about what content should be described in this section [BIBKEY1, BIBKEY2].
## 2. Section B
Write some detailed descriptions with citation bibkey about what content should be described in this section [BIBKEY1, BIBKEY2].
### 2.1 Subsection B1
Write some detailed descriptions with citation bibkey about what content should be described in this section [BIBKEY1, BIBKEY2].
### 2.2 Subsection B2
Write some detailed descriptions with citation bibkey about what content should be described in this section [BIBKEY1, BIBKEY2].
#### 2.2.1 Subsubsection B2.1
Write some detailed descriptions with citation bibkey about what content should be described in this section [BIBKEY1, BIBKEY2].
## 3. Section C
Write some detailed descriptions with citation bibkey about what content should be described in this section [BIBKEY1, BIBKEY2].
```
"""

# LLM_search prompts
QUERY_EXPAND_PROMPT_WITH_ABSTRACT = """You are an industry research expert tasked with writing a comprehensive report on the topic of {topic}. The report should adhere to the following requirements: {abstract}. To gather the necessary information, you will need to conduct online research. Please generate a set of search queries that will help you retrieve relevant data and insights for your report. Break down vague concepts in the current query into more specific subconcepts for more precise searches. For example, "foreign" can be further broken down into specific countries or regions that are representative within the reporting domain. The output queries must be quoted by ```markdown\\n```.

Output Format:
```markdown
query_content;
query_content;
```
"""

QUERY_EXPAND_PROMPT_WITHOUT_ABSTRACT = """You are an industry research expert tasked with writing a comprehensive report on the topic of {topic}. To gather the necessary information, you will need to conduct online research. Please generate a set of search queries that will help you retrieve relevant data and insights for your report. Break down vague concepts in the current query into more specific subconcepts for more precise searches. For example, "foreign" can be further broken down into specific countries or regions that are representative within the reporting domain. The output queries must be quoted by ```markdown\\n```.

Output Format:
```markdown
query_content;
query_content;
```
"""

QUERY_REFINE_STOP_FLAG = "No modifications needed"

USER_CHECK_PROMPT = """The queries you have decomposed are: {queries}\n{user_comment}\nPlease return only the queries, separated by commas, as a simple string. Do not include any additional text or explanations.
"""
LLM_CHECK_PROMPT = """The queries you have decomposed are: {queries}\nPlease rigorously review the output queries to ensure each one is closely related to the report's topic, covers non-overlapping domains, and can be further broken down into specific technologies, companies, or experts relevant to the industry. If any queries fail to meet these criteria, provide your analysis and suggest modifications. Retain queries that are already appropriate without deletion.\n\nIf modifications are needed, format your response as follows:\n\n"AI's assessment: ...\nThis round's output queries: query_1,query_2,...,query_n"\n\nWhere "This round's output queries:" is followed by the revised queries.\n\nIf no modifications are necessary, format your response as follows:\n\n"AI's assessment: No modifications needed.\nThis round's output queries: query_1,query_2,...,query_n"\n\nWhere "This round's output queries:" is followed by the unaltered queries.
"""

SNIPPET_FILTER_PROMPT="""Please infer the degree of relevance between this web page and the topic based on the following topic and the web page snippet retrieved from the Internet.

Topic: {topic}
Web page snippet: {snippet}

Please comprehensively consider the above two dimensions. First, provide the reason for the score, and then give the score. The scoring range is from 0 to 100. 0 means completely irrelevant, and 100 means completely relevant. Please be as strict as possible when scoring.

Note that the score needs to be enclosed in <SCORE></SCORE>. For example, <SCORE>78</SCORE>

Example response:
Reason:...
Similarity score: <SCORE>89</SCORE> 
"""

# crawl4ai prompts
PAGE_REFINE_PROMPT = """Analyze and process the following web page content related to '{topic}'. Output the main body text, removing image links, website URLs, advertisements, meaningless repeated characters, etc. Summarization of the content is prohibited, and all information related to the topic should be retained.

Original web page content:
{raw_content}

[Output requirements]
- Title: <TITLE>Your title</TITLE>
- Filtered text: <CONTENT>Filtered text</CONTENT> 
"""

SIMILARITY_PROMPT = """Evaluate the quality of the following content retrieved from the internet based on the given topic, and give a suitable title about the content. Provide a critical and strict assessment.

Topic: {topic}  
Content: {content}  

Evaluate the content based on the following dimensions:  

1. **Relevance to the topic**: Assess whether the content can be considered a subset or expansion of the topic.  
2. **Usability for writing about the topic**: Consider factors such as text length (e.g., very short texts have lower reference value), presence of garbled characters, and overall text quality.  

Provide a rationale for your evaluation before assigning scores. Score each dimension on a scale of 0-100, where 0 indicates no relevance and 100 indicates perfect relevance. Calculate the final average score after scoring each dimension.  

Enclose the scores in `<SCORE></SCORE>` tags. For example: `<SCORE>78</SCORE>` 
Enclose the title in `<TITLE></TITLE>` tags. For example: `<TITLE>Title</TITLE>` 

Example response:  
Rationale: ...  
Relevance score: <SCORE>89</SCORE>
Title: <TITLE>Title</TITLE>
"""
