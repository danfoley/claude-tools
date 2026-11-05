---
description: Study mode: pick a topic you want to understand and be taught it, without any work or gates
argument-hint: "[topic]"
---

Run the understand-first skill's teaching mode. Load the `understand-first:understand-first` skill and follow its "Teaching mode" section.

Topic: `$ARGUMENTS`

If a topic was given, teach that. If not, read the ledger and the work log in the data directory (`${UNDERSTAND_FIRST_DATA:-$HOME/.claude/understand-first}`) and offer up to three topics to choose from. Remember: studying never changes the learner's real status, level or code dial.
