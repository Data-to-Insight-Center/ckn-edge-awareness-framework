import json
import logging
import os
import sys
import time
from datetime import datetime

from confluent_kafka import Producer
from confluent_kafka.admin import AdminClient

CKN_LOG_FILE = os.getenv('CKN_LOG_FILE', 'ckn_example.log')
KAFKA_BROKER = os.getenv('CKN_KAFKA_BROKER', 'broker:29092')
KAFKA_TOPIC = os.getenv('CKN_KAFKA_TOPIC', 'oracle-events')

def setup_logging():
    """
    Logs to both console and file.
    :return:
    """
    log_formatter = logging.Formatter('%(asctime)s - %(message)s')

    # Create the root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    # Logs all INFO, DEBUG and ERROR to the CKN_LOG_FILE
    file_handler = logging.FileHandler(CKN_LOG_FILE)
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(log_formatter)
    root_logger.addHandler(file_handler)

    # Logs INFO and ERROR to stdout
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(log_formatter)
    root_logger.addHandler(console_handler)

def test_ckn_broker_connection(bootstrap_servers, timeout=10, num_tries=5):
    """
    Checks if the CKN broker is up and running.
    :param bootstrap_servers: CKN broker hosts
    :param timeout: seconds to wait for the admin client to connect
    :return: True if connection is successful, otherwise False
    """
    config = {'bootstrap.servers': bootstrap_servers}
    for i in range(num_tries):
        try:
            admin_client = AdminClient(config)
            admin_client.list_topics(timeout=timeout)  # Check if topics can be listed
            return True
        except Exception as e:
            logging.info(f"CKN broker not available yet: {e}. Retrying in 5 seconds...")
            time.sleep(5)
    logging.error("Could not connect to the CKN broker...")
    return False

def delivery_report(err, msg):
    """
    Callback for delivery reports
    """
    if err is not None:
        logging.error("Delivery failed: %s", err)
    else:
        logging.info("Produced example event to '%s' topic", msg.topic())

def read_event_from_file(file_path):
    """
    Reads event data from a JSON file.
    """
    try:
        with open(file_path, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        logging.error(f"Event file not found: {file_path}")
        return None
    except json.JSONDecodeError:
        logging.error(f"Invalid JSON in event file: {file_path}")
        return None

if __name__ == "__main__":
    setup_logging()

    # Configure Kafka producer
    kafka_conf = {'bootstrap.servers': KAFKA_BROKER}
    logging.info("Connecting to the CKN broker at %s", KAFKA_BROKER)

    # Wait for CKN broker to be available
    if not test_ckn_broker_connection(KAFKA_BROKER):
        logging.error("Shutting down CKN Daemon due to broker not being available")
        sys.exit(1)
    logging.info("Successfully connected to the CKN broker at %s", KAFKA_BROKER)

    # Read event data from file
    event = read_event_from_file("/app/event.json")
    if event is None:
        logging.error("Failed to read event data. Shutting down.")
        sys.exit(1)

    # Update timestamps to current time
    current_timestamp = datetime.utcnow().isoformat()
    event['image_receiving_timestamp'] = f"{current_timestamp}Z"
    event['image_scoring_timestamp'] = f"{current_timestamp}Z"
    event['image_store_delete_time'] = f"{current_timestamp}Z"

    # Ensure flattened_scores is a JSON string
    if isinstance(event['flattened_scores'], list):
        event['flattened_scores'] = json.dumps(event['flattened_scores'])

    # Produce event to Kafka topic
    producer = Producer(**kafka_conf)
    producer.produce(KAFKA_TOPIC, json.dumps(event), callback=delivery_report)
    producer.flush(timeout=1)