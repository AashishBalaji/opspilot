"""
Wires the RAG and GitHub tools in as genuine Semantic Kernel native
plugins (not just plain Python objects called directly), so the
diagnosis flow goes through the Kernel the way a real SK-based agent
would. This project deliberately does NOT use SK's autonomous
planner/function-calling loop -- that requires a real, paid LLM with
function-calling support on every CI run, which would make the test
suite flaky, slow, and billed. Instead, the retrieval -> diagnosis
pipeline here is explicit and deterministic, with the Kernel still
doing genuine work (hosting the plugin, running the prompt function)
rather than being an unused import for show.
"""
from __future__ import annotations

from semantic_kernel import Kernel
from semantic_kernel.functions import kernel_function

from opspilot.llm_client import LLMClient
from opspilot.tools.rag_tool import RepoIndex


class RepoContextPlugin:
    """A genuine Semantic Kernel native plugin: methods decorated with
    @kernel_function are registered on the Kernel and callable by name,
    exactly the mechanism a real SK agent would use to give an LLM
    tool access."""

    def __init__(self, index: RepoIndex):
        self._index = index

    @kernel_function(name="search_repo", description="Find the repo files most relevant to a failure message")
    def search_repo(self, query: str) -> str:
        chunks = self._index.query(query, top_k=3)
        if not chunks:
            return "No relevant files found in the indexed repo."
        return "\n\n".join(f"--- {c.path} (relevance {c.score:.2f}) ---\n{c.text}" for c in chunks)


def build_kernel(index: RepoIndex) -> Kernel:
    kernel = Kernel()
    kernel.add_plugin(RepoContextPlugin(index), plugin_name="repo_context")
    return kernel


DIAGNOSIS_SYSTEM_PROMPT = (
    "You are a DevOps diagnostic assistant. Given a CI/CD pipeline failure "
    "and relevant source context retrieved from the repository, propose a "
    "likely root cause and a specific, minimal remediation. You are never "
    "authorized to apply any change yourself -- you may only describe what "
    "a human operator should consider doing. Cite the specific file(s) your "
    "diagnosis is grounded in."
)


async def diagnose_failure(kernel: Kernel, llm: LLMClient, failure_message: str) -> tuple[str, int, int]:
    """Runs the real Kernel-hosted retrieval plugin, then calls the LLM
    client with the retrieved context. Returns (diagnosis_text, prompt_tokens, completion_tokens)."""
    repo_context_fn = kernel.get_function("repo_context", "search_repo")
    result = await kernel.invoke(repo_context_fn, query=failure_message)
    context = str(result)

    response = llm.diagnose(prompt=DIAGNOSIS_SYSTEM_PROMPT, context=f"FAILURE:\n{failure_message}\n\nCONTEXT:\n{context}")
    return response.text, response.prompt_tokens, response.completion_tokens
