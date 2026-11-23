
import json
import uuid
import boto3

AWS_REGION = "us-east-1"

ACTION_RUNTIME_ARN = (
    "arn:aws:bedrock-agentcore:us-east-1:318228906383:"
    "runtime/Action_default_Action-CzUpKGCllv"
)

client = boto3.client("bedrock-agentcore", region_name=AWS_REGION)


def ask_action_agent(question: str) -> str:
    payload = {
        "jsonrpc": "2.0",
        "id": "1",
        "method": "message/send",
        "params": {
            "message": {
                "messageId": str(uuid.uuid4()),
                "role": "user",
                "parts": [
                    {
                        "type": "text",
                        "text": question
                    }
                ]
            }
        }
    }

    response = client.invoke_agent_runtime(
        agentRuntimeArn=ACTION_RUNTIME_ARN,
        runtimeSessionId=str(uuid.uuid4()),
        contentType="application/json",
        accept="application/json",
        payload=json.dumps(payload).encode()
    )

    return response["response"].read().decode()
