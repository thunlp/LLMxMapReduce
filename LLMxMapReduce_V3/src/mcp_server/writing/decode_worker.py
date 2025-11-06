import gevent.monkey
gevent.monkey.patch_all() 

import os
import sys
import json
import gevent
from gevent import sleep
from src.data_structure.survey import Survey
from multiprocessing.connection import Connection
from src.mcp_server.writing.decode_pipeline import DecodePipeline, setup_logger
import datetime

log_dir = os.path.join(os.path.dirname(__file__), f'../../../output/{datetime.datetime.now().strftime("%Y%m%d")}/logs')
os.makedirs(log_dir, exist_ok=True)
logger = setup_logger(os.path.join(log_dir, 'decode_worker.log'))
logger.info("🟢 Decode worker started")


def run_decode_pipeline(conn: Connection, config, output_file):
    logger.info("Initializing DecodePipeline...")
    decode_pipeline = DecodePipeline(config=config, output_file=output_file)
    logger.info("DecodePipeline initialized, starting async...")
    # g = gevent.spawn(decode_pipeline.start())
    decode_pipeline.start()

    stop_signal = False
    while not stop_signal:
        if conn.poll(0.1):
            msg = conn.recv()
            logger.info(f"Received message: {str(msg)[:1000]}")
            if msg.get("cmd") == "put":
                survey = Survey.from_json(msg["survey"])
                decode_pipeline.put(survey)
                logger.info(f"Put the message into decode pipeline.")
            elif msg.get("cmd") == "stop":
                logger.info("Received stop signal.")
                stop_signal = True

        if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
            logger.info(f"Output file ready: {output_file}")
            conn.send({"status": "finished", "file": output_file})
            stop_signal = True

        sleep(1)

    logger.info("Stopping decode pipeline...")
    conn.close()

if __name__ == "__main__":
    args = json.loads(sys.stdin.read())
    config = args["config"]
    output_file = args["output_file"]
    parent_fd = args["fd"]
    conn = Connection(parent_fd)

    logger.info(f"Output file: {output_file}")
    run_decode_pipeline(conn, config, output_file)
 