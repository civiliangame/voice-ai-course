"""Slide 13's live demo: the 3-line Grok completion.

Run this in class, right after creating your key at console.x.ai:

    export XAI_API_KEY="xai-..."
    python hello_grok.py

If this prints a sentence, your key, billing, and network path all work,
and nothing about the week-1 homework can block you on account setup.
"""

import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
# The whole xAI quickstart is these three lines (Slide 13):
client = OpenAI(base_url="https://api.x.ai/v1", api_key=os.environ["XAI_API_KEY"])
resp = client.chat.completions.create(
    model="grok-4",  # check https://docs.x.ai for the current flagship name
    messages=[{"role": "user", "content": "In one sentence: why is voice a hard UI?"}],
)
print(resp.choices[0].message.content)
