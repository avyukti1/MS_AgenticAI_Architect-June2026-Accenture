# Mini Project 2: Sequential and Parallel Agent Workflows

This project demonstrates two Microsoft Agent Framework workflows running with Azure AI Foundry and DevUI:

- `sequential-workflow-devui.py`: a two-step research and writing workflow.
- `parallel-workflow-devui.py`: a vacation planner workflow with fan-out and fan-in execution.

Both scripts create Azure-backed chat agents, connect them with `WorkflowBuilder`, and expose the workflow through Agent Framework DevUI.

## Project Files

| File | Purpose |
| --- | --- |
| `sequential-workflow-devui.py` | Runs a sequential workflow: Researcher Agent -> Writer Agent. |
| `parallel-workflow-devui.py` | Runs a parallel workflow: Location Picker -> Destination, Weather, Cuisine -> Itinerary Planner. |
| `requirements.txt` | Python dependencies for Agent Framework, Azure AI Foundry, DevUI, and related packages. |
| `.env` | Local environment configuration for Foundry endpoint and model deployment. |
| `virtualenvsetup.md` | Quick virtual environment setup notes. |
| `APPLICATIONLOGIC.md` | Detailed application logic, workflow wiring, and execution explanation. |

## Prerequisites

Install dependencies in a Python virtual environment:

```powershell
python -m venv myvirtualenv
.\myvirtualenv\Scripts\Activate
pip install -r requirements.txt
```

Sign in to Azure CLI before running the workflows:

```powershell
az login
```

The scripts use `AzureCliCredential`, so the logged-in Azure identity must have access to the Azure AI Foundry project and model deployment.

## Environment Variables

Create or update `.env` with these values:

```env
FOUNDRY_PROJECT_ENDPOINT=https://your-foundry-resource.services.ai.azure.com/api/projects/your-project
MODEL_DEPLOYMENT_NAME=your-model-deployment-name
```

The scripts also support these alternate names:

```env
AI_FOUNDRY_PROJECT_ENDPOINT=...
AI_FOUNDRY_DEPLOYMENT_NAME=...
```

Optional runtime settings:

```env
DEVUI_PORT=8091
DEVUI_SEQUENTIAL_PORT=8090
ITINERARY_DELAY_SECONDS=10
AGENT_RETRY_ATTEMPTS=5
```

## Run the Sequential Workflow

```powershell
python .\sequential-workflow-devui.py
```

Default DevUI URL:

```text
http://localhost:8090
```

If port `8090` is busy:

```powershell
$env:DEVUI_SEQUENTIAL_PORT="8093"
python .\sequential-workflow-devui.py
```

Sample prompts:

```text
Write a short essay on how artificial intelligence is changing education.
```

```text
Research the benefits and risks of using generative AI at work, then write a balanced essay.
```

```text
Explain the importance of cybersecurity for small businesses in a short essay.
```

## Run the Parallel Workflow

```powershell
python .\parallel-workflow-devui.py
```

Default DevUI URL:

```text
http://localhost:8091
```

If port `8091` is busy:

```powershell
$env:DEVUI_PORT="8092"
python .\parallel-workflow-devui.py
```

Sample prompts:

```text
I want a 5-day vacation in India with beaches, good food, and a relaxed budget. Suggest a location and plan the trip.
```

```text
Plan a 4-day family vacation from Bangalore. We like nature, light adventure, and vegetarian food.
```

```text
Suggest a budget-friendly solo travel plan for 6 days. I like history, street food, and walkable cities.
```

## Common Issues

### Endpoint Is None

If you see:

```text
ValueError: Parameter 'endpoint' must not be None.
```

Check that `.env` contains either:

```env
FOUNDRY_PROJECT_ENDPOINT=...
MODEL_DEPLOYMENT_NAME=...
```

or:

```env
AI_FOUNDRY_PROJECT_ENDPOINT=...
AI_FOUNDRY_DEPLOYMENT_NAME=...
```

### Port Already In Use

If you see:

```text
only one usage of each socket address is normally permitted
```

Another DevUI server is already running on that port. Either stop the old Python process or run on a different port:

```powershell
$env:DEVUI_PORT="8092"
python .\parallel-workflow-devui.py
```

### Rate Limit Error

If Azure returns:

```text
429 Too Many Requests
rate_limit_exceeded
```

The model deployment quota is being hit. The scripts include retry/backoff, but for low quota deployments you can increase the delay before the final parallel itinerary step:

```powershell
$env:ITINERARY_DELAY_SECONDS="30"
python .\parallel-workflow-devui.py
```

You can also use shorter prompts or a model deployment with higher quota.

## What to Observe in DevUI

For the sequential workflow, DevUI should show:

```text
User Input -> ResearcherExecutor -> WriterExecutor -> Final Output
```

For the parallel workflow, DevUI should show:

```text
User Input -> LocationSelector
           -> DestinationRecommender
           -> Weather
           -> CuisineSuggestion
           -> ItineraryPlanner
           -> Final Output
```

The parallel workflow is useful for demonstrating independent agent branches that run after a shared starting step and then combine into one final response.
