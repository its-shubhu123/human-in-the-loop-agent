# 🤖 Human-in-the-Loop AI Agent

A Streamlit chat app where a Gemini-powered agent must get your explicit approval before it runs any tool. When the model wants to fetch the weather or search the news, the app pauses and shows the tool name and arguments, and you choose **Approve** or **Reject**.

## Features

- Chat interface built with Streamlit
- Gemini model via LangChain (`langchain-google-genai`)
- Two tools:
  - `get_current_weather`: current weather for any city, via [Open-Meteo](https://open-meteo.com/) (no key needed)
  - `get_latest_news`: web/news search, via [Tavily](https://tavily.com/)
- Approve / Reject buttons before every tool execution. A rejection is passed back to the model so it can respond gracefully.

## Requirements

- Python 3.9+
- A Gemini API key from [Google AI Studio](https://aistudio.google.com/)
- A Tavily API key (only needed for news search)

## Setup

```bash
git clone https://github.com/its-shubhu123/human-in-the-loop-agent.git
cd human-in-the-loop-agent
pip install -r requirements.txt
```

Set your keys as environment variables:

```bash
export GEMINI_API_KEY="your-gemini-key"
export TAVILY_API_KEY="your-tavily-key"
```

On Windows (PowerShell): `$env:GEMINI_API_KEY="your-gemini-key"`

## Run

```bash
streamlit run app.py
```

Then open the URL Streamlit prints (usually http://localhost:8501).

## Running in Google Colab

1. Add `GEMINI_API_KEY` and `TAVILY_API_KEY` in the Colab **Secrets** tab (🔑).
2. Install dependencies and [cloudflared](https://github.com/cloudflare/cloudflared) for a public tunnel:


   ```python
   !pip install -q streamlit langchain-google-genai langchain-core requests
   !wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -O cloudflared
   !chmod +x cloudflared
   ```

3. Load the keys into the environment so the Streamlit process can see them:

   ```python
   import os
   from google.colab import userdata
   os.environ["GEMINI_API_KEY"] = userdata.get("GEMINI_API_KEY")
   os.environ["TAVILY_API_KEY"] = userdata.get("TAVILY_API_KEY")
   ```

4. Upload `app.py` to Colab, then launch and open the tunnel:

   ```python
   import subprocess, time, re

   subprocess.Popen(["streamlit", "run", "app.py", "--server.port", "8501",
                     "--server.headless", "true"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
   time.sleep(5)

   tunnel = subprocess.Popen(["./cloudflared", "tunnel", "--url", "http://localhost:8501"],
                             stderr=subprocess.PIPE, text=True)
   for line in tunnel.stderr:
       m = re.search(r"https://[-a-z0-9]+\.trycloudflare\.com", line)
       if m:
           print("Open your UI here:", m.group(0))
           break
   ```

## Configuration

| Variable | Purpose | Required |
|---|---|---|
| `GEMINI_API_KEY` (or `GOOGLE_API_KEY`) | Gemini access | Yes |
| `TAVILY_API_KEY` | News search tool | Only for news |
| `GEMINI_MODEL` | Override the model name (default in `app.py`) | No |

## How it works

1. You send a message and the model decides whether it needs a tool.
2. If so, the pending tool calls are stored in `st.session_state` and shown for approval.
3. **Approve** runs the tools and feeds the results back to the model. **Reject** sends a "user rejected" message instead.
4. The model then writes its final answer.

## Security

Never commit API keys. This project reads them from environment variables only.
