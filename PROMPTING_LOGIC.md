# Prompting Logic

This document explains how VoterPath uses prompting patterns and tool calls to generate reliable election information.

## Objectives

- Provide concise, factual election and politician information.
- Prefer deterministic data paths first (static + cached + scraped) before generative fallback.
- Keep responses structured in markdown for readability.

## Profile Generation Flow (`/api/profile`)

The profile endpoint follows a layered strategy:

1. **Static profile lookup**  
   Known leaders are returned instantly from `STATIC_PROFILES`.
2. **In-memory cache lookup**  
   Repeated queries return cached content to reduce latency and cost.
3. **Wikipedia scrape path**  
   A search-assisted scrape gathers infobox and summary paragraphs.
4. **LLM fallback generation**  
   If scrape fails, Gemini is used with a constrained profile prompt.

Why this design:
- Faster responses for common names.
- Reduced hallucination risk via factual sources first.
- Graceful fallback when web parsing is unavailable.

## Chat Flow (`/api/chat`)

Chat requests use:

- System instruction: "concise and factual AP election assistant"
- Conversation history mapping into `HumanMessage` and `AIMessage`
- Tool-calling agent with:
  - `search_tool` (DuckDuckGo)
  - `tinyfish_scraper` (URL text extraction)

This enables retrieval-augmented responses instead of pure model memory.

## Prompt Design Principles

- **Role clarity:** fixed assistant role for AP election context.
- **Output shape:** sectioned markdown for profiles.
- **Grounding:** tool usage encouraged for recent or specific facts.
- **Fallback safety:** user-friendly degraded response on rate limits/errors.
- **Cost control:** short max-iteration tool loop and caching.

## Error Handling Strategy

- 429 rate-limit handling with retry for profile generation.
- Informative fallback messaging for temporary failures.
- Tool exceptions captured and returned as explicit error strings.

## Known Limitations

- Scraped sources can change page structure unexpectedly.
- In-memory cache resets on container restart.
- Public web data may contain stale or conflicting facts.

## Future Improvements

- Add Redis/Memorystore for persistent caching.
- Add source citations for every profile section.
- Add evaluation prompts and regression tests for response quality.
