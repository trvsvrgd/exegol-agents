from langchain_community.chat_models import ChatOllama
from langchain_core.messages import HumanMessage

from app.state import GraphState


def coder_node(state: GraphState) -> dict:
    """Uses ChatOllama (localhost:11434, qwen2.5-coder). Returns mock for now."""
    task = state.get("current_plan", "No task")
    # Uncomment to use real Ollama:
    # llm = ChatOllama(base_url="http://localhost:11434", model="qwen2.5-coder")
    # response = llm.invoke([HumanMessage(content=f"Execute: {task}")])
    # output = response.content
    output = f"[Mock] I wrote code based on the planner's instructions: {task}"

    return {
        "messages": state["messages"] + [{"role": "coder", "content": output}],
        "status": "completed",
    }
