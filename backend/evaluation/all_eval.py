import os
import logging
import json
from concurrent import futures
from tqdm import tqdm
import pandas as pd

from evaluation.args import parse_args
from evaluation.agents.judge import Judge
from evaluation.agents.atomic_facts import extract_and_deduplicate_facts

logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)

def evaluate(jsonl_file, eval_model, infer_type, skip_titles, skip_line_number=0):
    def eval_single_survey(judge, survey, topic, outline, papers):
        print(f"Start evaluating additional dimensions")
        dimension_scores = judge.evaluate_all_dimensions(survey, topic)

        print(f"Start batch_criteria_based_judging")
        criterion = ["Structure", "Relevance"]
        scores = judge.batch_criteria_based_judging(survey, topic, criterion)

        print(f"Start citation_quality")
        result_dict = judge.citation_quality_new(survey, papers)
        print(f"Finished evaluating survey title:{topic}")

        print(f"Start claim evaluation")
        fact_stats = extract_and_deduplicate_facts(survey, topic)
        
        result = {
            "name": topic,
            "language_score": float(dimension_scores["language_score"]),
            "critical_score": float(dimension_scores["critical_score"]),
            "structure": float(scores[0])* 20,
            "relevance": float(scores[1]) * 20,
            "claim_precision": result_dict['claim_precision'] * 100, # Faithfulness
            "citation_precision": result_dict['citation_precision'] * 100,
            "reference_precision": result_dict['reference_precision'] * 100,
            "reference_coverage": result_dict['reference_coverage'],
            "claims_before_dedup": float(fact_stats["claims_before_dedup"]),
            "claims_after_dedup": float(fact_stats["claims_after_dedup"]),
            "compression_ratio": float(fact_stats["compression_ratio"]),
        }
        return result

    judge = Judge(jsonl_file, eval_model, infer_type)
    result = []

    logger.info(f"evaluating survey..")
    logger.info(f"reading jsonl file: {jsonl_file}")
    with open(jsonl_file, "r") as f:
        with futures.ThreadPoolExecutor(5) as executor:
            future_to_eval = {}
            for line_number, line in enumerate(f, start=1):
                logger.info(f"line_number={line_number}")
                if line_number <= skip_line_number:
                    logger.info(f"skip line {line_number}")
                    continue
                data = json.loads(line.strip())
                topic = data["title"]
                papers = data["papers"]
                references = {i: paper["title"] for i, paper in enumerate(papers)}
                outline = data["outline"]
                survey = data["content"]

                logger.info(f"Start to evaluate {topic}")

                if survey is None or references is None:
                    print(f"File for topic '{topic}' not found. Skipping...")
                    continue

                if topic in skip_titles:
                    print(f"Topic '{topic}' already evaluated. Skipping...")
                    continue

                future = executor.submit(
                    eval_single_survey, judge, survey, topic, outline, papers
                )
                future_to_eval[future] = topic

            for future in tqdm(futures.as_completed(future_to_eval), total=len(future_to_eval), desc="Evaluating Surveys:"):
                topic = future_to_eval[future]
                try:
                    result.append(future.result())
                except Exception as e:
                    print(f"{topic} generated an exception: {e}, {future.result()}")
    result = pd.DataFrame(result)
    return result


def save_or_update_scores(args, scores, content_score):
    if content_score is not None:
        merged_scores = content_score

        columns_to_extract = scores.columns.tolist()
        merged_scores_extracted = merged_scores.reindex(columns=columns_to_extract)

        scores.set_index("name", inplace=True)
        merged_scores_extracted.set_index("name", inplace=True)
        combined_scores = pd.concat([scores, merged_scores_extracted], axis=0)
        scores = combined_scores.groupby(combined_scores.index).last().reset_index()
    else:
        scores.set_index("name", inplace=True)

    output_file = os.path.join(args.saving_path, "result.csv")
    scores.to_csv(output_file, index=False)

    avg_output_file = os.path.join(args.saving_path, "final.csv")
    scores = scores.astype({col: "float" for col in scores.select_dtypes(include="int").columns})
    avg_scores = scores.mean(numeric_only=True)
    avg_scores["name"] = args.method_name

    try:
        avg_scores_df = pd.read_csv(avg_output_file)
    except FileNotFoundError:
        avg_scores_df = pd.DataFrame(columns=scores.columns.tolist())

    if args.method_name in avg_scores_df["name"].values:
        avg_scores_df.loc[avg_scores_df["name"] == args.method_name, avg_scores.index] = avg_scores
    else:
        avg_scores_df = pd.concat([avg_scores_df, pd.DataFrame([avg_scores])], ignore_index=True)

    avg_scores_df.to_csv(avg_output_file, index=False)
    print(f"Evaluation results saved to {output_file}")
    print(f"Average scores saved to {avg_output_file}")


if __name__ == "__main__":
    args = parse_args()
    if not os.path.exists(args.saving_path):
        os.mkdir(args.saving_path)

    print(args)
    output_file = os.path.join(args.saving_path, f"{args.method_name}.csv")
    avg_output_file = os.path.join(args.saving_path, "total.csv")

    columns = [
        "name",
        "language_score",
        "critical_score",
        "structure",
        "relevance",
        "claim_precision",
        "citation_precision",
        "reference_precision",
        "reference_coverage",
        "claims_before_dedup",
        "claims_after_dedup",
    ]

    try:
        scores = pd.read_csv(output_file)
    except:
        scores = pd.DataFrame(columns=columns)

    titles = scores["name"].values
    if os.path.exists(output_file):
        logger.info("Reading existing scores...")
        scores = pd.read_csv(output_file)
    else:
        scores = pd.DataFrame(columns=columns)

    content_score = evaluate(
        args.jsonl_file, args.eval_model, args.infer_type, titles
    )
    logger.info(content_score)
    save_or_update_scores(args, scores, content_score)
    logger.info("Finish eval")
