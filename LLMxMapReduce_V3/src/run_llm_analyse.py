#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import sys
import os
import json
import logging
from pathlib import Path
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def run_llm_analyse(topic: str, description: str = None):
    """Run LLMHost analyse process"""
    print("🚀 Starting LLMHost Intelligent Analysis Process")
    print("=" * 70)

    try:
        from src.search.analyse_llm_host import AnalyseLLMHostInterface

        # Create analysis interface
        base_dir = f"output/{datetime.now().strftime('%Y%m%d')}/{topic}/search"
        analyser = AnalyseLLMHostInterface(base_dir=base_dir)

        print(f"📁 Working Directory: {base_dir}")
        print(f"🎯 Research Topic: {topic}")
        if description:
            print(f"📝 Topic Description: {description}")

        print(f"\n🔧 System Configuration:")
        print(f"  - Configuration File: config/unified_config.json")
        print(f"  - Model: {analyser.env_config.get('models', {}).get('default_model', 'N/A')}")
        print(f"  - Max Interaction Rounds: {analyser.env_config.get('analyse_settings', {}).get('max_interaction_rounds', 'N/A')}")
        print(f"  - LLM Host Max Rounds: {analyser.env_config.get('analyse_settings', {}).get('llm_host_max_rounds', 'N/A')}")

        try:
            print(f"\n🔄 Starting Analysis Process...")
            print(f"📊 Process Overview:")
            print(f"  Phase 1: Topic Expansion (LLM-based)")
            print(f"  Phase 2: Intelligent Tool Selection & Execution")
            print(f"  Phase 3: Literature Search & Content Crawling")
            print(f"  Phase 4: Result Processing & Saving")

            start_time = datetime.now()

            # Execute analysis
            print(f"\n⏳ Executing analysis pipeline...")
            result = await analyser.analyse(topic, description)

            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            print(f"\n✅ Analysis Process Completed! Duration: {duration:.1f} seconds")
            print("=" * 70)
            
            # Display detailed results
            print("📊 Analysis Results Summary:")
            print(f"  - Status: {result.get('status', 'unknown')}")
            print(f"  - Rounds Used: {result.get('rounds_used', 0)}")

            # Display operation history with detailed breakdown
            operation_history = result.get('operation_history', [])
            print(f"  - Operation History: {len(operation_history)} operations")

            tool_calls = []
            search_results_count = 0
            url_processed_count = 0

            print(f"\n🔍 Detailed Operation Breakdown:")
            for i, op in enumerate(operation_history):
                action = op.get('action', 'unknown')
                if action == 'call_tool':
                    tool_name = op.get('tool_name', 'unknown')
                    tool_calls.append(tool_name)
                    print(f"    Step {i+1}: Tool Execution - {tool_name}")

                    # Check tool results with detailed analysis
                    tool_result = op.get('result', {})
                    if isinstance(tool_result, dict):
                        if 'final_results' in tool_result:
                            final_count = len(tool_result.get('final_results', []))
                            if final_count > 0:
                                search_results_count += final_count
                                print(f"       📊 Literature Results: {final_count} papers")
                        elif 'total_urls' in tool_result:
                            url_count = tool_result.get('total_urls', 0)
                            url_processed_count += url_count
                            print(f"       📊 URLs Processed: {url_count} links")
                        elif 'queries_generated' in tool_result:
                            query_count = tool_result.get('queries_generated', 0)
                            print(f"       📊 Search Queries Generated: {query_count} queries")
                        elif 'error' in tool_result:
                            print(f"       ❌ Tool Error: {tool_result.get('error', 'unknown')}")
                        else:
                            print(f"       ✅ Tool executed successfully")
                elif action == 'request_info':
                    message = op.get('message', '')
                    print(f"    Step {i+1}: Information Request - {message}")
                elif action == 'complete':
                    result_msg = op.get('result', '')
                    print(f"    Step {i+1}: Task Completion - {result_msg[:100]}...")
                elif action == 'error':
                    error = op.get('error', '')
                    print(f"    Step {i+1}: Error Occurred - {error}")
            
            # Tool usage statistics with performance metrics
            print(f"\n🔧 Tool Usage Statistics:")
            tool_counts = {}
            for tool in tool_calls:
                tool_counts[tool] = tool_counts.get(tool, 0) + 1

            if tool_counts:
                for tool, count in tool_counts.items():
                    print(f"  - {tool}: {count} execution(s)")
                print(f"  - Total Tool Calls: {len(tool_calls)}")
            else:
                print(f"  - No tools were executed")

            # Comprehensive search results analysis
            print(f"\n📚 Literature Search Results:")
            if search_results_count > 0:
                print(f"  - Total Literature Found: {search_results_count} papers")
                print(f"  - URLs Processed: {url_processed_count} links")
                print(f"  - Success Rate: {(search_results_count/max(url_processed_count, 1)*100):.1f}%")
            else:
                print(f"  - No literature results obtained")
                if url_processed_count > 0:
                    print(f"  - URLs were processed ({url_processed_count}) but no valid results")
                else:
                    print(f"  - No URLs were processed")

            # Final result analysis
            final_result = result.get('result', '')
            if final_result:
                print(f"\n📋 Final Analysis Result:")
                print(f"  {final_result[:400]}...")
                if len(final_result) > 400:
                    print(f"  ... (truncated, full result saved to file)")

            # Performance metrics
            print(f"\n⚡ Performance Metrics:")
            print(f"  - Total Processing Time: {duration:.2f} seconds")
            print(f"  - Average Time per Round: {duration/max(result.get('rounds_used', 1), 1):.2f} seconds")
            if search_results_count > 0:
                print(f"  - Time per Literature Result: {duration/search_results_count:.2f} seconds")

            # Save results to file with enhanced metadata
            result_file = f"{base_dir}/{topic}_search_result.json"
            os.makedirs(base_dir, exist_ok=True)

            # Add metadata to result
            enhanced_result = {
                **result,
                "metadata": {
                    "topic": topic,
                    "description": description,
                    "processing_time": duration,
                    "timestamp": datetime.now().isoformat(),
                    "tool_statistics": tool_counts,
                    "literature_count": search_results_count,
                    "urls_processed": url_processed_count
                }
            }

            with open(result_file, 'a', encoding='utf-8') as f:
                json.dump(enhanced_result, f, ensure_ascii=False, indent=2)
            print(f"\n💾 Results Saved to: {result_file}")

            return result
            
        finally:
            await analyser.cleanup()
            
    except Exception as e:
        print(f"\n❌ Analysis Process Failed: {e}")
        import traceback
        traceback.print_exc()
        return None

async def run_simple_llm_host_test(task: str):
    """Run simple LLMHost test"""
    print("\n🧪 Running Simple LLMHost Test")
    print("=" * 60)

    try:
        from src.search.llm_host import LLMHost

        async with LLMHost() as host:
            print("✅ LLMHost Connection Successful")
            print(f"📋 Available Tools: {len(host.available_tools)} tools")

            print(f"🎯 Test Task: {task}")

            start_time = datetime.now()
            result = await host.process_task(task, "This is a test task")
            end_time = datetime.now()

            duration = (end_time - start_time).total_seconds()

            print(f"\n✅ Task Completed! Duration: {duration:.1f} seconds")
            print(f"  - Status: {result.get('status', 'unknown')}")
            print(f"  - Rounds Used: {result.get('rounds_used', 0)}")
            print(f"  - Operations: {len(result.get('operation_history', []))}")

            return result

    except Exception as e:
        print(f"\n❌ LLMHost Test Failed: {e}")
        import traceback
        traceback.print_exc()
        return None

def print_usage():
    """Print usage instructions"""
    print("🔧 LLMHost Analysis Process Runner")
    print("=" * 60)
    print("Usage:")
    print("  python run_llm_analyse.py <topic> [description]")
    print("  python run_llm_analyse.py --test <simple_task>")
    print("")
    print("Examples:")
    print("  python run_llm_analyse.py \"Machine Learning Optimization\"")
    print("  python run_llm_analyse.py \"Deep Learning\" \"Neural Network Fundamentals\"")
    print("  python run_llm_analyse.py --test \"Test Tool Calling\"")
    print("")
    print("Features:")
    print("  - Complete analysis pipeline: Topic expansion + Intelligent tool selection")
    print("  - LLM autonomous decision-making for search, crawling, and other tools")
    print("  - Detailed process logging and result statistics")
    print("  - Enhanced performance metrics and error handling")
    print("  - Unified configuration management")

async def main():
    if len(sys.argv) < 2:
        print_usage()
        return 1

    if sys.argv[1] == "--test":
        if len(sys.argv) < 3:
            task = "Test LLMHost Basic Functionality"
        else:
            task = sys.argv[2]

        result = await run_simple_llm_host_test(task)
        return 0 if result else 1

    # Parse arguments
    topic = None
    description = None

    i = 1
    while i < len(sys.argv):
        if sys.argv[i] == "--topic" and i + 1 < len(sys.argv):
            topic = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == "--description" and i + 1 < len(sys.argv):
            description = sys.argv[i + 1]
            i += 2
        else:
            # If no flags, treat as positional arguments
            if topic is None:
                topic = sys.argv[i]
            elif description is None:
                description = sys.argv[i]
            i += 1

    if topic is None:
        print("❌ Error: Topic is required")
        print_usage()
        return 1

    result = await run_llm_analyse(topic, description)

    if result:
        status = result.get('status', 'unknown')
        if status in ['completed', 'max_rounds_reached']:
            print(f"\n🎉 Process Completed Successfully!")
            return 0
        else:
            print(f"\n⚠️ Process Not Fully Successful, Status: {status}")
            return 1
    else:
        print(f"\n❌ Process Failed")
        return 1

if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n⏹️ Process Interrupted by User")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Error Occurred During Execution: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
