# SOLO BUILD RULES

```
1. MAX 200 LINES PER FILE
   If bigger → split into two files
   Smaller files = better Claude context

2. ONE MODULE AT A TIME
   Finish → test → document → commit
   Never work on two modules simultaneously

3. EVERY FUNCTION HAS A TEST
   Written immediately after the function
   No exceptions, no "I'll add tests later"

4. CONTEXT.md PER MODULE
   Each folder has CONTEXT.md
   Contains: purpose, interface, dependencies
   Paste at start of every Claude session for that module

5. DECISIONS.md UPDATED DAILY
   Every architectural choice explained
   Prevents re-arguing settled decisions

6. COMMIT AFTER EVERY WORKING FEATURE
   Message format: "feat: [module] what it does"
   Green tests = safe to commit

7. GITHUB ACTIONS FROM DAY ONE
   Tests run on every push automatically
   Nothing merges to main with failing tests

8. CLAUDE CONTEXT STRUCTURE
   Each Claude session starts with:
   → CONTEXT.md for this module
   → Relevant section of ARCHITECTURE.md
   → Test fixtures available
   → Exact function signature needed
   → Ask for: code + tests + docstring in one response