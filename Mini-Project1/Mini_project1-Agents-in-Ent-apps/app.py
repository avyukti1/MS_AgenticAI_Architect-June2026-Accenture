import os
import re
import json
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from io import BytesIO
from pathlib import Path
from xml.etree import ElementTree

import streamlit as st
from azure.ai.agents import AgentsClient
from azure.ai.agents.models import ListSortOrder
from azure.core.exceptions import ClientAuthenticationError
from azure.identity import AzureCliCredential, ChainedTokenCredential, DefaultAzureCredential, InteractiveBrowserCredential
from dotenv import load_dotenv


load_dotenv()

DEFAULT_PROJECT_ENDPOINT = (
    "https://sandeepfoundry2314.services.ai.azure.com/api/projects/proj-default"
)
DEFAULT_AGENT_ID = ""
DEFAULT_AGENT_NAME = "sandeepagent111"
DEFAULT_APP_AGENT_NAMES = {
    "HR App": "Accenture People Agent",
    "IT Helpdesk App": "Accenture Technology Support Agent",
    "ServiceNow Ticketing App": "Accenture Service Management Agent",
}
DEFAULT_AGENT_ENDPOINT = (
    "https://sandeepfoundry2314.services.ai.azure.com/api/projects/proj-default/"
    "agents/sandeepagent111/endpoint/protocols/openai/responses"
)
DEFAULT_DEPLOYMENT = "grok-4.3"
DEFAULT_MCP_SERVER_NAME = "Microsoft Learn MCP server"
DEFAULT_FOUNDRY_API_VERSION = "v1"
DEFAULT_FOUNDRY_FEATURES = "HostedAgents=V1Preview"
DEFAULT_FOUNDRY_AUTH_MODE = "entra"
DEFAULT_FOUNDRY_TOKEN_SCOPE = "https://ai.azure.com/.default"
DEFAULT_MODEL_VERSION = "Foundry agent runtime"
DEFAULT_TEMPERATURE = "1"
DEFAULT_TOP_P = "1"
DEFAULT_TENANT_ID = ""
DEFAULT_AUTH_MODE = "tenant_chain"

APP_CONFIGS = {
    "HR App": {
        "title": "Employee HR Assistant",
        "short_title": "HR",
        "accent": "#a100ff",
        "accent_soft": "rgba(161, 0, 255, 0.18)",
        "caption": "Ask about leave, onboarding, benefits, HR processes, workplace policies, or HR communications.",
        "context_label": "Policy Context",
        "upload_label": "Upload HR policy file",
        "chat_placeholder": "Ask an HR question...",
        "initial_message": "Hi, I am your Accenture HR AI assistant. How can I help today?",
        "reset_message": "New HR chat started. Ask me any HR policy or employee support question.",
        "agent_env_prefix": "HR",
        "agent_context": (
            "You are HRAgent, a dedicated HR assistant. Answer only HR and employee-support questions. "
            "Help employees with leave, benefits, "
            "onboarding, workplace policies, payroll questions, and HR communications. Avoid inventing "
            "company-specific policy details when context is missing."
        ),
        "routing_keywords": {
            "benefit", "benefits", "employee", "employees", "hr", "leave", "onboarding", "payroll",
            "policy", "policies", "salary", "attendance", "holiday", "holidays", "reimbursement",
            "manager", "probation", "performance", "resignation", "remote", "workplace",
        },
        "quick_prompts": {
            "Leave Policy": "Please explain our leave policy in simple terms, including leave types and approval workflow.",
            "Onboarding": "Create an onboarding checklist for a new employee joining next week.",
            "Benefits": "Summarize common employee benefits and list what details I should verify with HR.",
            "HR Email": "Draft a professional email to HR asking for clarification about remote work eligibility.",
        },
    },
    "IT Helpdesk App": {
        "title": "IT Helpdesk Assistant",
        "short_title": "IT",
        "accent": "#00a3ff",
        "accent_soft": "rgba(0, 163, 255, 0.16)",
        "caption": "Get help with laptop issues, access requests, email, VPN, software, and troubleshooting.",
        "context_label": "IT Knowledge Context",
        "upload_label": "Upload IT SOP or troubleshooting guide",
        "chat_placeholder": "Describe the IT issue...",
        "initial_message": "Hi, I am your Accenture technology support assistant. What issue should we troubleshoot?",
        "reset_message": "New IT helpdesk chat started. Describe the issue or access request.",
        "agent_env_prefix": "IT",
        "agent_context": (
            "You are ITAgent, a dedicated IT helpdesk assistant. Answer only IT support and technology-access questions. "
            "Help users troubleshoot common endpoint, "
            "network, VPN, email, software, password, and access issues. Ask for missing device, urgency, "
            "error message, and business impact details before suggesting escalation."
        ),
        "routing_keywords": {
            "access", "account", "application", "computer", "device", "email", "error", "helpdesk",
            "install", "internet", "it", "laptop", "login", "mfa", "network", "outlook", "password",
            "printer", "software", "support", "system", "troubleshoot", "unlock", "vpn", "wifi",
        },
        "quick_prompts": {
            "Laptop Issue": "My laptop is running very slow. Please give me a troubleshooting checklist.",
            "Password Reset": "Help me with steps for a password reset or account lockout issue.",
            "VPN Problem": "VPN is not connecting. What should I check before raising a ticket?",
            "Software Access": "Draft an IT access request for installing approved project software.",
        },
    },
    "ServiceNow Ticketing App": {
        "title": "ServiceNow Ticketing Assistant",
        "short_title": "SN",
        "accent": "#7fdf64",
        "accent_soft": "rgba(127, 223, 100, 0.16)",
        "caption": "Create ticket drafts, classify incidents, summarize issues, and prepare assignment notes.",
        "context_label": "Ticketing Context",
        "upload_label": "Upload ticket policy, catalog, or SOP",
        "chat_placeholder": "Describe the ticket or incident...",
        "initial_message": "Hi, I am your Accenture ServiceNow ticketing assistant. What ticket should we prepare?",
        "reset_message": "New ticketing chat started. Describe the incident, request, or change.",
        "agent_env_prefix": "SERVICENOW",
        "agent_context": (
            "You are ServNowAgent, a dedicated ServiceNow ticketing assistant. Answer only ticketing, incident, "
            "request, change, assignment, and SLA questions. Help draft incidents, service "
            "requests, assignment notes, impact/urgency, category, priority, short descriptions, and "
            "resolution notes. Keep outputs structured for ticket entry."
        ),
        "routing_keywords": {
            "assignment", "catalog", "category", "change", "classify", "incident", "itsm", "priority",
            "request", "resolution", "routing", "servicenow", "service now", "sla", "subcategory",
            "ticket", "ticketing", "urgency",
        },
        "quick_prompts": {
            "Incident Draft": "Create a ServiceNow incident draft for a user unable to access email.",
            "Classify Ticket": "Classify this ticket by category, subcategory, impact, urgency, and priority.",
            "Assignment Notes": "Write clear assignment group notes for an unresolved VPN connectivity issue.",
            "Resolution Note": "Draft a professional resolution note after restoring application access.",
        },
    },
}


def inject_brand_styles() -> None:
    st.markdown(
        """
        <style>
            :root {
                --acn-purple: #a100ff;
                --acn-violet: #7500c0;
                --acn-cyan: #00a3ff;
                --acn-green: #7fdf64;
                --acn-border: rgba(255, 255, 255, 0.14);
            }

            .stApp {
                background:
                    linear-gradient(90deg, rgba(161, 0, 255, 0.28), transparent 34rem),
                    linear-gradient(135deg, #050505 0%, #111116 52%, #1d1028 100%);
                color: #f7f7f7;
            }

            [data-testid="stSidebar"] {
                background: linear-gradient(180deg, #000000 0%, #15101c 100%);
                border-right: 1px solid var(--acn-border);
            }

            [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
            [data-testid="stSidebar"] label,
            [data-testid="stSidebar"] span {
                color: #f2f2f2;
            }

            .accenture-shell {
                border: 1px solid var(--acn-border);
                background: linear-gradient(135deg, rgba(161,0,255,0.18), rgba(255,255,255,0.045));
                border-radius: 8px;
                padding: 20px 22px;
                margin: 0 0 18px 0;
                box-shadow: 0 22px 70px rgba(0, 0, 0, 0.32);
            }

            .accenture-topline {
                display: flex;
                align-items: center;
                gap: 18px;
                margin-bottom: 14px;
            }

            .accenture-logo-mark {
                width: 140px;
                height: 48px;
                position: relative;
                flex: 0 0 auto;
            }

            .accenture-logo-chevron {
                position: absolute;
                left: 0;
                top: -2px;
                color: var(--acn-purple);
                font-size: 36px;
                font-weight: 900;
                line-height: 1;
            }

            .accenture-logo-text {
                position: absolute;
                left: 0;
                bottom: 2px;
                color: #ffffff;
                font-size: 26px;
                font-weight: 720;
                line-height: 1;
                letter-spacing: 0;
                font-family: Arial, Helvetica, sans-serif;
            }

            .accenture-brand-kicker {
                color: var(--acn-purple);
                font-weight: 700;
                font-size: 13px;
                letter-spacing: 0;
                text-transform: uppercase;
            }

            .accenture-brand-title {
                font-size: 30px;
                font-weight: 760;
                margin-top: 4px;
                color: #ffffff;
                letter-spacing: 0;
            }

            .accenture-brand-copy {
                color: #d8d8d8;
                margin-top: 6px;
                max-width: 820px;
                line-height: 1.45;
            }

            .accenture-mode-row {
                display: grid;
                grid-template-columns: repeat(3, minmax(0, 1fr));
                gap: 10px;
                margin-top: 14px;
            }

            .accenture-mode-chip {
                border-radius: 8px;
                padding: 11px 12px;
                background: rgba(255,255,255,0.07);
                border: 1px solid rgba(255,255,255,0.13);
                color: #f8f8f8;
                font-size: 13px;
                min-height: 54px;
            }

            .accenture-mode-chip strong {
                display: block;
                color: #ffffff;
                margin-bottom: 2px;
            }

            .accenture-mode-chip.hr { border-top: 4px solid var(--acn-purple); }
            .accenture-mode-chip.it { border-top: 4px solid var(--acn-cyan); }
            .accenture-mode-chip.sn { border-top: 4px solid var(--acn-green); }

            div[role="radiogroup"] {
                gap: 8px;
            }

            div[role="radiogroup"] label {
                background: rgba(255,255,255,0.08);
                border: 1px solid rgba(255,255,255,0.13);
                border-radius: 8px;
                padding: 9px 10px;
                margin-bottom: 8px;
                transition: all 0.18s ease;
            }

            div[role="radiogroup"] label:hover {
                background: rgba(161, 0, 255, 0.16);
                border-color: rgba(161, 0, 255, 0.55);
            }

            div[role="radiogroup"] label:nth-of-type(1) { border-left: 5px solid var(--acn-purple); }
            div[role="radiogroup"] label:nth-of-type(2) { border-left: 5px solid var(--acn-cyan); }
            div[role="radiogroup"] label:nth-of-type(3) { border-left: 5px solid var(--acn-green); }

            .stButton > button {
                border-radius: 8px;
                border: 1px solid rgba(255,255,255,0.16);
                background: linear-gradient(135deg, rgba(255,255,255,0.13), rgba(255,255,255,0.07));
                color: #ffffff;
                font-weight: 650;
            }

            .stButton > button:hover {
                border-color: var(--acn-purple);
                color: #ffffff;
                background: linear-gradient(135deg, rgba(161,0,255,0.45), rgba(117,0,192,0.25));
            }

            [data-testid="stChatMessage"] {
                background: rgba(255,255,255,0.075);
                border: 1px solid rgba(255,255,255,0.11);
                border-radius: 8px;
            }

            [data-testid="stTextInput"] input {
                background: rgba(255,255,255,0.08);
                border-color: rgba(255,255,255,0.16);
                color: #ffffff;
            }

            @media (max-width: 760px) {
                .accenture-topline { align-items: flex-start; flex-direction: column; }
                .accenture-mode-row { grid-template-columns: 1fr; }
                .accenture-brand-title { font-size: 24px; }
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_brand_header() -> None:
    st.markdown(
        """
        <div class="accenture-shell">
            <div class="accenture-topline">
                <div class="accenture-logo-mark" aria-label="Accenture">
                    <div class="accenture-logo-chevron">&gt;</div>
                    <div class="accenture-logo-text">accenture</div>
                </div>
                <div>
                    <div class="accenture-brand-kicker">Let there be change</div>
                    <div class="accenture-brand-title">Accenture AI Agent Apps Portal</div>
                    <div class="accenture-brand-copy">
                        A multi-application assistant experience for HR, technology support,
                        and ServiceNow workflows, aligned to Accenture's reinvention mindset and powered by Azure AI Foundry.
                    </div>
                </div>
            </div>
            <div class="accenture-mode-row">
                <div class="accenture-mode-chip hr"><strong>HR App</strong>People experience and talent support</div>
                <div class="accenture-mode-chip it"><strong>IT Helpdesk App</strong>Cloud, device, access and productivity help</div>
                <div class="accenture-mode-chip sn"><strong>ServiceNow Ticketing App</strong>Service management, incident drafts and notes</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def get_config() -> dict[str, str]:
    endpoint = os.getenv(
        "FOUNDRY_PROJECT_ENDPOINT",
        os.getenv("AZURE_AI_PROJECT_ENDPOINT", DEFAULT_PROJECT_ENDPOINT),
    ).strip()
    agent_endpoint = os.getenv("FOUNDRY_AGENT_ENDPOINT", DEFAULT_AGENT_ENDPOINT).strip()
    api_key = os.getenv("FOUNDRY_API_KEY", "").strip()
    agent_id = os.getenv("AZURE_AI_AGENT_ID", DEFAULT_AGENT_ID).strip()
    tenant_id = os.getenv("AZURE_TENANT_ID", DEFAULT_TENANT_ID).strip()
    auth_mode = os.getenv("AZURE_AUTH_MODE", DEFAULT_AUTH_MODE).strip().lower()
    model_deployment = os.getenv(
        "MODEL_DEPLOYMENT_NAME",
        os.getenv("AZURE_AI_DEPLOYMENT", DEFAULT_DEPLOYMENT),
    ).strip()
    mcp_server_name = os.getenv("MCP_SERVER_NAME", DEFAULT_MCP_SERVER_NAME).strip()
    foundry_api_version = os.getenv("FOUNDRY_API_VERSION", DEFAULT_FOUNDRY_API_VERSION).strip()
    foundry_features = os.getenv("FOUNDRY_FEATURES", DEFAULT_FOUNDRY_FEATURES).strip()
    foundry_auth_mode = os.getenv("FOUNDRY_AUTH_MODE", DEFAULT_FOUNDRY_AUTH_MODE).strip().lower()
    foundry_token_scope = os.getenv("FOUNDRY_TOKEN_SCOPE", DEFAULT_FOUNDRY_TOKEN_SCOPE).strip()
    agents = {}
    for app_name, app_config in APP_CONFIGS.items():
        prefix = app_config["agent_env_prefix"]
        agents[app_name] = {
            "agent_id": os.getenv(f"AZURE_AI_{prefix}_AGENT_ID", agent_id).strip(),
            "agent_name": os.getenv(
                f"AZURE_AI_{prefix}_AGENT_NAME",
                DEFAULT_APP_AGENT_NAMES[app_name],
            ).strip(),
        }
    return {
        "endpoint": endpoint,
        "agent_endpoint": agent_endpoint,
        "api_key": api_key,
        "agent_id": agent_id,
        "agent_name": os.getenv("AZURE_AI_AGENT_NAME", DEFAULT_AGENT_NAME).strip(),
        "agents": agents,
        "deployment": model_deployment,
        "mcp_server_name": mcp_server_name,
        "foundry_api_version": foundry_api_version,
        "foundry_features": foundry_features,
        "foundry_auth_mode": foundry_auth_mode,
        "foundry_token_scope": foundry_token_scope,
        "model_version": os.getenv("AZURE_AI_MODEL_VERSION", DEFAULT_MODEL_VERSION).strip(),
        "temperature": os.getenv("AZURE_AI_AGENT_TEMPERATURE", DEFAULT_TEMPERATURE).strip(),
        "top_p": os.getenv("AZURE_AI_AGENT_TOP_P", DEFAULT_TOP_P).strip(),
        "tenant_id": tenant_id,
        "auth_mode": auth_mode,
    }


def build_azure_credential(tenant_id: str, auth_mode: str):
    tenant_id = (tenant_id or "").strip()
    auth_mode = (auth_mode or "tenant_chain").strip().lower()

    if auth_mode == "azure_cli":
        return AzureCliCredential(tenant_id=tenant_id or None)

    if auth_mode == "browser":
        return InteractiveBrowserCredential(tenant_id=tenant_id or None)

    if auth_mode == "default":
        return DefaultAzureCredential(
            interactive_browser_tenant_id=tenant_id or None,
            additionally_allowed_tenants=[tenant_id, "*"] if tenant_id else ["*"],
            exclude_interactive_browser_credential=False,
        )

    return ChainedTokenCredential(
        AzureCliCredential(tenant_id=tenant_id or None),
        InteractiveBrowserCredential(tenant_id=tenant_id or None),
    )


@st.cache_resource(show_spinner=False)
def get_agents_client(endpoint: str) -> AgentsClient:
    return AgentsClient(
        endpoint=endpoint,
        credential=build_azure_credential("", "default"),
    )


def extract_uploaded_text(uploaded_file) -> str:
    if uploaded_file is None:
        return ""

    suffix = Path(uploaded_file.name).suffix.lower()
    raw_bytes = uploaded_file.getvalue()

    if suffix in {".txt", ".md", ".csv"}:
        return raw_bytes.decode("utf-8", errors="ignore")

    if suffix == ".pdf":
        try:
            from pypdf import PdfReader

            reader = PdfReader(BytesIO(raw_bytes))
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception as exc:
            st.warning(f"Could not read PDF text: {exc}")
            return ""

    if suffix == ".docx":
        try:
            return extract_docx_text(raw_bytes)
        except Exception as exc:
            st.warning(f"Could not read Word document text: {exc}")
            return ""

    st.warning("Supported files: PDF, DOCX, TXT, MD, CSV.")
    return ""


def extract_docx_text(raw_bytes: bytes) -> str:
    with zipfile.ZipFile(BytesIO(raw_bytes)) as docx:
        document_xml = docx.read("word/document.xml")

    root = ElementTree.fromstring(document_xml)
    namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    paragraphs = []
    for paragraph in root.findall(".//w:p", namespace):
        text_parts = [
            node.text
            for node in paragraph.findall(".//w:t", namespace)
            if node.text
        ]
        if text_parts:
            paragraphs.append("".join(text_parts))
    return "\n".join(paragraphs)


def words_from_text(text: str) -> set[str]:
    return {
        word
        for word in re.findall(r"[a-zA-Z][a-zA-Z0-9]{2,}", text.lower())
    }


def route_app(prompt: str, current_app: str, context_text: str = "") -> str:
    combined_words = words_from_text(f"{prompt}\n{context_text[:1200]}")
    scores = {}
    for app_name, app_config in APP_CONFIGS.items():
        keyword_score = len(combined_words.intersection(app_config["routing_keywords"]))
        exact_phrase_score = sum(
            2
            for keyword in app_config["routing_keywords"]
            if " " in keyword and keyword in prompt.lower()
        )
        scores[app_name] = keyword_score + exact_phrase_score

    best_app = max(scores, key=scores.get)
    if scores[best_app] == 0:
        return current_app
    if scores[best_app] == scores.get(current_app, 0):
        return current_app
    return best_app


def uploaded_context_answer(app_name: str, prompt: str, context_text: str) -> str:
    if not context_text.strip():
        return ""

    stop_words = {
        "please", "tell", "about", "what", "when", "where", "which", "with", "from", "this", "that",
        "into", "your", "have", "show", "give", "need", "does", "will", "can", "for", "the", "and",
    }
    query_words = {
        word
        for word in re.findall(r"[a-zA-Z][a-zA-Z0-9]{2,}", prompt.lower())
        if word not in stop_words
    }

    units = [
        block.strip()
        for block in re.split(r"\n\s*\n|(?<=[.!?])\s+", context_text)
        if block.strip()
    ]
    chunks = []
    for index, unit in enumerate(units):
        nearby_text = " ".join(units[index:index + 4]).strip()
        if len(nearby_text) > 35:
            chunks.append((index, nearby_text[:1000]))

    scored_blocks = []
    for index, chunk in chunks:
        chunk_lower = chunk.lower()
        score = sum(2 for word in query_words if re.search(rf"\b{re.escape(word)}\b", chunk_lower))
        score += sum(1 for word in APP_CONFIGS[app_name]["routing_keywords"] if word in chunk_lower)
        score += 3 if any(term in chunk_lower for term in {"must", "should", "steps", "process", "approval", "required"}) else 0
        if score:
            scored_blocks.append((score, index, chunk))

    verify_note = {
        "HR App": "Please verify the final interpretation with HR if this affects eligibility, approval, or payroll.",
        "IT Helpdesk App": "Please verify environment-specific tools, access rules, and approvals with IT support.",
        "ServiceNow Ticketing App": "Please verify live routing, assignment groups, and SLA values in ServiceNow.",
    }.get(app_name, "Please verify final details with the owning team.")

    if not scored_blocks:
        excerpt = context_text.strip()[:1200]
        return (
            "I could not find a direct matching section in the uploaded document. Here is the document preview I could read:\n\n"
            f"> {excerpt}\n\n"
            f"{verify_note}"
        )

    top_blocks = []
    for _, _, block in sorted(scored_blocks, key=lambda item: (-item[0], item[1])):
        normalized_block = re.sub(r"\s+", " ", block).strip()
        if any(normalized_block in existing or existing in normalized_block for existing in top_blocks):
            continue
        top_blocks.append(normalized_block)
        if len(top_blocks) == 4:
            break
    excerpts = "\n\n".join(f"- {block[:900]}" for block in top_blocks)
    return (
        f"Answer from the uploaded {APP_CONFIGS[app_name]['short_title']} document:\n\n"
        f"{excerpts}\n\n"
        f"{verify_note}"
    )


def build_agent_prompt(app_name: str, user_prompt: str, context_text: str) -> str:
    app_config = APP_CONFIGS[app_name]
    context_block = ""
    if context_text.strip():
        context_block = (
            "\n\nUploaded document context follows. Treat it as the primary source for policy-specific answers. "
            "Answer from this context when relevant. If the answer is not present in the context, say that clearly.\n\n"
            "<uploaded_context>\n"
            f"{context_text[:24000]}\n"
            "</uploaded_context>"
        )

    return (
        f"{app_config['agent_context']}"
        f"{context_block}\n\n"
        f"Application: {app_name}\n"
        f"User request:\n{user_prompt}"
    )


def message_text(message) -> str:
    if not getattr(message, "text_messages", None):
        return ""
    return message.text_messages[-1].text.value


def get_or_create_thread(client: AgentsClient, app_name: str) -> str:
    thread_key = f"thread_id_{app_name}"
    if thread_key not in st.session_state:
        thread = client.threads.create()
        st.session_state[thread_key] = thread.id
    return st.session_state[thread_key]


def ask_foundry_agent(client: AgentsClient, agent_id: str, app_name: str, prompt: str, context_text: str) -> str:
    thread_id = get_or_create_thread(client, app_name)
    agent_prompt = build_agent_prompt(app_name, prompt, context_text)

    client.messages.create(
        thread_id=thread_id,
        role="user",
        content=agent_prompt,
    )

    run = client.runs.create_and_process(
        thread_id=thread_id,
        agent_id=agent_id,
    )

    if run.status == "failed":
        raise RuntimeError(f"Agent run failed: {run.last_error}")

    messages = client.messages.list(
        thread_id=thread_id,
        order=ListSortOrder.ASCENDING,
    )
    assistant_messages = [
        message_text(message)
        for message in messages
        if message.role == "assistant" and message_text(message)
    ]

    if not assistant_messages:
        return "The agent completed the run but did not return a text response."
    return assistant_messages[-1]


def extract_responses_text(payload: dict) -> str:
    if payload.get("output_text"):
        return str(payload["output_text"])

    text_parts = []
    for output_item in payload.get("output", []):
        for content_item in output_item.get("content", []):
            if "text" in content_item:
                text_parts.append(str(content_item["text"]))
            elif content_item.get("type") in {"output_text", "text"} and content_item.get("value"):
                text_parts.append(str(content_item["value"]))

    if text_parts:
        return "\n".join(text_parts)
    return ""


def endpoint_with_api_version(agent_endpoint: str, api_version: str) -> str:
    parsed = urllib.parse.urlparse(agent_endpoint)
    query = dict(urllib.parse.parse_qsl(parsed.query, keep_blank_values=True))
    query.setdefault("api-version", api_version)
    return urllib.parse.urlunparse(
        parsed._replace(query=urllib.parse.urlencode(query))
    )


def ask_foundry_responses_agent(
    agent_endpoint: str,
    api_key: str,
    api_version: str,
    foundry_features: str,
    foundry_auth_mode: str,
    foundry_token_scope: str,
    tenant_id: str,
    azure_auth_mode: str,
    app_name: str,
    prompt: str,
    context_text: str,
) -> str:
    agent_prompt = build_agent_prompt(app_name, prompt, context_text)
    body = json.dumps({"input": agent_prompt}).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
    }
    if foundry_auth_mode == "api_key":
        headers["api-key"] = api_key
    else:
        credential = build_azure_credential(tenant_id, azure_auth_mode)
        token = credential.get_token(foundry_token_scope).token
        headers["Authorization"] = f"Bearer {token}"

    if foundry_features:
        headers["Foundry-Features"] = foundry_features

    request = urllib.request.Request(
        endpoint_with_api_version(agent_endpoint, api_version),
        data=body,
        headers=headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"Responses endpoint returned HTTP {exc.code}: {error_body}") from exc

    answer = extract_responses_text(payload)
    if not answer:
        raise RuntimeError("Responses endpoint completed but did not return text output.")
    return answer


def format_agent_error(exc: Exception) -> str:
    if isinstance(exc, ClientAuthenticationError):
        if ".azure" in str(exc) and "Permission denied" in str(exc):
            return (
                "The cloud agent is configured, but Azure authentication cannot read your local Azure CLI profile "
                "at `C:\\Users\\xsr89\\.azure`. Fix that folder permission or run `az login` again from a normal "
                "PowerShell window, then restart this app. I will continue using the uploaded document locally for now."
            )
        return (
            "The cloud agent is configured, but the local machine could not access the Foundry project. "
            "I will continue using the uploaded document locally for now."
        )

    return (
        "Azure AI Foundry agent request failed.\n\n"
        f"Error: `{exc}`\n\n"
        "Please confirm the Foundry project endpoint, agent responses endpoint, API key, and Azure permissions."
    )


def context_note(app_name: str, context_text: str) -> str:
    if context_text.strip():
        return "\n\nI also see uploaded context. Please use that document as the source of truth for final details."

    if app_name == "HR App":
        return "\n\nFor company-specific limits, eligibility, balances, or approvals, please verify the final policy with HR."
    if app_name == "IT Helpdesk App":
        return "\n\nFor environment-specific tools, approvals, or access rules, please verify with your IT support team."
    return "\n\nFor live routing, assignment groups, and SLA rules, please verify the final values in ServiceNow."


def fallback_answer(app_name: str, prompt: str, context_text: str) -> str:
    context_answer = uploaded_context_answer(app_name, prompt, context_text)
    if context_answer:
        return context_answer

    if app_name == "IT Helpdesk App":
        return fallback_it_answer(prompt, context_text)
    if app_name == "ServiceNow Ticketing App":
        return fallback_servicenow_answer(prompt, context_text)
    return fallback_hr_answer(prompt, context_text)


def fallback_hr_answer(prompt: str, context_text: str) -> str:
    prompt_lower = prompt.lower()
    note = context_note("HR App", context_text)

    if "leave" in prompt_lower:
        return (
            "Here is a simple leave-policy summary:\n\n"
            "- Employees usually request planned leave in advance through the HR or leave-management system.\n"
            "- Common leave types include annual leave, sick leave, emergency leave, maternity/paternity leave, and unpaid leave.\n"
            "- Managers typically approve leave based on balance, business coverage, and policy eligibility.\n"
            "- Sick or emergency leave may require later documentation depending on company policy.\n"
            "- Employees should check leave balance before applying and keep their manager informed."
            f"{note}"
        )

    if "onboard" in prompt_lower or "joining" in prompt_lower:
        return (
            "Here is a practical onboarding checklist:\n\n"
            "- Confirm joining date, role, manager, work location, and reporting time.\n"
            "- Collect required identity, bank, tax, and employment documents.\n"
            "- Set up email, laptop, access cards, HR portal access, and collaboration tools.\n"
            "- Share company policies, code of conduct, security guidance, and benefits details.\n"
            "- Schedule introductions with the manager, team, HR, IT, and buddy or mentor.\n"
            "- Plan first-week goals, training sessions, and a 30-day check-in."
            f"{note}"
        )

    if "benefit" in prompt_lower:
        return (
            "Common employee benefits usually include:\n\n"
            "- Health or medical insurance.\n"
            "- Paid time off and holidays.\n"
            "- Retirement or savings plans where applicable.\n"
            "- Learning, certification, or training support.\n"
            "- Wellness, employee assistance, or flexible work programs.\n\n"
            "Details such as eligibility, enrollment window, dependents, and coverage limits should be checked with HR."
            f"{note}"
        )

    if "email" in prompt_lower or "draft" in prompt_lower:
        return (
            "Subject: Clarification Request Regarding HR Policy\n\n"
            "Dear HR Team,\n\n"
            "I hope you are doing well. I would like to request clarification regarding the relevant HR policy and the process I should follow. "
            "Please let me know the eligibility criteria, required approvals, and any documents or timelines I should be aware of.\n\n"
            "Thank you for your support.\n\n"
            "Best regards,"
            f"{note}"
        )

    return (
        "I can help with HR topics such as leave, onboarding, benefits, policy clarification, workplace guidance, and HR emails. "
        "Please share the specific HR question or process you want help with."
        f"{note}"
    )


def fallback_it_answer(prompt: str, context_text: str) -> str:
    prompt_lower = prompt.lower()
    note = context_note("IT Helpdesk App", context_text)

    if "vpn" in prompt_lower:
        return (
            "VPN troubleshooting checklist:\n\n"
            "- Confirm internet is working outside VPN.\n"
            "- Restart the VPN client and try signing in again.\n"
            "- Check username, MFA prompt, and password status.\n"
            "- Confirm system date/time is correct.\n"
            "- Try a different network such as mobile hotspot.\n"
            "- Capture the exact error message and time of failure.\n"
            "- If still failing, raise a ticket with device name, OS, location, VPN client version, and business impact."
            f"{note}"
        )

    if "password" in prompt_lower or "locked" in prompt_lower:
        return (
            "Password or lockout guidance:\n\n"
            "- Use the approved self-service password reset portal if available.\n"
            "- Wait a few minutes after repeated failed attempts before retrying.\n"
            "- Confirm MFA method is active and accessible.\n"
            "- Update saved passwords on phone, email client, VPN, and browser after reset.\n"
            "- Raise a ticket if the account remains locked or MFA is unavailable."
            f"{note}"
        )

    if "software" in prompt_lower or "install" in prompt_lower or "access" in prompt_lower:
        return (
            "Software or access request draft:\n\n"
            "- Request type: Software/access request.\n"
            "- Business justification: Needed for assigned project work.\n"
            "- User details: Name, email, department, manager.\n"
            "- Asset details: Laptop hostname or asset tag.\n"
            "- Software/access needed: Name, version, environment, role.\n"
            "- Approval needed: Manager and application owner if required."
            f"{note}"
        )

    return (
        "Please share the issue category, device name, error message, when it started, urgency, and business impact. "
        "I can then provide troubleshooting steps or a ticket-ready summary."
        f"{note}"
    )


def fallback_servicenow_answer(prompt: str, context_text: str) -> str:
    prompt_lower = prompt.lower()
    note = context_note("ServiceNow Ticketing App", context_text)

    if "classify" in prompt_lower:
        return (
            "Ticket classification template:\n\n"
            "- Type: Incident or Service Request.\n"
            "- Category: Application, Access, Hardware, Network, Security, or Software.\n"
            "- Subcategory: Specific affected service or component.\n"
            "- Impact: Single user, multiple users, department, or enterprise.\n"
            "- Urgency: Low, medium, high, or critical based on business impact.\n"
            "- Priority: Derived from impact and urgency.\n"
            "- Assignment group: Team that owns the affected service."
            f"{note}"
        )

    if "resolution" in prompt_lower:
        return (
            "Resolution note draft:\n\n"
            "Issue was investigated and the affected service/access was restored. Validation was completed with the user or monitoring evidence. "
            "No further action is pending at this time. Ticket can be closed after user confirmation."
            f"{note}"
        )

    return (
        "ServiceNow ticket draft:\n\n"
        "- Short description: User is experiencing an access or service issue.\n"
        "- Description: Include affected user, service, error message, start time, troubleshooting already attempted, and business impact.\n"
        "- Category: To be selected based on affected service.\n"
        "- Impact: Confirm number of affected users.\n"
        "- Urgency: Confirm business deadline or work stoppage.\n"
        "- Assignment notes: Please investigate, validate access/service status, and update the user with next steps."
        f"{note}"
    )


def initialize_state() -> None:
    if "active_app" not in st.session_state:
        st.session_state.active_app = "HR App"
    if "app_messages" not in st.session_state:
        st.session_state.app_messages = {}
    if "app_contexts" not in st.session_state:
        st.session_state.app_contexts = {}
    if "app_context_files" not in st.session_state:
        st.session_state.app_context_files = {}

    for app_name, app_config in APP_CONFIGS.items():
        if app_name not in st.session_state.app_messages:
            st.session_state.app_messages[app_name] = [
                {
                    "role": "assistant",
                    "content": app_config["initial_message"],
                }
            ]
        if app_name not in st.session_state.app_contexts:
            st.session_state.app_contexts[app_name] = ""
        if app_name not in st.session_state.app_context_files:
            st.session_state.app_context_files[app_name] = ""


def reset_chat(app_name: str) -> None:
    st.session_state.app_messages[app_name] = [
        {
            "role": "assistant",
            "content": APP_CONFIGS[app_name]["reset_message"],
        }
    ]
    st.session_state.pop(f"thread_id_{app_name}", None)


def main() -> None:
    st.set_page_config(page_title="Accenture AI Agent Apps Portal", layout="wide")
    inject_brand_styles()
    initialize_state()

    config = get_config()
    endpoint = config["endpoint"]
    app_names = list(APP_CONFIGS.keys())
    active_app = st.session_state.active_app
    app_config = APP_CONFIGS[active_app]
    active_agent = config["agents"][active_app]
    context_text = st.session_state.app_contexts[active_app]
    messages = st.session_state.app_messages[active_app]

    with st.sidebar:
        st.title("Accenture AI Portal")
        st.caption("Let there be change")

        selected_app = st.radio(
            "Application",
            app_names,
            index=app_names.index(active_app),
        )
        if selected_app != active_app:
            st.session_state.active_app = selected_app
            st.rerun()

        st.subheader("Foundry Agent")
        st.selectbox(
            "Assistant engine",
            ["Azure AI Foundry responses endpoint"],
            index=0,
            disabled=True,
        )
        st.text_input("Active agent", value=active_agent["agent_name"], disabled=True)
        st.text_input("Project endpoint", value=endpoint, disabled=True)
        st.text_input("Agent endpoint", value=config["agent_endpoint"], disabled=True)
        st.text_input("Model deployment", value=config["deployment"], disabled=True)
        st.text_input("MCP server", value=config["mcp_server_name"], disabled=True)
        st.text_input("Foundry auth", value=config["foundry_auth_mode"], disabled=True)
        st.text_input("API version", value=config["foundry_api_version"], disabled=True)
        st.text_input("Temperature", value=config["temperature"], disabled=True)
        st.text_input("Top P", value=config["top_p"], disabled=True)
        st.success("Accenture HR, IT, and ServiceNow routing is enabled.")
        thread_key = f"thread_id_{active_app}"
        if thread_key in st.session_state:
            st.text_input("Thread ID", value=st.session_state[thread_key], disabled=True)

        st.subheader(app_config["context_label"])
        uploaded_file = st.file_uploader(
            app_config["upload_label"],
            type=["pdf", "docx", "txt", "md", "csv"],
            key=f"upload_{active_app}",
        )
        if uploaded_file:
            previous_file = st.session_state.app_context_files.get(active_app, "")
            st.session_state.app_contexts[active_app] = extract_uploaded_text(uploaded_file)
            st.session_state.app_context_files[active_app] = uploaded_file.name
            if previous_file != uploaded_file.name:
                st.session_state.pop(f"thread_id_{active_app}", None)
            context_text = st.session_state.app_contexts[active_app]
            if context_text:
                st.success(f"Loaded {len(context_text):,} characters from {uploaded_file.name}")

        if st.button("Clear chat", use_container_width=True):
            reset_chat(active_app)
            st.rerun()

    render_brand_header()
    st.markdown(
        f"""
        <div style="
            border-left: 6px solid {app_config['accent']};
            background: {app_config['accent_soft']};
            border-radius: 8px;
            padding: 14px 16px;
            margin-bottom: 16px;
        ">
            <div style="font-size: 13px; color: {app_config['accent']}; font-weight: 750;">
                Active application: {active_app}
            </div>
            <div style="font-size: 26px; color: #ffffff; font-weight: 760; margin-top: 2px;">
                {app_config['title']}
            </div>
            <div style="color: #e4e4e4; margin-top: 5px;">
                {app_config['caption']}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    quick_prompts = app_config["quick_prompts"]
    cols = st.columns(len(quick_prompts))
    for col, (label, prompt_text) in zip(cols, quick_prompts.items()):
        if col.button(label, use_container_width=True):
            st.session_state.pending_prompt = prompt_text

    for message in messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    prompt = st.chat_input(app_config["chat_placeholder"])
    if "pending_prompt" in st.session_state:
        prompt = st.session_state.pop("pending_prompt")

    if prompt:
        routed_app = route_app(prompt, active_app, context_text)
        routed_config = APP_CONFIGS[routed_app]
        routed_agent = config["agents"][routed_app]
        routed_context_text = st.session_state.app_contexts[routed_app] or context_text

        if routed_app != active_app:
            st.session_state.active_app = routed_app
            st.info(f"Routing this question to {routed_agent['agent_name']} because it matches {routed_config['short_title']} support.")

        st.session_state.app_messages[routed_app].append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner(f"Asking {routed_agent['agent_name']}..."):
                try:
                    if config["agent_endpoint"] and (
                        config["api_key"] or config["foundry_auth_mode"] != "api_key"
                    ):
                        answer = ask_foundry_responses_agent(
                            agent_endpoint=config["agent_endpoint"],
                            api_key=config["api_key"],
                            api_version=config["foundry_api_version"],
                            foundry_features=config["foundry_features"],
                            foundry_auth_mode=config["foundry_auth_mode"],
                            foundry_token_scope=config["foundry_token_scope"],
                            tenant_id=config["tenant_id"],
                            azure_auth_mode=config["auth_mode"],
                            app_name=routed_app,
                            prompt=prompt,
                            context_text=routed_context_text,
                        )
                    elif routed_agent["agent_id"]:
                        client = get_agents_client(endpoint)
                        answer = ask_foundry_agent(
                            client=client,
                            agent_id=routed_agent["agent_id"],
                            app_name=routed_app,
                            prompt=prompt,
                            context_text=routed_context_text,
                        )
                    else:
                        raise RuntimeError("No Foundry responses API key or Azure AI agent ID is configured.")
                except Exception as exc:
                    st.caption(format_agent_error(exc))
                    answer = fallback_answer(routed_app, prompt, routed_context_text)

                st.markdown(answer)
                st.session_state.app_messages[routed_app].append({"role": "assistant", "content": answer})


if __name__ == "__main__":
    main()
