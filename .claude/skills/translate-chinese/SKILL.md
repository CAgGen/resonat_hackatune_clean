---
name: translate-chinese
description: >-
  Translate Chinese text in this repo's source code (comments, docstrings, log
  and error messages, UI strings) into English using the find_chinese.py
  locator script. Use this whenever the user wants to translate, localize,
  internationalize, or "English-ify" Chinese in the codebase — e.g. "translate
  the comments to English", "find and translate the Chinese", "make this repo
  English-only", "remove Chinese text", "translate comments to English". Also use it when reviewing a file
  and the user asks what the Chinese says or to clean up mixed-language code.
  Critically, some Chinese is load-bearing (regex that matches Chinese input,
  LLM prompts, parsed string formats, test assertions) — this skill exists to
  translate the safe parts without breaking the load-bearing ones.
---

# Translate Chinese → English

The goal is an English codebase that still behaves identically. The danger is
that "just translate everything" silently breaks code: some Chinese strings are
data, not prose. This skill is the disciplined version — locate, classify,
translate, verify.

## 1. Locate

Run the repo's locator from the repo root. It prints `file:line:col: <line>` for
every line containing a CJK character, respecting `.gitignore`.

```bash
python3 find_chinese.py                 # whole repo
python3 find_chinese.py backend         # scope to a dir
python3 find_chinese.py app.py x.ts     # specific files
```

Work one file at a time — translate a file fully, verify, then move on. A giant
cross-file diff is hard to review and hard to roll back.

## 2. Classify each hit before translating

The category decides how careful you must be. Read the surrounding code, don't
guess from the line alone.

**Safe — translate freely (this is the bulk):**
- `# comments` and `""" docstrings """`
- Log lines, `print(...)`, exception *messages* (`raise ValueError("…")`)
- User-facing UI copy in the frontend (translate the text, keep it natural)

**Load-bearing — translate only after confirming it won't change behavior:**
- **String literals that are compared, parsed, or matched.** If a Chinese string
  is a dict key, an `if x == "CJK text"`, a regex pattern, or a token split on later,
  translating one side without the other breaks it. Translate *all* sides
  together, or leave it.
- **Regexes that match Chinese input.** e.g. a pattern matching Chinese
  punctuation `「」，。` exists to parse Chinese — changing it breaks parsing.
- **LLM prompt text.** Prompts in `prompts/*.md` or inline prompt strings are
  tuned; the model's output language/quality may depend on them. Translate only
  if the user explicitly wants the prompts in English, and treat it as a
  behavior change, not a cosmetic one.
- **Test assertions.** `assert "CJK text" in output` passes only because the code
  emits that exact Chinese. Translate the assertion *and* the code it checks in
  the same change, or neither.
- **Persisted/serialized formats.** Strings written to files, DBs, or markdown
  that downstream code reparses (e.g. an evidence/memory line format) — changing
  the literal can orphan existing data or break the parser.

When unsure whether a string is load-bearing, grep for it across the repo. If it
appears in more than one place, it's probably data — handle every occurrence
together.

## 3. Translate well

- Preserve meaning and tone, not word-for-word. A terse Chinese comment becomes a
  terse English comment.
- Keep technical terms, identifiers, API names, and code unchanged.
- Match the surrounding code's comment style and density.
- Don't add explanation the original didn't have — translation, not annotation.

## 4. Verify before claiming done

After each file (and at the end):

```bash
python3 find_chinese.py <file>     # should print nothing for finished files
```

Then prove behavior is unchanged for the parts you touched:
- Backend: run the affected `python3 *.py` self-checks and `pytest`.
- Frontend: `npx tsc --noEmit` and a build if strings were touched.

If a test now fails on a translated assertion, that's the load-bearing case from
step 2 — you changed one side but not the other. Fix both sides or revert that
hunk.

## Scope control

Default to comments/docstrings/messages unless the user says otherwise. If the
repo has Chinese in prompts, parsed formats, or test data, surface those as a
separate decision ("X strings are load-bearing — translate prompts too?") rather
than translating them silently. Report what you translated and what you
deliberately left, with the reason.
