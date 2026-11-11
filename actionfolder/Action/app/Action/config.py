import os

from dotenv import load_dotenv

load_dotenv()

AWS_REGION = os.environ["AWS_REGION"]
BEDROCK_MODEL_ID = os.environ["BEDROCK_MODEL_ID"]
BEDROCK_MAX_TOKENS = int(os.environ["BEDROCK_MAX_TOKENS"])