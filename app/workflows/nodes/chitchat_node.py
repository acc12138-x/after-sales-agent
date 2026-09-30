"""闲聊/问候节点：不走 RAG，直接返回礼貌回复 + 能力介绍。"""
from __future__ import annotations
import re

from app.workflows.state import AgentState


GREETING_RE = re.compile(r"你好|您好|hi|hello|嗨|哈喽|哈啰|在吗|在不在|早上好|下午好|晚上好", re.I)
WHOAMI_RE   = re.compile(r"你是谁|你叫什么|你能做什么|你会做什么|能帮我做什么|有什么功能|帮助|help|菜单", re.I)
THANKS_RE   = re.compile(r"谢谢|感谢|多谢|thank", re.I)
BYE_RE      = re.compile(r"再见|拜拜|bye|see you|晚安", re.I)


CAPABILITY = """👋 您好，我是业务助手。

我可以帮您：
1. **报修建单** — 例如：帮我报修 XY200 故障码 E102
2. **查询订单/物流** — 例如：查订单 O20240001 / 查物流
3. **查看我的工单** — 例如：查看我的工单
4. **售后政策咨询** — 例如：E102 是什么原因 / 怎么排查
5. **查工程师** — 例如：谁有空 / 张工在吗
6. **转人工** — 例如：转人工

直接说出您的问题即可，我会尽力帮您处理。"""

WHOAMI = """我是**业务助手** 🛠️

可以帮您处理：
- 报修建单、查订单/物流
- 查工单、查工程师空闲情况
- 售后政策、故障排查咨询
- 需要时转人工客服

直接问我就行～"""

THANKS = "不客气 😊 有问题随时找我。"
BYE    = "再见，祝您工作顺利 👋"


def _text_of(state: AgentState) -> str:
    """取当前用户消息：优先 user_input，回退到最后一条 user 消息。

    回退是为了容错 —— 若哪天某个入口忘了填 user_input，
    这里不会静默退化成「能力介绍」。
    """
    t = (state.get("user_input") or "").strip()
    if t:
        return t
    for m in reversed(state.get("messages") or []):
        if isinstance(m, dict) and m.get("role") == "user":
            return (m.get("content") or "").strip()
    return ""


def chitchat_node(state: AgentState) -> AgentState:
    text = _text_of(state)
    if WHOAMI_RE.search(text):
        answer = WHOAMI
    elif THANKS_RE.search(text):
        answer = THANKS
    elif BYE_RE.search(text):
        answer = BYE
    elif GREETING_RE.search(text):
        answer = CAPABILITY
    else:
        answer = CAPABILITY

    messages = state.get("messages", []) or []
    messages = messages + [{"role": "assistant", "content": answer}]
    return {
        **state,
        "answer": answer,
        "messages": messages,
        "flow_status": "succeeded",
    }
