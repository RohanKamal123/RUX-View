from langchain_openai import ChatOpenAI
from browser_use import Agent
import asyncio
from dotenv import load_dotenv

load_dotenv()  # Load API keys from .env file

async def main():
    agent = Agent(
        task="Go to Google, search for 'browser-use GitHub', click on the first link, and return the repository description.",
        llm=ChatOpenAI(model="gpt-4o"),
    )
    result = await agent.run()
    print(result)

asyncio.run(main())
