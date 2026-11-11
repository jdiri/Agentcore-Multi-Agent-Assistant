from langchain_aws import ChatBedrockConverse
from config import AWS_REGION, BEDROCK_MODEL_ID, BEDROCK_MAX_TOKENS

def _load_model() -> ChatBedrockConverse:
    """ Build Bedrock chat mmodel from environment variables. """

    return ChatBedrockConverse(
        model=BEDROCK_MODEL_ID,
        region_name=AWS_REGION,
        max_tokens=BEDROCK_MAX_TOKENS,
        temperature=0.0
    )


# lazily load the model so it is only ever instantiated when it is used
_MODEL : ChatBedrockConverse | None = None

def get_model() -> ChatBedrockConverse:

    global _MODEL
    if _MODEL is None:
        _MODEL = _load_model()
    return _MODEL