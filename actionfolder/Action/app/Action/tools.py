from gateway import call_gateway_tool
from langchain.tools import tool


@tool
async def draft_email(
    to_role: str,
    subject: str,
    recipient_email: str,  # just added
    body: str,
) -> dict:
    """
    Create an email draft for a specified recipient role.
    The draft must go through the approval process before it can be sent.
    """

    return await call_gateway_tool(
        "ActionLambda___draft_email",
        {
            "to_role": to_role,
            "subject": subject,
            "recipient_email": recipient_email,
            "body": body,
        },
    )


@tool
async def send_approved_email(request_id: str) -> dict:
    """
    Send an email associated with an approved email request.
    The request must already be approved before sending.
    """

    return await call_gateway_tool(
        "ActionLambda___send_approved_email", {"request_id": request_id}
    )


@tool
async def create_ticket(summary: str, description: str, category: str) -> dict:
    """
    Create a support ticket through the authorized ticket creation process.
    """
    print("CREATE_TICKET TOOL STARTED")
    print("Calling Gateway: ActionLambda___create_ticket")
    result = await call_gateway_tool(
        "ActionLambda___create_ticket",
        {"summary": summary, "description": description, "category": category},
    )

    print("GATEWAY RESULT:", result)
    return result
