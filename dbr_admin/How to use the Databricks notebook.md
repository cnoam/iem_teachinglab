# How to use the Databricks notebook

## Getting started
- Open a notebook and attach it to **Serverless** compute (compute dropdown, top-left). No cluster to wait for — it's ready in seconds.

## Detach when you're not using it
- **If you won't be actively working for the next few minutes, detach** (compute dropdown → Detach).
- An attached notebook uses compute — and counts against your group's usage — even while sitting idle with nothing running.
- Don't count on it disconnecting itself. It may eventually happen, but there's no guaranteed timing — leaving it attached and walking away can burn your group's usage for zero actual work.
- Re-attaching takes seconds, so there's no real downside to detaching between work sessions.

## Your group's daily quota
- Each **group** shares one daily compute-time budget — it's shared across your whole group, not per student.
- It resets every day at **midnight**.
- If your group goes over the limit, you'll be blocked from starting new work (running a new cell, opening a notebook) until the reset. Anything already running when the limit is hit keeps running — you just can't start anything new.
- Because it's shared, coordinate with your groupmates: several of you working at once, or notebooks left attached idle, all draw from the same daily budget.

## Quick checklist
- Attach to **Serverless**, not a classic cluster.
- **Detach** when you step away, even briefly.
- Don't leave notebooks open overnight or between sessions.
- Blocked? It resets at midnight — no need to contact anyone, just wait or plan around it.
