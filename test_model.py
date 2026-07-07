import os
from dotenv import load_dotenv
from strands import Agent
from strands.models.litellm import LiteLLMModel

load_dotenv()

model = LiteLLMModel(
    client_args={
        "api_base": "https://openrouter.ai/api/v1",
        "api_key": os.environ["OPENROUTER_API_KEY"],
    },
    model_id="openrouter/openrouter/free",
    params={"max_tokens": 256},
)

agent = Agent(model=model)
response = agent("Say hello and tell me what model you are in one sentence.")
print(response)
