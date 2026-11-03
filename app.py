import os

import requests
import streamlit as st
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI

# Colab-only secrets store. Optional, so the app also runs locally.
try:
    from google.colab import userdata
except ImportError:
    userdata = None

MODEL_NAME = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")

st.set_page_config(page_title="Human-in-the-Loop AI Agent", page_icon="🤖", layout="wide")

st.title("🤖 Human-in-the-Loop Interactive Agent")
st.markdown(
    "This agent asks for your explicit permission in real-time before executing "
    "any back-end tools (like weather retrieval or web searches)."
)


# 1. API keys
def get_secret(*names):
    """Look for a key in environment variables first, then in Colab secrets."""
    for name in names:
        value = os.environ.get(name)
        if value:
            return value
    if userdata is not None:
        for name in names:
            try:
                value = userdata.get(name)
                if value:
                    return value
            except Exception:
                continue
    return None


GEMINI_API_KEY = get_secret("GEMINI_API_KEY", "GOOGLE_API_KEY")
TAVILY_API_KEY = get_secret("TAVILY_API_KEY", "TRAVILY_API_KEY")

if not GEMINI_API_KEY:
    st.error(
        "Missing Gemini API key. Set GEMINI_API_KEY as an environment variable "
        "(or as a Colab secret)."
    )
    st.stop()

os.environ["GOOGLE_API_KEY"] = GEMINI_API_KEY


# 2. Tools
@tool
def get_current_weather(location: str) -> str:
    """Fetches the current weather description and temperature for a given city or location."""
    try:
        geo_res = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": location, "count": 1, "language": "en", "format": "json"},
            timeout=5,
        ).json()
        if not geo_res.get("results"):
            return f"Could not find coordinates for: {location}"
        loc_data = geo_res["results"][0]
        lat, lon, name = loc_data["latitude"], loc_data["longitude"], loc_data["name"]
        weather_res = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={"latitude": lat, "longitude": lon, "current_weather": "true"},
            timeout=5,
        ).json()
        current = weather_res["current_weather"]
        return f"Weather in {name}: {current['temperature']}°C, Windspeed: {current['windspeed']} km/h."
    except Exception as err:
        return f"Error retrieving weather data: {err}"


@tool
def get_latest_news(query: str) -> str:
    """Searches the internet for news and current events based on a search query."""
    if not TAVILY_API_KEY:
        return "Error: Tavily Search API key is missing or not configured."
    try:
        payload = {
            "api_key": TAVILY_API_KEY,
            "query": query,
            "search_depth": "basic",
            "max_results": 3,
        }
        response = requests.post("https://api.tavily.com/search", json=payload, timeout=8).json()
        results = response.get("results", [])
        if not results:
            return f"No news found for: {query}"
        return "\n".join(
            f"[{idx}] {r.get('title', 'No Title')}: {r.get('content', 'No Content')}"
            for idx, r in enumerate(results, 1)
        )
    except Exception as err:
        return f"Error fetching news: {err}"


tool_map = {
    "get_current_weather": get_current_weather,
    "get_latest_news": get_latest_news,
}

# 3. LLM setup
llm = ChatGoogleGenerativeAI(model=MODEL_NAME, temperature=0)
llm_with_tools = llm.bind_tools(list(tool_map.values()))

# Conversation state
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "pending_tool_calls" not in st.session_state:
    st.session_state.pending_tool_calls = []

# Show previous messages
for msg in st.session_state.chat_history:
    if isinstance(msg, HumanMessage):
        with st.chat_message("user"):
            st.write(msg.content)
    elif isinstance(msg, AIMessage) and msg.content:
        with st.chat_message("assistant"):
            if isinstance(msg.content, list):
                st.write(
                    "".join(
                        part.get("text", "") if isinstance(part, dict) else part
                        for part in msg.content
                    )
                )
            else:
                st.write(msg.content)


def execute_agent_loop():
    """Call the model once. If it wants tools, park them for user approval."""
    response = llm_with_tools.invoke(st.session_state.chat_history)
    st.session_state.chat_history.append(response)

    if response.tool_calls:
        st.session_state.pending_tool_calls = response.tool_calls
        st.rerun()
    elif response.content:
        st.rerun()


# Handle user input
if user_query := st.chat_input("Ask me about weather or recent news..."):
    with st.chat_message("user"):
        st.write(user_query)
    st.session_state.chat_history.append(HumanMessage(content=user_query))
    execute_agent_loop()

# 4. Pending tool confirmations
if st.session_state.pending_tool_calls:
    st.markdown("---")
    st.warning("⚠️ **Approval Required:** The AI agent requests permission to run back-end tools:")

    for tool_call in st.session_state.pending_tool_calls:
        st.info(f"**Tool Name:** `{tool_call['name']}` | **Arguments:** `{tool_call['args']}`")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🟢 Approve and Execute", use_container_width=True):
            for tool_call in st.session_state.pending_tool_calls:
                name, args = tool_call["name"], tool_call["args"]
                if name in tool_map:
                    output = tool_map[name].invoke(args)
                else:
                    output = f"Tool {name} not found."
                st.session_state.chat_history.append(
                    ToolMessage(content=str(output), tool_call_id=tool_call["id"], name=name)
                )
            st.session_state.pending_tool_calls = []
            execute_agent_loop()
    with col2:
        if st.button("🔴 Reject and Skip", use_container_width=True):
            for tool_call in st.session_state.pending_tool_calls:
                st.session_state.chat_history.append(
                    ToolMessage(
                        content=f"User rejected execution of tool '{tool_call['name']}'.",
                        tool_call_id=tool_call["id"],
                        name=tool_call["name"],
                    )
                )
            st.session_state.pending_tool_calls = []
            execute_agent_loop()
