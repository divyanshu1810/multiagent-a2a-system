"""
Host Agent – Gradio UI
Orchestrates the Google ADK host router and provides a chat interface.
"""
from __future__ import annotations

import asyncio
import os

import gradio as gr
from dotenv import load_dotenv

from host_agent.agent import run_host_agent

load_dotenv()


async def chat(message: str, history: list) -> str:
    result = await run_host_agent(message)
    return f"**Routed to:** {result['routed_to']}\n\n{result['response']}"


def gradio_chat(message: str, history: list) -> str:
    return asyncio.run(chat(message, history))


with gr.Blocks(title="ABC Consultants Ltd. — AI Assistant") as demo:
    gr.ChatInterface(
        fn=gradio_chat,
        title="ABC Consultants Ltd. — AI Assistant",
        description=(
            "Ask about HR policies (leave, NPS, WFH, education support, expenses) "
            "or about products, orders, payment, return & delivery policies."
        ),
        examples=[
            "How many WFH days am I allowed per month?",
            "What is the maternity leave entitlement for JL4?",
            "Show me all Electronics products from Samsung with stock > 10",
            "What is the COD limit for orders?",
            "What is the per-person spend limit for a project party in India?",
        ],
    )

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860, share=False, theme=gr.themes.Soft())
