import argparse

def parse_args():
    parser = argparse.ArgumentParser(
        description="Run the EntirePipeline with specified input, output, and prompt files.")
    
    parser.add_argument("--topic", type=str, help="Your research topic")
    parser.add_argument("--description", type=str, help="Description about your research topic. It will be used to retrieve pages.")
    parser.add_argument("--top_n", type=int, default=100, help="Number of top n references to retrieve")
    
    parser.add_argument("--input_file", type=str, help="Path to the input file")
    parser.add_argument("--output_file", type=str, required=True, help="Path to the output file")
    parser.add_argument("--config_file", type=str, default='config\model_config.json', help="Path to the config json file")
    
    parser.add_argument("--data_num", type=int, default=None, help="Number of data to process") 
    parser.add_argument("--parallel_num", type=int, default=1, help="Number of data to process concurrently in pipeline")
    
    parser.add_argument("--digest_group_mode", type=str, choices=["random", "llm"], default="llm", help="Group paper to digest mode")
    parser.add_argument("--skeleton_group_size", type=int, default=2, help="Number of digest to generate a skeleton")
    
    parser.add_argument("--block_count", type=int, default=0, help="Number of max iteration blocks")
    parser.add_argument("--output_each_block", type=bool, default=False, help="Whether to output each block")
    
    parser.add_argument("--conv_layer", type=int, default=6, help="Number of convolution layer, only mcts need.")
    parser.add_argument("--conv_kernel_width", type=int, default=3, help="Receptive field of convolution layer, how many old suggestion to generate new suggestion")
    parser.add_argument("--conv_result_num", type=int, default=10, help="Number of suggestion to generate in each convolution layer")
    parser.add_argument("--top_k", type=int, default=6, help="Number of top k suggestion that will be kept in mcts")
    
    parser.add_argument("--self_refine_count", type=int, default=3, help="Number of self-refine cycle")
    parser.add_argument("--self_refine_best_of", type=int, default=3, help="Number of result number in each cycle")
    args = parser.parse_args()
    return args
