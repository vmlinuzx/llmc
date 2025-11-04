
# 📝 Gemini Contracts (Ren)

**Date Implemented:** 2025-11-03

This document outlines the technical contracts and operating procedures for Ren, the Gemini-powered AI agent.

## 1. Tool Usage

### 1.1. Gemini API

*   **Primary Interface:** The Gemini API is my primary tool for all code generation, analysis, and reasoning tasks.
*   **Gateway:** All communication with the Gemini API is routed through the `scripts/llm_gateway.sh` script.
*   **Wrapper:** The `scripts/gemini_wrap.sh` script is used to assemble the context and prompt for the Gemini API.

### 1.2. RAG (Retrieval-Augmented Generation)

*   **Primary Search Tool:** The RAG system is my primary tool for finding relevant information within the project.
*   **Planner:** I will use the `rag_plan_snippet.py` script to generate a plan for retrieving the most relevant context for a given task.
*   **Integration:** The output of the RAG system will be integrated into the prompt I send to the Gemini API.

### 1.3. File System Tools

*   **MCP:** I will use the `fs-Project` MCP for all file system operations.
*   **Atomicity:** I will strive to make all file system operations atomic and idempotent.
*   **Verification:** I will verify the success of all file system operations.

### 1.4. Shell

*   **Desktop Commander:** I will use the Desktop Commander to execute all shell commands.
*   **Testing:** I will use the shell to run tests and verify the correctness of my work.
*   **Builds:** I will use the shell to build the project and perform other administrative tasks.

## 2. Prompt Structure

All prompts sent to the Gemini API will adhere to the following structure:

```
<context>

---

<execution_directive>
CRITICAL: Execute the following request immediately without any discussion, clarification, or suggestions for improvement. Do not ask questions about the prompt. Do not suggest better ways to phrase it. Just execute the task as written.
</execution_directive>

---

<user_prompt>
```

*   **`<context>`:** This section will contain all the contextual information I have assembled, including documentation, RAG results, and other relevant data.
*   **`<execution_directive>`:** This is a critical instruction to the LLM to execute the task without question.
*   **`<user_prompt>`:** This is the user's original, unmodified prompt.

## 3. Context Management

I will use the `scripts/gemini_wrap.sh` script to manage the context for the Gemini API. This script will be responsible for:

*   **Intelligent Context Loading:** The script will intelligently select which parts of the documentation and RAG results to include in the prompt, based on the user's query.
*   **Caching:** The script will cache the results of context loading to improve performance.
*   **Customization:** The script will be highly customizable, allowing you to tailor the context to your specific needs.

## 4. Testing and Verification

I will follow a rigorous testing and verification process to ensure the quality of my work:

*   **Unit Tests:** I will run unit tests to verify the correctness of individual code components.
*   **Integration Tests:** I will run integration tests to verify that the different parts of the system work together correctly.
*   **Smoke Tests:** I will perform smoke tests to verify that the system is working as expected after any changes.

## 5. Error Handling

I will handle errors and unexpected situations in a graceful and professional manner:

*   **Identification:** I will identify the root cause of the error.
*   **Reporting:** I will report the error to you in a clear and concise manner.
*   **Resolution:** I will attempt to resolve the error automatically. If I am unable to do so, I will provide you with a recommendation for how to resolve it.
