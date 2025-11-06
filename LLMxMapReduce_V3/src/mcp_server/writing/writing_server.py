import multiprocessing
import json
import os
import sys
import traceback
import logging
import asyncio
from typing import List

from mcp.server import Server
from mcp.types import Resource, Tool, TextContent
import mcp.server.stdio
import datetime
from src.data_structure.survey import Survey

log_dir = os.path.join(os.path.dirname(__file__), f'../../../output/{datetime.datetime.now().strftime("%Y%m%d")}/logs')
os.makedirs(log_dir, exist_ok=True)
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(log_dir, 'digest_server.log'), encoding='utf-8'),
        logging.StreamHandler(sys.stderr)
    ]
)
logger = logging.getLogger(__name__)

class DecodeServer:
    def __init__(self):
        self.worker_process = None
        self.conn = None

    async def decode_generation(self, config: dict, output_file: str, survey: dict):
        if self.worker_process is None:
            parent_conn, child_conn = multiprocessing.Pipe()
            self.conn = parent_conn

            self.worker_process = multiprocessing.Process(
                target=self._start_worker,
                args=(child_conn, config, output_file),
                daemon=False,
            )
            self.worker_process.start()
            logger.info(f"Decode worker process started. PID={self.worker_process.pid}")

        self.conn.send({"cmd": "put", "survey": survey})
        logger.info("Sent survey to decode worker.")

        while True:
            await asyncio.sleep(1)
            if self.conn.poll():
                msg = self.conn.recv()
                logger.info(f"Decode worker message: {msg}")
                if msg.get("status") == "finished":
                    return {"status": "ok", "file": msg["file"]}

    def _start_worker(self, conn, config, output_file):
        import os, sys
        print(f">>> child _start_worker pid={os.getpid()} cwd={os.getcwd()}", flush=True)
        sys.stdout.flush()

        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
        if project_root not in sys.path:
            sys.path.insert(0, project_root)

        try:
            from src.mcp_server.writing.decode_worker import run_decode_pipeline
        except Exception:
            print("Failed to import decode_worker:", flush=True)
            import traceback as _tb
            _tb.print_exc()
            raise

        logger.info("Starting decode pipeline in worker...")
        run_decode_pipeline(conn, config, output_file)

def _output_to_md(output_file):
    output_dir = os.path.dirname(output_file)

    with open(output_file, "r") as f:
        for line in f:
            data = json.loads(line)
            content = data["content"]
            content += "\n\n" + data["ref_str"]
            with open(os.path.join(output_dir, data["title"] + ".md") , "w") as out:
                out.write(content)

def create_and_run_app():
    app = Server("writing-processor")

    @app.list_resources()
    async def list_resources() -> List[Resource]:
        return [
            Resource(
                uri="writing://processor/prompts",
                name="writing Processing Prompts",
                description="Writing prompt template for writing the whole survey",
                mimeType="application/json"
            )
        ]

    @app.read_resource()
    async def read_resource(uri: str) -> str:
        if uri == "writing://processor/prompts":
            prompts = {"writing": "Start writing according to skeleton."}
            return json.dumps(prompts, ensure_ascii=False, indent=2)
        else:
            raise ValueError(f"Unknown resource: {uri}")

    @app.list_tools()
    async def list_tools() -> List[Tool]:
        return [
            Tool(
                name="writing",
                description="Start writing according to given skeleton.",
                inputSchema={
                "type": "object",
                "properties": {
                    "survey": {
                        "type": "string",
                        "description": "A JSON string containing the complete structured data of the initialized literature survey. This string must be a valid JSON representation of a comprehensive dictionary that holds all context for digest generation. The data structure includes:\n- \"title\": The title of the literature survey.\n- \"skeleton\": The hierarchical, initialized outline (skeleton).\n- \"papers\": The reference papers.\n- \"digests\": A list linking group/category names to lists of reference objects and the digests for each paper.\nInstruction: The server will use the content to analyze the survey_outline and individual paper abstract to write application-focused digests for each reference.",
                    },
                    "config": {"type": "object", "description": "Model config used in digest generation."},
                    "output_file": {
                        "type": "string",
                        "description": "The file path of final survey."
                    }
                },
                "required": ["survey", "config", "output_file"]
            }
            )
        ]

    @app.call_tool()
    async def call_tool(tool_name: str, params_dict: str):
        survey = params_dict["survey"]
        config = params_dict["config"]
        output_file = params_dict["output_file"]

        try:
            decode_server = DecodeServer()
            result = await decode_server.decode_generation(config['decode'], output_file, survey)
            _output_to_md(output_file)

            # return result
        except Exception as e:
            return [TextContent(type="text", text=f"Error calling tool {tool_name}: {e}\n\nTraceback\n{traceback.format_exc()}")]

    async def run():
        logger.info("Starting Writing MCP Server...")
        async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
            await app.run(read_stream, write_stream, app.create_initialization_options())

    asyncio.run(run())

if __name__ == "__main__":
    multiprocessing.set_start_method("spawn", force=True)
    create_and_run_app()
