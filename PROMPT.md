Build agent-context, an open-source code knowledge graph and context server for AI coding agents.

The goal is to let an AI coding agent understand an unfamiliar repository without repeatedly exploring large numbers of files.

agent-context should:

- Index an arbitrary local Git repository.
- Extract useful code entities such as files, modules, classes, functions, methods, interfaces, and imports.
- Represent relationships between those entities, including definitions, imports, references, calls, inheritance, and dependencies where they can be determined reliably.
- Persist the resulting graph locally.
- Provide a CLI for indexing and querying a repository.
- Expose useful queries over MCP for coding agents.
- Return compact, structured context rather than dumping raw source chunks.
- Be repository-agnostic and suitable for public use on GitHub.
- Work locally without requiring hosted infrastructure.

Examples of questions the system should eventually help answer:

- Where is authentication implemented?
- What calls this function?
- What depends on this class?
- What would likely be affected if this interface changed?
- Trace the execution path for this endpoint.
- Which tests cover this component?

Develop incrementally.

For every iteration:

1. Inspect all existing code and notes before deciding what to change.
2. Choose one coherent, high-value improvement toward the goal.
3. Implement it completely.
4. Add or update tests.
5. Run relevant validation.
6. Keep the architecture simple.
7. Avoid speculative abstractions.
8. Record important architectural decisions, limitations, discoveries, and possible next steps for future iterations.
9. Prefer working vertical slices over scaffolding.
10. Do not make unrelated cosmetic changes.

Early development should prioritize reaching an end-to-end vertical slice:

repository
→ parser
→ extracted symbols
→ persisted graph
→ query
→ useful output

Once that works, improve the quality of the graph, add additional languages, expose the system through MCP, support incremental indexing, and add evaluations.

Continuously dogfood agent-context against its own source repository once doing so becomes practical.

A successful MVP is reached when:

- a user can install the project,
- run a command to index a repository,
- query its code structure,
- and allow an MCP-compatible coding agent to retrieve useful structured context,
- with automated tests and basic documentation.

Do not attempt the entire roadmap in one iteration. Make one tested, committed improvement at a time.
