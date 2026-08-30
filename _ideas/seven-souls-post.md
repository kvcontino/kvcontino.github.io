---
layout: default
title: Seven Souls
date: YYYY-MM-DD
categories: notes
description: I want to reach the Western Lands, and I'll burn as many tokens as it takes to get there.
---

<!-- STATUS: skeleton. Essential details filled in; narrative is yours to write.
     Before moving to _posts/: set a real date (filename date and date: must
     agree), confirm `categories:` (it sets the URL), and delete every TODO. -->

<p class="dek">TODO — the dek. One or two sentences on why a single reviewer, however good, returns the same five findings every time, and what changes when you give seven of them incompatible postures.</p>

<!-- TODO: opening section. The problem this solves: asking a model "review this"
     produces agreeable, undifferentiated criticism. The fix is not a better
     prompt — it is a division of labor enforced by persona. -->

## The frame

Burroughs, *The Western Lands*: "The Ancient Egyptians postulated seven souls." Each soul departs the body at a different point and answers for a different thing. That structure is already a review rubric — seven mutually exclusive accountabilities, none of which can be satisfied by another.

<span class="sc">Seven Souls</span> is a slash command that dispatches seven adversarial reviewers against one work product, one per soul, in parallel. The names are not decoration. They are what gives each reviewer a distinct posture, and the posture is what stops seven agents from converging on the same complaints.

<div class="tablewrap" markdown="1">

| # | Soul | Burroughs | Review lens |
|---|---|---|---|
| 1 | **Ren** — the Secret Name | The Director. Directs the film of your life; the Secret Name is its title. First to leave. | Thesis, title, architecture. One argument or several? Does each section earn its position? Does the ending land the thesis or substitute a flourish? |
| 2 | **Sekem** — Energy, Power, Light | The Director gives the orders; Sekem presses the right buttons. | Execution and arithmetic. Recompute every headline number — denominators, units, percentages vs. points, false precision. Run the code. |
| 3 | **Khu** — the Guardian Angel | Responsible for the subject; can be injured in his defense. | Steelman the defendant. The strongest honest case *against* the conclusion. Where is it unfair, asymmetric, or silent on the best counterargument? |
| 4 | **Ba** — the Heart, often treacherous | A hawk's body with your own face on it. Many a hero brought down by a perfidious Ba. | Motivated reasoning. Which findings get called robust and which fragile — and does that sorting track the thesis? Where does prose outrun evidence? |
| 5 | **Ka** — the Double | Reaches adolescence at bodily death; the only reliable guide through the Land of the Dead. | Reproducibility and chain of custody. Can a hostile stranger get from published claim to raw source? Do the scripts run? Are links and versions real? |
| 6 | **Khaibit** — the Shadow | Memory; your whole past conditioning from this and other lives. | Prior work and the record. What was published first, or contradicts this, and is uncited? Verify dates and quote attributions against primaries. |
| 7 | **Sekhu** — the Remains | The last soul. What is left. | Residue and decay. Strip every contested claim — what survives maximal hostile scrutiny, and is it enough? What hedges were lost in revision? |

</div>

<!-- TODO: a paragraph on why these seven and not some other seven. The honest
     answer is that the schema came first and the lenses were fitted to it —
     which is worth admitting, because the constraint is what produced lenses
     you would not have chosen deliberately (Ba and Khaibit especially). -->

## What each reviewer is actually sent

The lens is one line of a prompt. The rest is a contract, identical across all seven:

- **Identity and gloss first**, then the lens
- **Absolute paths** to every file they should read — reviewers otherwise burn their budget hunting
- **Enough domain context** to review without re-deriving it
- **A numbered priority order**, highest-value check first, plus an explicit instruction to *stop when they have enough to report rather than exhaust the list*. Agents that try to be complete get truncated before reporting anything.
- **"Do NOT edit any file."**
- **An output contract:** findings ranked most-severe first; file, quoted evidence, and the recomputation or command output; distinguish "this is wrong" from "I'd choose differently"; no praise sandwiches; say so if they ran out of room.

A filled-in prompt, for Sekem:

```
You are Sekem — Energy, Power, Light. In Burroughs' schema the Director gives
the orders and Sekem presses the right buttons. Your lens is EXECUTION AND
ARITHMETIC: not whether the argument is good, but whether the numbers under
it are right.

ARTIFACT
  Primary:     .../metro_relocation/report/finalists.md
  Methodology: .../metro_relocation/METHOD.md
  Code:        .../metro_relocation/src/score.py
  Data:        .../metro_relocation/data/processed/

CONTEXT
  A two-level scoring model (metro, then neighborhood) ranking US metros
  against a relocation brief, with a damping parameter lambda = 0.25 mixing
  the two levels. It reports 9 finalists. The claim under review is that the
  9 are stable across reasonable changes to the model.

PRIORITY ORDER — highest value first. Stop when you have enough to report.
Do NOT try to finish the list; agents that aim for completeness get
truncated before they report anything.
  1. Recompute every number in the finalists table from the processed data.
     Report each as expected vs. found.
  2. The lambda = 0.25 blend: are both levels normalized to the same scale
     before mixing, or does one enter the sum in raw units?
  3. Percentages vs. percentage points. For every "X% better" claim, name the
     denominator and say whether it is the one the sentence implies.
  4. Run src/score.py end to end; diff its output against the committed
     report. Report any drift.
  5. False precision: any figure carrying more digits than its input supports.

CONSTRAINTS
  Do NOT edit any file. You are reviewing, not fixing.

OUTPUT
  Findings ranked most-severe first. For each: the file, the quoted claim,
  your recomputation or the command output, and the corrected value.
  Distinguish "this is wrong" from "I would have chosen differently." No
  praise sandwich, no summary of what is fine. If you ran out of room for
  something important, name it.
```

Only **CONTEXT** and **PRIORITY ORDER** change between souls. Sekem's priorities are a checklist because recomputation is mechanical; Khu's are a sequence of questions, because a checklist cannot ask for an argument.

## Which lens needs which model

Observed rather than guessed. Most of the value is in the lens, not the model — but not uniformly.

<div class="tablewrap" markdown="1">

| Soul | Floor | Why |
|---|---|---|
| **Khu** | **opus** | Constructing the unanswered counterargument means holding the whole artifact in mind and reasoning past it. Highest yield in the set. |
| **Ba** | sonnet | Its finding is a pattern *across* the document — that the robust/fragile sorting tracks the thesis. Unavailable to a model reading section by section. |
| **Ren** | sonnet | Whether an argument has one spine or four, and whether the ending contradicts the middle, is whole-document reasoning. |
| **Sekhu** | sonnet | Must refuse claims the text presents confidently — strictness against the artifact's own framing. |
| **Khaibit** | sonnet | Search is easy; judging whether a hit is genuine uncredited precedent or merely on-topic is not. Also has to know when *not* to cry wolf. |
| **Sekem** | **haiku, if you enumerate** | Recomputation is faithful on a cheap model *provided the prompt lists what to recompute*. Conceptual traps need naming explicitly. |
| **Ka** | **haiku** | Almost entirely mechanical, and the slowest soul by wall-clock — here the cheap model is the fast one. |

</div>

Default is sonnet for the middle four, haiku for Ka, and opus for Khu regardless of what the flag says.

<div class="note">Seven concurrent agents can exhaust a session limit mid-flight. A dead agent is resumable by message if it persisted a transcript, and must be relaunched fresh if it did not — but it is never silently dropped. If a soul cannot run, the synthesis has to say which lens is missing.</div>

## Synthesis is the actual work

Seven reports is not a review. It is seven transcripts, and reading them all defeats the point. What the dispatcher owes you:

- **Convergence first.** A finding two or three souls reached independently, by different routes, is the highest-confidence defect in the set.
- **Then unique high-severity findings**, attributed.
- **Then conflicts.** Where Khu (defending) and Ba (prosecuting the author) disagree, the disagreement is itself the information. Surfacing it beats silently picking a winner.
- **Correctable defects separated from structural ones.** "This number is wrong" and "the argument is built in the wrong order" need different responses and very different amounts of your time.
- **Spot-checks, flagged.** Subagents assert confidently and are sometimes wrong. Arithmetic and quotes get verified before they are relayed; what was checked and what is being passed along unchecked are marked differently.

<!-- TODO: the payoff section. Candidates, pick one and make it the point:
     (a) the souls fail in different registers by design — Sekem returning
         "arithmetic is clean" while Ba returns "the sorting is biased" is a
         coherent result, not a contradiction;
     (b) Khu is the one worth reading in full, every time — a steelman of the
         thing you are criticising is the hardest review to get from one pass;
     (c) the general lesson: adversarial diversity beats model quality, and
         persona is a cheap way to buy diversity. -->

<!-- TODO: a concrete run. This piece needs one real example — an artifact put
     through all seven and what came back. Without it the post describes a
     machine rather than showing it working. The metadata-archaeology post or
     the metro relocation model are both candidates; the relocation model is
     stronger because it has arithmetic for Sekem to catch. -->

<!-- TODO: closing. Something that earns the description line about burning
     tokens to reach the Western Lands. -->

---

### Resources

- [The Western Lands](https://en.wikipedia.org/wiki/The_Western_Lands) — Burroughs, 1987; the seven-souls passage is in the opening pages
- TODO: link the command source if you decide to publish it
