"""Vacation Planning Workflow Sample for DevUI.

This sample demonstrates a multi-agent workflow for vacation planning using the Microsoft Agent Framework.
Agents include: Location Picker, Destination Recommender, Weather, Cuisine Suggestion, and Itinerary Planner.
"""

import os
import asyncio
import logging
import random
from dotenv import load_dotenv
from agent_framework import (
    Executor,
    WorkflowBuilder,
    WorkflowContext,
    handler,
    WorkflowViz,
)
from agent_framework import ChatAgent
from agent_framework.azure import AzureAIClient
from azure.ai.projects.aio import AIProjectClient
from azure.identity.aio import AzureCliCredential
from agent_framework.devui import serve

# Configuration is kept outside the source code in .env. This avoids hard-coding
# deployment-specific values and lets the workflow run in other environments.
load_dotenv()
project_endpoint = os.getenv("AI_FOUNDRY_PROJECT_ENDPOINT") or os.getenv("FOUNDRY_PROJECT_ENDPOINT")
model = os.getenv("AI_FOUNDRY_DEPLOYMENT_NAME") or os.getenv("MODEL_DEPLOYMENT_NAME")

print("Project Endpoint: ", project_endpoint)
print("Model: ", model)

if not project_endpoint or not model:
    missing = []
    if not project_endpoint:
        missing.append("AI_FOUNDRY_PROJECT_ENDPOINT or FOUNDRY_PROJECT_ENDPOINT")
    if not model:
        missing.append("AI_FOUNDRY_DEPLOYMENT_NAME or MODEL_DEPLOYMENT_NAME")
    raise ValueError("Missing required .env value(s): " + ", ".join(missing))


async def run_agent_with_retry(agent: ChatAgent, message, *, max_tokens: int = 800):
    """Run an agent and wait/retry when Azure returns a transient rate limit."""
    max_attempts = int(os.getenv("AGENT_RETRY_ATTEMPTS", "5"))
    for attempt in range(max_attempts):
        try:
            return await agent.run(message, max_tokens=max_tokens)
        except Exception as exc:
            error_text = str(exc).lower()
            is_rate_limit = (
                "429" in error_text
                or "too many requests" in error_text
                or "rate_limit" in error_text
                or "rate limit" in error_text
            )
            if not is_rate_limit or attempt == max_attempts - 1:
                raise

            delay = min(30, (2 ** attempt) + random.uniform(0.25, 1.25))
            print(f"Rate limit hit. Retrying in {delay:.1f}s...")
            await asyncio.sleep(delay)

async def create_agent(agent_name: str, agent_instructions: str) -> ChatAgent:
    """Create one conversation-scoped Foundry chat agent.

    Each specialist receives its own conversation so its messages and context
    remain independent from the other parallel branches.
    """
    # AzureCliCredential uses the identity established by `az login`.
    credential = AzureCliCredential()
    # AIProjectClient is the entry point to resources in the Foundry project.
    project_client = AIProjectClient(
        endpoint=project_endpoint,
        credential=credential
    )
    # A conversation stores the messages exchanged by this specific agent.
    openai_client = project_client.get_openai_client()
    conversation = await openai_client.conversations.create()
    conversation_id = conversation.id
    print("Conversation ID: ", conversation_id)

    # AzureAIClient binds the project, model deployment, and conversation.
    chat_client = AzureAIClient(
        project_client=project_client,
        conversation_id=conversation_id,
        model_deployment_name=model
    )

    agent = chat_client.create_agent(
        name=agent_name,
        instructions=agent_instructions,
    )
    print(f"{agent_name} Agent created successfully!")
    return agent

# Executors are workflow nodes. A handler receives the upstream node's message,
# invokes its specialist agent, and publishes the result through the context.
class LocationSelectorExecutor(Executor):
    def __init__(self, agent, **kwargs):
        super().__init__(**kwargs)
        self.agent = agent

    @handler
    async def handle(self, user_query: str, ctx: WorkflowContext[str]) -> None:
        response = await run_agent_with_retry(self.agent, user_query, max_tokens=500)
        # send_message forwards this location result to every fan-out branch.
        await ctx.send_message(str(response))

class DestinationRecommenderExecutor(Executor):
    def __init__(self, agent, **kwargs):
        super().__init__(**kwargs)
        self.agent = agent

    @handler
    async def handle(self, location: str, ctx: WorkflowContext[str]) -> None:
        response = await run_agent_with_retry(self.agent, location, max_tokens=500)
        await ctx.send_message(str(response))

class WeatherExecutor(Executor):
    def __init__(self, agent, **kwargs):
        super().__init__(**kwargs)
        self.agent = agent

    @handler
    async def handle(self, location: str, ctx: WorkflowContext[str]) -> None:
        response = await run_agent_with_retry(self.agent, location, max_tokens=450)
        await ctx.send_message(str(response))

class CuisineSuggestionExecutor(Executor):
    def __init__(self, agent, **kwargs):
        super().__init__(**kwargs)
        self.agent = agent

    @handler
    async def handle(self, location: str, ctx: WorkflowContext[str]) -> None:
        response = await run_agent_with_retry(self.agent, location, max_tokens=500)
        await ctx.send_message(str(response))

class ItineraryPlannerExecutor(Executor):
    def __init__(self, agent, **kwargs):
        super().__init__(**kwargs)
        self.agent = agent

    @handler
    async def handle(self, results: list[str], ctx: WorkflowContext[str]) -> None:
        # Fan-in supplies a list containing all three parallel branch results.
        delay_seconds = int(os.getenv("ITINERARY_DELAY_SECONDS", "10"))
        if delay_seconds > 0:
            print(f"Waiting {delay_seconds}s before final itinerary call to avoid rate limits...")
            await asyncio.sleep(delay_seconds)
        response = await run_agent_with_retry(self.agent, results, max_tokens=900)
        # yield_output marks this value as the workflow's final result.
        await ctx.yield_output(str(response))

async def build_workflow():
    """Create the specialist agents and connect them as a parallel workflow."""
    # Agent instructions establish a focused role for each workflow stage.
    location_picker_agent = await create_agent(
        agent_name="Location-Picker-Agent",
        agent_instructions="You help users pick one suitable vacation location. Keep the answer under 120 words and do not ask follow-up questions unless absolutely required."
    )
    destination_recommender_agent = await create_agent(
        agent_name="Destination-Recommender-Agent",
        agent_instructions="You are a travel expert. Recommend practical attractions, neighborhoods, and budget tips for the selected location. Keep the answer under 220 words."
    )
    weather_agent = await create_agent(
        agent_name="Weather-Agent",
        agent_instructions="You are a weather expert. Summarize likely weather and packing advice for the selected destination. Keep the answer under 180 words."
    )
    cuisine_suggestion_agent = await create_agent(
        agent_name="Cuisine-Suggestion-Agent",
        agent_instructions="You are a culinary expert. Suggest local foods and budget-friendly dining ideas for the selected destination. Keep the answer under 220 words."
    )
    itinerary_planner_agent = await create_agent(
        agent_name="Itinerary-Planner-Agent",
        agent_instructions="You are an itinerary planning expert. Combine the destination, weather, and cuisine notes into a clear day-by-day itinerary. Keep the final answer concise and actionable."
    )

    # Executor IDs make nodes identifiable in traces and visualizations.
    location_selector_executor = LocationSelectorExecutor(location_picker_agent, id="LocationSelector")
    destination_recommender_executor = DestinationRecommenderExecutor(destination_recommender_agent, id="DestinationRecommender")
    weather_executor = WeatherExecutor(weather_agent, id="Weather")
    cuisine_suggestion_executor = CuisineSuggestionExecutor(cuisine_suggestion_agent, id="CuisineSuggestion")
    itinerary_planner_executor = ItineraryPlannerExecutor(itinerary_planner_agent, id="ItineraryPlanner")

    # State lets workflow infrastructure inspect or persist the objects
    # associated with an executor.
    for executor in [
        location_selector_executor,
        destination_recommender_executor,
        weather_executor,
        cuisine_suggestion_executor,
        itinerary_planner_executor,
    ]:
        executor.state = {
            "location_picker_agent": location_picker_agent,
            "destination_recommender_agent": destination_recommender_agent,
            "weather_agent": weather_agent,
            "cuisine_suggestion_agent": cuisine_suggestion_agent,
            "itinerary_planner_agent": itinerary_planner_agent,
        }

    # Data flow:
    # user -> location selector -> three concurrent specialists -> itinerary.
    workflow = (
        WorkflowBuilder(
            name="Vacation Planner Workflow",
            description="Multi-agent workflow for vacation planning with recommendations and itinerary."
        )
        .set_start_executor(location_selector_executor)
        # Fan-out starts independent branches from the same location message.
        .add_fan_out_edges(location_selector_executor, [
            destination_recommender_executor,
            weather_executor,
            cuisine_suggestion_executor
        ])
        # Fan-in waits for every branch before planning the itinerary.
        .add_fan_in_edges([
            destination_recommender_executor,
            weather_executor,
            cuisine_suggestion_executor
        ], itinerary_planner_executor)
        .build()
    )

    # Mermaid text makes the workflow graph easy to inspect or document.
    viz = WorkflowViz(workflow)
    mermaid_content = viz.to_mermaid()
    print("Mermaid Diagram:\n", mermaid_content)

    return workflow

def main():
    """Launch the vacation planning workflow in DevUI."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logger = logging.getLogger(__name__)
    devui_port = int(os.getenv("DEVUI_PORT", "8092"))
    logger.info("Starting Vacation Planning Workflow")
    logger.info("Available at: http://localhost:%s", devui_port)
    logger.info("Entity ID: workflow_vacation_planner")

    # asyncio.run bridges this synchronous entry point to async setup.
    workflow = asyncio.run(build_workflow())
    # DevUI provides an interactive browser client. Tracing records each node
    # and agent call so the execution can be inspected.
    serve(entities=[workflow], port=devui_port, auto_open=True, tracing_enabled=True)

if __name__ == "__main__":
    # This guard runs main only when the file is executed directly.
    main()



#######Suggested - user prompts 

#I want a 5-day vacation in India with beaches, good food, and a relaxed budget. Suggest a location and plan the trip.

#Plan a 4-day family vacation from Bangalore. We like nature, light adventure, and vegetarian food.

#I want 3-day trip in Europe during winter. Include destination ideas, weather, cuisine, and itinerary.

#Suggest a budget-friendly solo travel plan for 6 days. I like history, street food, and walkable cities.
