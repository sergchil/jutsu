---
name: jutsu
description: Turn on poteto mode, pstack's rigorous playbook router, for this session. Type /jutsu then your task, or /jutsu off.
disable-model-invocation: true
---

If the request is exactly `off`, poteto mode is now off for this session. Confirm in one line and stop. Read nothing.

Otherwise read `${CLAUDE_SKILL_DIR}/skills/poteto-mode/SKILL.md` in full now. Follow it for the request below and for every later turn of this session while poteto mode is on. Paths inside it are relative to that file.

If the request is empty, the request is the text of the user's message before this command. If that is empty too, say poteto mode is on and ask what to work on.

Request: $ARGUMENTS
