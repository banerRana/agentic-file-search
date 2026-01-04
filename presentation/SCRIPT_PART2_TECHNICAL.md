# Script: Technical Deep Dive
## Part 2 of 2 — Building the Agentic File Search System

**Total Duration**: ~12-15 minutes  
**Tone**: Technical but accessible, show-don't-tell  
**Goal**: Viewers understand HOW it works and can build it themselves

---

## TRANSITION FROM PART 1

> "Alright, now you understand WHY agentic search works better for complex documents. Let's build it."
>
> "I'm going to show you the exact architecture, the tools, and the code. By the end of this, you'll be able to implement this yourself."

---

## SLIDE 1: Title
**fs-explorer — Technical Deep Dive**

> "This is fs-explorer — an open-source agentic document search system. Let me show you how it's built."

---

## SLIDE 2: Architecture Overview
**Click 1**: Query → Workflow → Agent → Gemini  
**Click 2**: Arrow to tools  
**Click 3**: All 6 tools appear

> *[Click 1]*
> "Here's the high-level architecture. A user query comes in and goes to a workflow engine. The workflow coordinates an agent, which talks to Gemini 3 Flash for decision-making."

> *[Click 2]*
> "The agent doesn't just return text — it returns structured actions. Those actions get executed by tools."

> *[Click 3]*
> "There are six tools the agent can use. Think of these as the agent's hands — it can scan folders, preview files, parse documents, read text, search with grep, and find files with glob."

> "The key insight: the agent decides WHICH tool to use based on what it's learned so far. It's not a fixed pipeline."

---

## SLIDE 3: Core Components
**Click 1**: Workflow Engine box  
**Click 2**: Agent box  
**Click 3**: Document Parser box

> "Let me break down the three core components."

> *[Click 1]*
> "First, the Workflow Engine. I'm using LlamaIndex Workflows for this. It's event-driven — the agent emits events, and the workflow reacts. This gives you async execution, timeout handling, and clean separation of concerns."

> *[Click 2]*
> "Second, the Agent. This is a thin wrapper around Gemini 3 Flash. The important part is structured JSON output — the model returns a schema, not free text. This means no parsing errors, predictable actions."

> *[Click 3]*
> "Third, the Document Parser. I'm using Docling — it's open source and runs locally. No API calls for parsing. It handles PDFs, Word docs, PowerPoints, Excel files, HTML, and Markdown. Everything gets converted to clean Markdown text."

---

## SLIDE 4: The 6 Tools
**Click 1**: Tool grid appears  
**Click 2**: Bottom text

> *[Click 1]*
> "Here are the six tools. Let me walk through each one."

> "`scan_folder` — this is the most important tool. It scans ALL documents in a folder in parallel and returns quick previews of each. One API call, full visibility."

> "`preview_file` — quick preview of a single document. About 3000 characters, roughly the first page. Useful for spot checks."

> "`parse_file` — full document extraction. This is the deep dive. You get everything."

> "`read` — for plain text files. Faster than parse_file when you don't need document processing."

> "`grep` — regex search within a file. Useful when you're looking for specific patterns."

> "`glob` — find files by pattern. Like 'find all PDFs in this folder.'"

> *[Click 2]*
> "The agent chooses which tool to use based on the current context. That decision-making is where the intelligence lives."

---

## SLIDE 5: scan_folder Deep Dive
**Click 1**: Code appears  
**Click 2**: Why it matters list

> "Let me zoom in on `scan_folder` because it's the key innovation."

> *[Click 1]*
> "Here's the implementation. It finds all documents in a folder, then uses a ThreadPoolExecutor to process them in parallel. Four workers by default. Each document gets a quick preview — first 1500 characters."

> *[Click 2]*
> "Why does this matter? Three reasons."

> "One: single API call. Instead of the agent calling preview_file ten times, it calls scan_folder once and sees everything."

> "Two: parallel I/O. Document parsing is I/O-bound, so parallelism gives you a real speedup. About 4x faster than sequential."

> "Three: informed decisions. The agent can categorize all documents at once — 'these three are relevant, these seven I can skip.' That's intelligent filtering."

---

## SLIDE 6: Three-Phase Strategy
**Click 1**: Phase 1  
**Click 2**: Phase 2  
**Click 3**: Phase 3

> "Now let me show you how these tools get used in practice. The system follows a three-phase strategy."

> *[Click 1]*
> "Phase one: Parallel Scan. When the agent encounters a folder, it uses scan_folder to preview everything at once. Quick, broad coverage."

> *[Click 2]*
> "Phase two: Deep Dive. Based on those previews, the agent identifies which documents are relevant and calls parse_file on each. Now it's reading the full content."

> *[Click 3]*
> "Phase three: Backtrack. This is critical. If document A says 'see Exhibit B' and the agent skipped Exhibit B in phase one... it goes back and reads it. Cross-references get followed."

> "The system prompt explicitly tells the agent to watch for references and backtrack when needed."

---

## SLIDE 7: Agent Decision Loop
**Click 1**: Receive context  
**Click 2**: Gemini returns JSON  
**Click 3**: Decision tree  
**Click 4**: Loop back

> "Let me show you the agent's decision loop — what happens on each iteration."

> *[Click 1]*
> "The agent receives the full conversation history — the original question, all tool calls so far, all results."

> *[Click 2]*
> "It sends this to Gemini 3 Flash, which returns structured JSON. Not free text — a schema."

> *[Click 3]*
> "That JSON contains an action type. Three possibilities: `tool_call` means 'use this tool with these parameters.' `go_deeper` means 'navigate to this directory.' `stop` means 'I have the answer.'"

> *[Click 4]*
> "After executing the action, the result gets added to history, and we loop. This continues until the agent says stop or we hit a timeout."

---

## SLIDE 8: Structured JSON Output
**Click 1**: Request schema  
**Click 2**: Response example

> "The structured JSON output is crucial. Let me show you why."

> *[Click 1]*
> "When we call Gemini, we set the response MIME type to JSON and provide a schema. This isn't prompt engineering — it's a hard constraint. The model MUST return valid JSON matching this schema."

> *[Click 2]*
> "Here's what a response looks like. Action type is `tool_call`. The reason field contains the agent's thinking — why it chose this action. Then the actual tool call with name and parameters."

> "No parsing, no regex, no 'extract the JSON from this markdown.' It just works."

---

## SLIDE 9: Document Caching
**Click 1**: Cache decision diagram  
**Click 2**: Code implementation

> "One optimization that matters: document caching."

> *[Click 1]*
> "When parse_file gets called, we first check a cache. If the document was already parsed — maybe from a preview or a previous question — we return the cached version instantly."

> *[Click 2]*
> "Implementation is simple. A dictionary mapping file paths to parsed content. Parse once, reuse everywhere."

> "This matters for backtracking. If the agent previewed a document, then later needs the full content, the preview work isn't wasted."

---

## SLIDE 10: Cross-Reference Detection
**Click 1**: Pattern examples  
**Click 2**: Agent behavior

> "How does the agent know when to backtrack? Cross-reference detection."

> *[Click 1]*
> "We tell the agent to watch for patterns like 'See Exhibit A,' 'As stated in the document,' 'Refer to Section 4.2,' and so on. These are in the system prompt."

> *[Click 2]*
> "When the agent encounters a reference, it checks: was that document in my skip list? If yes, it backtracks and reads it. If the referenced document wasn't even in the folder scan, it might use glob to find it."

> "This is where the 'agentic' part shines. The agent is reasoning about what it needs, not just pattern matching."

---

## SLIDE 11: Token Tracking
**Click 1**: Tracking box  
**Click 2**: Pricing calculation

> "Let's talk about cost. Token tracking is built in."

> *[Click 1]*
> "The system tracks API calls, prompt tokens, completion tokens, documents scanned, and documents fully parsed. Everything you need for cost analysis."

> *[Click 2]*
> "With Gemini Flash pricing — 7.5 cents per million input tokens, 30 cents per million output — a typical query over 25 documents costs about a tenth of a cent. That's cheap enough to use in production."

> "The key is efficiency. By scanning first and only deep-diving on relevant documents, you avoid wasting tokens on content that doesn't matter."

---

## SLIDE 12: Workflow Events
**Click 1**: Table header  
**Click 2-5**: Event rows appear

> "Let me show you how the workflow engine communicates. It's event-based."

> *[Click 1]*
> "Four main events."

> *[Click 2]*
> "`ToolCallEvent` — fires when the agent calls a tool. Contains the tool name, inputs, and the agent's reasoning."

> *[Click 3]*
> "`GoDeeperEvent` — fires when the agent navigates to a different directory."

> *[Click 4]*
> "`AskHumanEvent` — fires when the agent needs clarification from the user. The workflow pauses until it gets a response."

> *[Click 5]*
> "`ExplorationEndEvent` — fires when the agent has an answer. Contains the final result or an error."

> "If you're building a UI, you stream these events to show real-time progress. That's exactly what the web interface does."

---

## SLIDE 13: Project Structure
**Click 1**: File tree appears

> *[Click 1]*
> "Here's the file structure. It's intentionally simple."

> "`agent.py` — the Gemini client, token tracking, and the system prompt."

> "`workflow.py` — the LlamaIndex workflow engine, event definitions, step handlers."

> "`fs.py` — all the file tools. Scan, parse, grep, glob."

> "`models.py` — Pydantic models for actions and tool calls. This is your schema."

> "`main.py` — CLI entry point using Typer."

> "`server.py` — FastAPI server with WebSocket for the web UI."

> "`ui.html` — single-file web interface. No build step, no framework."

> "Total is maybe 1500 lines of code. It's not a massive system."

---

## SLIDE 14: Tech Stack
**Click 1**: First row (AI, Docs, Orchestration)  
**Click 2**: Second row (CLI, Web, Package)

> *[Click 1]*
> "The tech stack. For AI, I'm using Gemini 3 Flash through the google-genai SDK. Structured JSON output is native to the API."

> "For document processing, Docling. It's open source, runs locally, handles all common formats."

> "For orchestration, LlamaIndex Workflows. Event-driven, async, handles timeouts gracefully."

> *[Click 2]*
> "CLI uses Typer and Rich for nice formatting. The web UI is FastAPI with WebSocket streaming. Package management with uv — it's fast."

> "All of this is in the requirements. One `pip install` and you're running."

---

## SLIDE 15: Performance
**Click 1**: Stats appear

> *[Click 1]*
> "Let me give you real numbers."

> "Parallel scan of 25 documents takes about 2 seconds. That's all 25 previewed in parallel."

> "Parsing a single document takes about 1 second. Depends on size, but that's typical."

> "Gemini response time is about half a second. Fast."

> "A typical query needs 3 to 5 API calls. Scan, a couple deep dives, maybe a backtrack, then the final answer."

> "Total query time: 5 to 15 seconds depending on how many documents you need to read. For complex multi-document reasoning, that's pretty good."

---

## SLIDE 16: Extensibility
**Click 1**: Adding tools  
**Click 2**: Swapping LLM

> "The system is designed to be extensible."

> *[Click 1]*
> "Want to add a new tool? Four steps. Define the function in fs.py. Add it to the TOOLS dictionary in agent.py. Update the Tools type in models.py. Document it in the system prompt. That's it."

> *[Click 2]*
> "Want to swap the LLM? Replace the google-genai import with anthropic or openai. Update the generate_content call. The rest of the system doesn't change."

> "The architecture is modular. Tools, LLM, and workflow are separate concerns."

---

## SLIDE 17: Key Insights
**Click 1-4**: Each insight appears

> "Let me leave you with four key insights from building this."

> *[Click 1]*
> "One: parallel scanning is crucial. One scan_folder call gives the agent full context to make smart decisions. Without this, you're making dozens of round trips."

> *[Click 2]*
> "Two: structured output prevents errors. When the LLM returns a schema instead of free text, you eliminate an entire class of bugs. No regex, no parsing failures."

> *[Click 3]*
> "Three: backtracking enables thoroughness. The ability to revisit skipped documents based on cross-references is what makes this work on real documents."

> *[Click 4]*
> "Four: caching keeps costs low. Parse once, reuse everywhere. Documents that get previewed aren't re-processed for deep dives."

---

## SLIDE 18: Summary

> "Here's the full flow one more time."

> "Query comes in. Agent scans all documents in parallel. It categorizes them — relevant, maybe, skip. Deep dives on relevant documents. Backtracks when it finds cross-references. Returns an answer with citations."

> "Six tools. Three phases. Less than a cent per query."

---

## OUTRO

> "The code is open source — link in the description. Star it if you found this useful."

> "If you want to see more deep dives on agentic systems, let me know in the comments. I'm thinking about doing one on multi-agent architectures next."

> "Thanks for watching. See you in the next one."

---

## END OF PART 2

---

## NOTES FOR RECORDING

1. **Pacing**: Slow down on code slides. Give viewers time to read.
2. **Screen**: When showing code, consider zooming your IDE or using a larger font.
3. **Scan_folder slide**: This is the "aha" moment. Emphasize why parallel matters.
4. **Three-phase slide**: Connect it back to Part 1's strategy explanation.
5. **Token tracking**: Viewers love cost breakdowns. Don't rush this.
6. **Extensibility**: Plant seeds for viewers to build on this.

## STORY ARC RECAP

**Part 1 Story**: "RAG is broken for complex documents. Here's why. Here's the alternative."

**Part 2 Story**: "Now let's build it. Architecture → Tools → Strategy → Implementation → Results."

**Retention hooks**:
- Part 1: The book analogy (relatable), the "RAG would have..." contrast (satisfying)
- Part 2: The scan_folder insight (technical aha), the cost breakdown (practical value)

**Call to action**: Star the repo, comment for more content.

