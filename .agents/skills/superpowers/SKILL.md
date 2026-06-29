---
name: superpowers
description: Process disciplines for serious development work — brainstorm before building, test-drive before implementing, find root cause before fixing, verify before claiming done. Use at the start of any feature, bugfix, or multi-step task to decide HOW to approach it before touching code.
license: MIT
---

# Superpowers (condensed)

Condensed core of the superpowers framework: the disciplines that decide *how* to
approach work. These are **process skills** — apply them before implementation skills.
Priority: process first (this), then implementation. User instructions always win over these.

When a discipline below applies, **announce it** ("Using TDD to…") and follow it exactly.
These are rigid by design — adapting away the discipline is violating it.

## 1. Brainstorming — before ANY creative work

Creating a feature, component, or behavior change? Design before building.

**Hard gate:** do not write code, scaffold, or take implementation action until you've
presented a design and the user approved it. Applies to every project, however simple —
"too simple to design" is where unexamined assumptions waste the most work.

- Explore project context first (files, docs, recent commits).
- Ask clarifying questions **one at a time** — purpose, constraints, success criteria.
- Propose 2–3 approaches with trade-offs and a recommendation.
- Present the design (scaled to complexity), get approval, then write a short spec doc.
- If the request spans multiple independent subsystems, decompose first — one spec each.
- Terminal state: move to planning (§4), not straight to code.

## 2. Test-Driven Development — before writing implementation code

**Iron law: NO PRODUCTION CODE WITHOUT A FAILING TEST FIRST.**

Red → Green → Refactor:
1. Write one minimal failing test for the next behavior.
2. Run it. Watch it fail *for the right reason*. (Didn't watch it fail → you don't know it tests the right thing.)
3. Write the minimal code to pass.
4. Run — all green.
5. Refactor while staying green.

Wrote code before the test? Delete it and start from the test. Exceptions (ask first):
throwaway prototypes, generated code, config. "Skip TDD just this once" is rationalization.

## 3. Systematic Debugging — before proposing any fix

**Iron law: NO FIXES WITHOUT ROOT CAUSE INVESTIGATION FIRST.** Symptom fixes are failure.

Phase 1 — root cause, before touching anything:
1. Read error messages / stack traces completely — line numbers, paths, codes.
2. Reproduce consistently. Not reproducible → gather data, don't guess.
3. Check recent changes (git diff, new deps, config, env).
4. In multi-component systems, gather evidence at each boundary before blaming one.

Only after you can explain *why* it happens do you propose a fix. Especially under time
pressure — systematic is faster than thrashing.

## 4. Writing Plans — turn an approved spec into tasks

Write the plan for an engineer with zero context: exact file paths, complete code per
step, exact test commands with expected output. Bite-sized steps (write failing test →
verify fail → implement → verify pass → commit). DRY, YAGNI, TDD, frequent commits.
No placeholders ("TODO", "handle edge cases", "similar to above") — they are plan failures.

## 5. Verification Before Completion — before claiming done

**Iron law: NO COMPLETION CLAIMS WITHOUT FRESH VERIFICATION EVIDENCE.**

Before saying passing / fixed / done / committing / opening a PR:
1. Identify the command that proves the claim.
2. Run it fresh and complete — this message, not a past run.
3. Read full output, check exit code, count failures.
4. State the claim *with* the evidence — or state the actual status.

Red flags = stop: "should work", "probably", "Perfect!/Done!" before running anything,
trusting an agent's "success" report, partial checks. Confidence is not evidence.

---

**Full versions:** these are condensed from the superpowers plugin (brainstorming,
test-driven-development, systematic-debugging, writing-plans, verification-before-completion,
requesting/receiving-code-review, using-git-worktrees). Install the plugin for the complete
skills; this file captures the behavioral core for collaborators without it.
