from action_client import ask_action_agent

response = ask_action_agent(
    "Create a ticket with summary 'Coordinator connection test', "
    "description 'Verify Coordinator can communicate with Action Agent', "
    "and category 'Technical Support'."
)

print("Here:")
print(response)
