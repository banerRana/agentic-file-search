# Script: RAG vs Agentic File Search
## Part 1 of 2 — The Problem & Solution

**Total Duration**: ~8-10 minutes  
**Tone**: Conversational, educational, no hype  
**Goal**: Make viewers understand WHY traditional RAG fails and WHAT the alternative is

---

## PRE-ROLL (Before Slide 1)

*[Camera on you, or start with slide 1 visible]*

> "If you've ever built a RAG system and wondered why it gives you garbage answers on complex documents... this video is for you."
>
> "I'm going to show you exactly why chunking and embeddings fail on real-world documents, and then build something better. No hype, no fluff — just the actual problem and a working solution."

---

## SLIDE 1: Title
**RAG vs Agentic File Search**

*[Hold for 2-3 seconds, then advance]*

> "RAG versus Agentic File Search. Let's break down what these terms actually mean and when you'd use each one."

---

## SLIDE 2: The Promise of RAG
**Click 1**: Show pipeline diagram  
**Click 2**: Show "Just embed and ask" quote  
**Click 3**: Show "Sounds simple" text

> *[Click 1 — pipeline appears]*
> "Here's the standard RAG pipeline everyone teaches. You take your documents, create embeddings, store them in a vector database, and when someone asks a question, you retrieve the relevant chunks and feed them to an LLM."

> *[Click 2]*
> "The pitch is always the same: 'Just embed your documents and ask questions!' It sounds magical."

> *[Click 3]*
> "And for simple use cases? It works. But here's where things get interesting..."

---

## SLIDE 3: The Reality
**Click 1-4**: Problems appear one by one

> "Let me show you what actually happens when you throw real documents at a RAG system."

> *[Click 1]*
> "Problem one: chunks lose context. When you split a document into 500-token pieces, you destroy the relationships between sections. The chunk about 'the purchase price' doesn't know it's connected to 'Exhibit B' three pages later."

> *[Click 2]*
> "Problem two: cross-references become invisible. Legal documents, technical specs, research papers — they're FULL of phrases like 'See Section 4.2' or 'As defined in Exhibit A.' Embeddings can't follow those links."

> *[Click 3]*
> "Problem three: similarity is not the same as relevance. Just because two pieces of text are semantically similar doesn't mean they're both useful for answering your question."

> *[Click 4]*
> "And problem four: there's no reasoning happening. RAG is pattern matching on surface-level text. It's not understanding your document — it's just finding things that look similar."

---

## SLIDE 4: The Chunking Problem
**Click 1**: Show RAG side  
**Click 2**: Show what you need  
**Click 3**: Show bottom text

> *[Click 1]*
> "Let me make this concrete. Here's what a RAG system actually sees when you ask about a purchase price."

> "Chunk 47 says 'the purchase price shall be adjusted according to...' and then it cuts off. Chunk 48 mentions 'Schedule 2.3(b) which outlines the methodology...' These chunks are neighbors in the document but the RAG system doesn't know that."

> *[Click 2]*
> "What you actually need is the full context: the Purchase Agreement links to Section 2.3, which references Schedule 2.3(b), which points to Exhibit B, which contains the Financial Statements. It's a chain."

> *[Click 3]*
> "Documents are structured. They have hierarchy, cross-references, and logical flow. Chunking destroys all of that structure."

---

## SLIDE 5: Cross-References Are Everywhere
**Click 1**: Document grid  
**Click 2**: Example reference  
**Click 3**: RAG retrieves one chunk  
**Click 4**: Industries that rely on this

> *[Click 1]*
> "Here's a typical document set. Ten files in a folder. When you ask a question, you might need information from three or four of them — but they reference EACH OTHER."

> *[Click 2]*
> "Look at this line: 'The terms in Exhibit B are subject to Schedule 4.2.' This is one sentence that spans two documents."

> *[Click 3]*
> "A RAG system retrieves one chunk. It might find the sentence, but it won't follow the chain. It won't go read Exhibit B or Schedule 4.2."

> *[Click 4]*
> "This isn't a niche problem. Legal documents, technical specifications, research papers, financial filings — they all work this way. Cross-references are the norm, not the exception."

---

## SLIDE 6: What If the AI Could Explore?
**Click 1**: Main text appears

> "So here's the question I started asking: what if instead of pre-computing chunks and hoping for the best..."

> *[Click 1]*
> "...we let the AI actually navigate documents like a human would?"

> *[Pause for effect]*

> "Think about how YOU read documents. You don't read every word linearly. You skim, you jump to relevant sections, you follow references. What if an AI could do the same thing?"

---

## SLIDE 7: The Book Analogy
**Click 1**: Scenario label + question  
**Click 2**: Book with TOC  
**Click 3**: First thought step  
**Click 4**: Second thought step  
**Click 5**: Third and fourth steps + page content

> *[Click 1]*
> "Let me give you a concrete example. You're looking for the return policy on electronics in a store policy manual."

> *[Click 2]*
> "What do you do first? You don't read page one. You look at the table of contents."

> *[Click 3]*
> "You see Chapter 3 is 'Return Policies' — that looks relevant. Chapters about store hours and employee guidelines? You skip those."

> *[Click 4]*
> "You go to page 28, scan for 'electronics'..."

> *[Click 5]*
> "And you find exactly what you need: '30 days with receipt.' And notice — it says 'See Section 4.1 for extended warranty.' A human would follow that link."

> "This is how intelligent document search should work. Not 'find similar text' — but 'understand and navigate.'"

---

## SLIDE 8: RAG Would Have...
**Click 1**: RAG result  
**Click 2**: Agent result

> *[Click 1]*
> "Here's what a RAG system would have returned for the same question. Some chunk that mentions return policies exist and tells you to 'see section 3.2.' It found related text but not the answer."

> *[Click 2]*
> "The agentic approach finds the actual answer, follows the reference to extended warranty info, and gives you complete context. That's the difference."

---

## SLIDE 9: Agentic File Search
**Click 1**: User query box  
**Click 2**: Scan step  
**Click 3**: Deep dive step  
**Click 4**: Follow references step

> "So let me show you what agentic file search actually looks like."

> *[Click 1]*
> "It starts with a user query — same as RAG."

> *[Click 2]*
> "But instead of retrieving pre-computed chunks, the agent scans all documents in parallel. It gets a quick preview of everything at once."

> *[Click 3]*
> "Then it decides which documents are actually relevant and does a deep dive — reading the full content of just those files."

> *[Click 4]*
> "And critically — if it finds a reference to another document, it goes back and reads that too. It can backtrack."

---

## SLIDE 10: Three Phases
**Click 1**: Phase 1 active  
**Click 2**: Phase 2 active  
**Click 3**: Phase 3 active

> "I call this the three-phase strategy."

> *[Click 1]*
> "Phase one: Scan. Get previews of all documents in parallel. This is fast — you're not reading everything, just enough to categorize."

> *[Click 2]*
> "Phase two: Deep dive. Now you read the full content of documents that look relevant."

> *[Click 3]*
> "Phase three: Backtrack. If document A says 'see document B' and you skipped B earlier? Go back and read it."

> "The agent decides what to read based on the question. That's the key difference from RAG."

---

## SLIDE 11: Key Difference
**Click 1**: RAG side  
**Click 2**: Agentic side

> *[Click 1]*
> "Let me summarize the fundamental difference. RAG uses pre-computed embeddings. They're fixed at indexing time. You get the same chunks no matter how you phrase your question."

> *[Click 2]*
> "Agentic search is dynamic. It adapts to each query. Different questions lead to different exploration paths. And it follows logical connections, not just semantic similarity."

---

## SLIDE 12: Real-World Results
**Click 1**: Stats appear

> *[Click 1]*
> "Here's what this looks like in practice. I ran this on a folder of 25 legal documents."

> "Three API calls. About 10,000 tokens. Cost? Less than a tenth of a cent."

> "The agent scanned everything in parallel, identified the relevant documents, and only did deep dives where it mattered. That's efficient exploration, not brute force."

---

## SLIDE 13: When to Use What
**Click 1**: RAG column  
**Click 2**: Agentic column

> "Now, I'm not saying RAG is useless. It has its place."

> *[Click 1]*
> "Use RAG when you have simple Q&A over a large corpus, when documents are independent and don't reference each other, and when speed is critical — RAG is faster."

> *[Click 2]*
> "Use agentic search when you need complex multi-document reasoning, when documents reference each other, when structure matters — like legal or technical docs — and when accuracy is more important than speed."

> "They're different tools for different jobs."

---

## SLIDE 14: Summary
**Click 1**: RAG vs Agentic badges  
**Click 2**: Embeddings vs agents text  
**Click 3**: Future text

> *[Click 1]*
> "So here's the summary. RAG is retrieval — it finds similar text. Agentic search is reasoning — it understands documents."

> *[Click 2]*
> "Embeddings find similar text. Agents understand documents."

> *[Click 3]*
> "I believe the future isn't retrieval. It's exploration."

> *[Transition]*
> "Now, let me show you exactly how to build this. In the next part, we'll go through the technical implementation — the tools, the architecture, and the code."

---

## SLIDE 15: Call to Action

> "If you want to try this yourself, the code is open source. Link in the description."

> "In the next part of this video, I'll walk through exactly how it's built — the agent loop, the tools, the workflow engine. Let's get into it."

---

## END OF PART 1

**Transition to Part 2**: Either cut here for a separate video, or continue directly into the technical deep dive.

---

## NOTES FOR RECORDING

1. **Pacing**: Don't rush the problem slides (3-5). Let viewers feel the pain.
2. **Book analogy**: This is your best retention moment. Make it relatable.
3. **Clicks**: Each click should feel intentional. Pause briefly after important reveals.
4. **Tone**: You're explaining to a smart friend, not lecturing. Stay conversational.
5. **No jargon dump**: Explain terms as you use them.

