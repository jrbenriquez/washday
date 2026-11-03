---
name: "plan-work"
description: "Plan a piece of work from idea to hand-off: discuss to a shared vision, build and iterate a clickable prototype, then package a reference zip (agent README, PRD, prototype). Use for any app, site or tool idea, prototype, PRD, or extension of an existing app."
---

# Plan a piece of work

Turn an idea into three things a coding agent can build from: a shared vision, a preview of the result the user has approved, and a reference package (agent README, PRD, preview files).

"The work" can be a new app, site or tool, or a change to something that already exists: a feature, a layout, a section, a restructure. How the result is previewed depends on which (see Phase 4).

The work moves through phases with **gates**. The user opens each gate; you never skip one.

| Phase | What happens | Gate to leave it |
| --- | --- | --- |
| 0. Situation | New build, or a change to something existing? | Known |
| 1. Discovery | Conversation and questions until nothing important is unclear | No open gaps |
| 2. Vision brief | One-page summary of the agreed vision | User confirms the brief **and** says to build the preview |
| 3. Directions (optional) | 2–3 distinct visual directions | User picks one or a mix |
| 4. Preview | Show the proposed result: a clickable prototype for new work, the change inside the existing app otherwise | Shown to the user |
| 5. Revision loop | Discuss each change, then update the preview | User says they are satisfied and want the package |
| 6. PRD | Requirements document, decisions resolved | Written |
| 7. Package | `README.md` + PRD + brief + preview, zipped and checked | Delivered |

Why the gates matter: building before agreement wastes a preview on a guess, and packaging before the user is satisfied freezes a design they still want to change. Saying which phase you are in ("Discovery, round 2") keeps the user oriented.

---

## Phase 0: Situation

Find out which of these applies, from the conversation or by asking:

- **New build.** Nothing exists yet: a new app, site or tool.
- **Change to an existing app.** A repo, live site or earlier package already exists, and the work adds a feature, a layout (for example desktop for a mobile-only site), a section, or restructures what is there.

For a change, also learn: the existing data model or CMS records, what is live, and what must not change. This changes the PRD's shape (see Phase 6). If the user shares a live URL, try to load it so your suggestions match what is actually there.

**Record the existing stack precisely.** Note the frameworks and their versions, the database, the package manager, the build tooling, and conventions such as project layout, template or component patterns, test tools and lint rules. When the repo is available, read it from the source of truth: `pyproject.toml` or `requirements*.txt`, `package.json` and its lockfile, settings files and the existing app structure. Otherwise ask the user. This record is what the plan must follow (see Stack policy).

**Note how the repo can show its own output.** Look for what already exists for running or previewing it: a local dev server and seed data, a style guide or component library page, Storybook, preview deployments, end-to-end test tooling that can take screenshots, and any skills, commands or scripts the repo provides for these. Phase 4 uses them.

## Phase 1: Discovery

Start by restating the idea in a few lines, in the user's words, so they can correct you early.

Then ask in **rounds of 3–5 numbered questions**, grouped, each with a **suggested default**, so the user can reply "defaults" or change only what they disagree with. Stop when nothing important is unclear; do not ask about things with an obvious default or that you can check yourself.

Cover only the areas that are still unclear:

- **People.** Who uses it, how many, and who edits content versus who only reads it.
- **Core jobs.** The 3–5 things it must do well. Push for specifics ("move a project to the next step in one tap"), not features in the abstract.
- **Devices and context.** Phone, desk or both, and the real setting: one-handed at a workbench, a long desk session. Ask for the split ("50/50 phone and desk").
- **Content and data.** What is stored, what is editable, whether it needs a CMS, which units and currency apply, and what sample data looks like.
- **Look and feel.** Existing brand documents, reference images, sites they like, the feeling it should give. For a change to an existing app, the app's current design is the starting point.
- **Stack.** Apply the Stack policy below. For a change to an existing app, the stack is inherited, so confirm what you recorded rather than proposing anything. For a new build, ask what the user or the project has already chosen, then fill only the gaps from the preference table and say which parts are defaults.
- **Scope.** What is in this round of work, and what is explicitly later.
- **Integrations.** Sign-in, email, payments, file storage, external services.

**Volunteer ideas.** Users often know their problem better than the solution space. Suggest what work of this kind usually needs or what would save them time: templates, undo, a timer, unit-based costing, a board view. Label these as suggestions, explain the benefit in a line, and let the user pick.

**Handling decisions with real impact.** When a choice has trade-offs the user may not see (a breakpoint, whether text shows on mobile, a data model choice), lay out:

- what is happening, in plain words
- the options and what changes with each (a small table helps)
- your recommendation and why

Then let the user decide. Record every decision; it goes into the brief and the PRD.

**Gaps and contradictions.** If two answers conflict, or an instruction could mean two different builds, ask. A wrong guess on something expensive to redo costs more than a question.

An unresolved material stack change counts as an open gap: discovery isn't finished until it is decided.

## Phase 2: Vision brief

When discovery settles, write a one-page brief. Make it an editable doc if a document tool is available; otherwise put it in the reply. Use this shape:

```markdown
# <Name of the work> — vision brief

**What it is.** One or two sentences. For a change, also what exists today.
**For whom.** Users, how many, and their context (devices, setting).
**Core jobs.** 3–5 numbered, specific jobs.
**Scope.** Bullets. **Later:** bullets.
**Look and feel.** Direction in a few words, plus brand constraints and references.
**Devices.** Primary device, secondary device, and how each should behave.
**Stack.** Each layer with its source: inherited from the existing app, chosen by the user, or a default from the preference table. Note any approved material stack change and why.
**Preview.** How the result will be shown (Phase 4): a clickable prototype, or the change running in the existing app.
**Decisions so far.** Bullets.
**Open questions.** Only ones that do not block the preview.
```

Then ask both questions explicitly: *Does this match what you have in mind? Should I build the preview?* Wait for a yes before building.

## Phase 3: Visual directions (optional)

For visual-heavy work (marketing sites, brand-led apps, anything where "how it feels" is the point), offer 2–3 **distinct** directions as quick mockups, not colour variations of one layout. Use a design canvas if one is available, otherwise one HTML page. Give each direction a name and a one-line trade-off, and recommend one or a combination.

For tools, utility apps and changes that should match an existing design, skip this phase unless the user asks.

## Phase 4: Preview the result

Show the user the proposed outcome so they react to the real thing, not a description. The form depends on the situation from Phase 0.

### New build: a clickable prototype

Build a **working** prototype, not a static mock. The user should be able to tap through the real flow.

**Format.** The prototype is a design reference, not a stack choice: it is plain HTML whatever the app will be built with, and it never implies a stack. One self-contained HTML file per surface: vanilla HTML, CSS and JavaScript, with no build step. Use a CDN script only when the design needs it (for example three.js for 3D). If an artifact or publishing tool exists, publish the prototype so the user can open it on their phone and desktop; otherwise send the file. If mobile and desktop differ substantially, they can be separate prototypes; say which one is primary.

### Change to an existing app: show it in the app

A standalone prototype of an existing app drifts from the real thing: different markup, fonts, data and edge cases. Show the change in the app itself instead, using what Phase 0 found:

- **Prefer the repo's own ways of showing output:** its dev server with seed or fixture data, its component or style-guide pages, Storybook, a preview deployment, or its end-to-end tooling to capture screenshots at phone and desktop widths. Use the repo's own skills, commands and scripts for these when it has them.
- **Keep the preview disposable.** Work on a separate branch named for the preview (for example `preview/stories-collection`). Use stubbed or hard-coded content, template-only changes and fixture data where possible. Don't run migrations against shared databases, don't deploy to production, and don't merge. The real implementation happens later, from the PRD.
- **Share it in a form the user can open:** a preview URL, or screenshots and a short screen recording if the user can't run the app, plus how to run the branch locally.
- **Fallback:** if you can't run the app (no repo access, no working environment), build an HTML mockup from the app's real CSS, templates and content rather than an invented look, and say that it is a fallback.

### Work with no user interface

For work without a UI (an API, a data pipeline, an integration, a command-line tool), the preview is whatever shows its output best: example requests and responses, a sample of the output data, a command-line transcript, or a sequence diagram. The same gates apply.

### What a good preview includes (lessons from earlier projects)

- **Working interactions.** Navigation, the primary actions, forms with validation and error states, and feedback such as toasts (with undo where a change is easy to regret).
- **Realistic sample data, clearly marked as examples.** Open on a realistic working state, never an empty shell. If a prototype saves to browser storage, add a "Reset sample data" control.
- **Placeholders for unknown facts.** Put anything you don't know in brackets: `[₱ PRICE]`, `[City]`, `[Maker name]`. Never invent real prices, real people's names or claims about the product.
- **Phone and desktop both considered.** Design the primary device first. Nothing may break on the other: no horizontal scroll, and no phone-width column stranded on a wide screen.
- **Deliberate design** (new builds; changes follow the existing design).
  - Put design tokens in `:root`.
  - Choose a palette and type specific to the subject.
  - Include one signature detail from the subject's own world. Examples from earlier projects: progress drawn as saddle stitches for a leather workshop, and a held photograph with the story scrolling past it.
  - Keep motion to one orchestrated moment and respect `prefers-reduced-motion`.
- **Accessibility basics.** Real buttons and links, labelled inputs, touch targets of at least 44 px, visible focus.
- **Standalone-file safety** (HTML prototypes and fallbacks). Put `<meta charset="utf-8">` in the file and `[hidden] { display: none !important; }` in your own CSS. Hosted previews often add these, but a downloaded file won't have them. Without them, symbols like ₱ turn into garbage characters, and menus or dialogs that toggle `hidden` stop closing. Both bugs have happened on earlier projects.
- **Image stand-ins.** If the user gives a reference image, you may crop stand-in photos from it and say they are low-resolution stand-ins.

### Self-check, once

If a headless browser is available (for example Playwright, or the repo's own end-to-end tooling), render the main screens at 390 px and 1440 px. Check for:

- console errors
- horizontal overflow (`scrollWidth` greater than the viewport)
- elements that should be hidden but are visible
- failed image loads

Fix what you find, then show the preview. Don't loop on checks.

### Present it

Say in a few lines what to try (the flows worth tapping), which values are placeholders or stand-ins, and that the data is sample data. For an in-app preview, also say which branch it is on and how to run it. Then ask: *Want any changes, or is it ready for the reference package?*

## Phase 5: Revision loop

Every change request is a small discovery round:

- **Clear, small change** (a colour, a label, a bug): make it and update the same preview so the link or branch stays the same. For a bug, say the cause in one line.
- **Ambiguous change, or one with impact** (a new screen, a layout change, a new data concept): restate it, ask the few questions that close the gaps (with defaults), agree, then update the preview.
- **Direction-level change:** go back to the brief, update it and confirm it before rebuilding.

Repeat for as long as the user wants. After each update, ask again whether it is ready for the package. **Do not build the package until the user clearly says they are satisfied** ("I'm happy with this", "let's do the PRD", "package it").

## Phase 6: PRD

Write the PRD once the preview is approved. If a doc tool exists, make it an editable doc so the user can comment, and **always** produce a Markdown copy for the package. Keep the two in sync: if the doc changes later, re-export it and re-package.

**Division of authority** (state it in the PRD and the README): the preview is the source of truth for visual presentation, layout, copy tone and interaction design; the PRD is the source of truth for functional rules, validation, state changes and data. If they disagree on functional behaviour, the PRD wins.

### PRD for a new build

1. **Overview.** Goal, user, reference files, 3–4 goals, measurable success criteria.
2. **Scope.** In this round of work, and out of scope.
3. **Tech stack and architecture.** A table of layer, choice, source (user choice or default) and notes. List the apps or modules, and the URLs or routes.
4. **Data model.** Models and key fields in a table, plus a diagram (Mermaid `erDiagram` in the Markdown copy). Note what is copied versus linked (for example library items copied into a project so later edits don't change old records). Mention money and decimal precision and the units.
5. **Screens and behaviour.** Map each screen to the prototype: what it shows and what each control does on the server.
6. **Rules.** Status transitions, formulas (written out), timers, templates, undo: anything the prototype does in JavaScript that the server must reproduce exactly.
7. **Design system.** Tokens (light and dark if both exist), typography, signature details to keep, mobile rules, and the template or partial structure.
8. **Non-functional.** Speed, mobile, files, accessibility, security, data safety, testing.
9. **Delivery.** An acceptance checklist, milestones in build order, and a **Decisions** list.

### PRD for a change to an existing app

Use the same idea, but replace sections 3–5 with these:

- **Constraints.** What must not change, and which records and content are reused. Start with the inherited stack: frameworks, versions, database, package manager and conventions the agent must follow, and the rule that no new framework or dependency is added without approval.
- **Content mapping.** Every new element traced to an existing field or block, or derived in a template. Allow at most a handful of *optional, additive* new fields, each with what happens when it is left empty.
- **Preview to production.** Name the preview branch and say what in it is throwaway (stubbed content, hard-coded data) versus what the real implementation keeps.
- **Scope of change.** A two-column table of what the agent may touch and what it must leave alone. Coding agents tend to "improve" nearby code unless told not to.
- **Migration safety.** Additive migrations only. Every new field optional. Content moves in a separate, idempotent command with a dry-run mode, never in a migration. Test against a copy of production data. Keep migrations in their own commit.
- Add acceptance checks that existing records render with no editor action, and that nothing outside the scope list changed.

### Resolve open questions before packaging

Before packaging, list any remaining open questions to the user. Explain each one's impact as in Phase 1, recommend an answer, and record the outcome under **Decisions**. A package with unresolved questions makes the coding agent guess.

## Phase 7: Reference package

Build one zip for a coding agent:

```
<work>-reference/
├── README.md            # the agent's starting point (template below)
├── docs/
│   ├── PRD.md
│   ├── brief.md
│   └── <user's brand or positioning docs, earlier PRDs, if any>
├── prototype/           # new build: the HTML prototype (or mobile/ and desktop/)
│   └── index.html       # references images by relative path
├── preview/             # change to an existing app: screenshots, recording, run notes
└── img/                 # shared images, if any
```

For a new build, also deliver `<work>-standalone.html`, a single file with images embedded, for double-click viewing. Tell the user the zip is for the agent and the standalone file is for viewing, because embedded images bloat the code an agent would read. For an in-app preview, the README names the preview branch, and `preview/` holds screenshots at phone and desktop widths.

**README template:**

```markdown
# <Name of the work> — reference package

<One paragraph: what the work is, who it's for, what exists today if it's a change, and what this package is for.>

## Start here
1. Read `docs/PRD.md`: what to build, stack, data model, rules, acceptance criteria.
2. Look at the preview: open `prototype/index.html` at <390 px and/or 1440 px>, or run branch `<preview branch>` (see `preview/`). It is the source of truth for visual presentation and interaction design.
3. `docs/brief.md` (and any brand docs) decide unclear design choices.
When the PRD and the preview disagree, the PRD wins on functional rules, validation, state changes and data; the preview wins on visual presentation and interaction design.

## Ground rules
- <Stack rule. Existing app: "Follow the existing stack and conventions (see the PRD); add no framework or dependency without approval." New build: the chosen stack, for example "server-rendered Django + Hotwire, no React, no bundler".>
- <Scope rule for changes: see the PRD's Scope of change. For an in-app preview: "The preview branch is throwaway; implement from the PRD.">
- Sample data and bracketed placeholders are not real data. Don't ship them or invent values for them.

## How the preview maps to the real work
| Preview | Real implementation |
| --- | --- |
| <JS state / stubbed content / fixtures> | <models, CMS records> |
| <sample data> | <seed management command> |
| <client-side or hard-coded rules> | <server rules in the PRD> |

## Notes
- <Image stand-ins, fonts to self-host, currency and units, anything easy to get wrong.>

## Next step
Extract this package into the consuming repository, keeping its files together. With `to-outcomes` installed, ask:
`Use to-outcomes to split <path-to-this-package>/docs/PRD.md. Name the general outcome "<Name of the work>".`
Review the generated outcomes, then explicitly request execution:
`orchestrate-work for outcomes/<general-outcome-name>`
```

**Verify before sending:**

- List the zip's contents.
- Open each HTML file headlessly if possible and confirm no console errors and no failed image loads.
- Confirm the README's file paths and branch names exist.

Then send the zip (and the standalone file, for a new build) with a line of context each.

Explain the next step from the README: extract into the consuming repository, use `to-outcomes` on the packaged PRD, review the outcomes, then explicitly invoke `orchestrate-work`. Package delivery does not start decomposition or execution. This planning package is not a runtime phase result and needs no `HANDOFFS.md` or `.agents/work/` state.

**After delivery:** if the PRD or the preview changes, update the doc, the Markdown copy and the zip together. Tell the user which file replaces which.

---

## Stack policy

Stack preferences are **fallbacks, not requirements**. What already exists, or what the user has chosen, always comes first.

- **Existing app:** follow its frameworks, database, package manager, versions and conventions. Don't propose replacements or "better" alternatives as part of the plan.
- **New feature in an existing app:** inherit that app's stack, including how it already does similar things (for example, if it uses HTMX for partial updates, the feature does too).
- **New build:** use the preference table only for layers the user or the project hasn't already chosen. Say which choices are defaults so the user can change them.
- **Material stack change:** if the vision seems to need something the current stack doesn't provide, stop and resolve it before continuing. Material means a new framework, language, database, frontend approach (such as adding React to a server-rendered app), build step, or hosting or deployment model. A small library that fits existing conventions is not material, but still list it in the PRD. To resolve it:
  - explain what the vision needs that the current stack can't do well
  - show the options, including a way to stay within the current stack, and what each costs (complexity, maintenance, migration, learning)
  - recommend one, let the user decide, and record the decision in the brief and the PRD

  Don't build the preview or write the PRD around an unapproved stack change.

### Preferred defaults by type of work

Use these only to fill gaps, following the policy above. If no row fits, ask, and offer to record the answer here as a new preference.

| Type of work | Preferred stack | Notes |
| --- | --- | --- |
| Web app or site (server-rendered) | Django, PostgreSQL (SQLite for local dev) | Default for anything web |
| Content-managed site | Django + Wagtail (StreamField blocks, page types with default content, site settings) | Editors manage everything; design stays locked through fixed blocks with no style fields |
| Typical interactivity | Hotwire (Turbo + Stimulus) or HTMX | App-like speed without a SPA; no bundler |
| Deeply interactive client-side app (rich editors, heavy canvas, complex real-time UI) | React, with Vite if a build step is justified | Only when server-rendered interactivity would fight the design |
| 3D or immersive | three.js | Through a CDN in prototypes |
| Sign-in for personal or single-owner apps | django-allauth with Google, restricted to an allow-list of emails | Quick and safe |
| Native mobile app | No preference yet | Ask |
| System architecture and infrastructure plans | No preference yet | Ask |
| DevOps, hosting and deployment | No preference yet | Ask |

---

## How to talk to the user

- Write in plain language; explain jargon in a few words when it matters to a decision.
- Recommend, then let the user decide; record decisions.
- Keep messages short. Put long material (briefs, PRDs, previews) in documents and files, not in chat.
- At each gate, ask the gate question explicitly and wait for the answer.
