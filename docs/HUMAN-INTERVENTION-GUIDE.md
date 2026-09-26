# When Consul Needs You

Consul works a brief on its own, turn after turn, and stops for you only when something truly needs a person: an account step, a key, a decision, or a review you asked to keep. This guide lists every such moment and what to do.

## How it asks

A specialist that hits something it can't resolve raises a **blocker**. The runner writes it into the brief under `## Blockers` with the context, the options it sees, and an empty `Resolution:` line, then keeps working on everything that doesn't depend on it. Only when nothing runnable is left does the brief move to `briefs/3-blocked/`, with the announcement **NEEDS HUMAN INTERVENTION**. That is a separate outcome from done and is never reported as success.

You answer in one of two ways.

- **In the chat.** In Quick Start projects the runner asks a short question with two or three options and a recommendation. Reply in plain words; it writes your answer onto the `Resolution:` line and continues.
- **In the brief.** Write your answer on the blocker's `Resolution:` line yourself, then run `/orchestrate`. The brief moves back to `2-active/`, your decision goes into the Progress Log, and the blocked work is re-planned.

`/status blockers` lists every open question at any time.

## The moments

| Moment | What you'll see | What to do | Avoid it by |
|---|---|---|---|
| **Render credential** | An `external-action` blocker about a missing or rejected key | Create an API key (Render → Account Settings → API Keys), then `python3 ~/consul/onboard.py --set-render-key` | Letting `/start` store the key once per Mac |
| **Provisioning failed** | The provisioner's `[FAIL]` line and its `→ fix` | Fix the named cause (a card in Render → Billing, or Render → Account Settings → GitHub → allow the repo), then `python3 .claude/scripts/provision.py` | The wizard provisions at onboarding; if it passed then, this doesn't happen |
| **Sign-in keys (Clerk)** | Missing `CLERK_SECRET_KEY` or `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | `python3 .claude/scripts/provision.py --set NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_... --set CLERK_SECRET_KEY=sk_...` | Pasting the keys when the wizard asks |
| **Other secrets** | A list of keys a feature needs (Stripe, email, and so on) | Create the account, then `provision.py --set KEY=VALUE` for each | Naming third-party services in the brief and having keys ready |
| **Push to deploy** | "Code committed. Run `git push` to deploy." Only with push policy `human` | Review with `git log` and `git diff`, then `git push`; Render deploys and Consul verifies the new version is live | Quick Start's `consul` push policy, where the runner pushes |
| **Custom domain** | A DNS verification failure | Add the record the blocker names at your registrar and wait for it to propagate | Nothing; DNS takes its own time |
| **Unclear requirement** | The ambiguity and the options, e.g. "share by link, share to users, or both?" | Pick one | Acceptance criteria that say how you'll know it works, and an Out of Scope list |
| **Design choice** | Two or three options with trade-offs | Pick one, or say what matters | Stating preferences under Technical Constraints |
| **Repeated failure** | A subtask that failed three times, with each attempt's error | Fix the cause, or change the requirement with `/spec update`; the attempt count resets | Rare; usually an environment gap `/preflight` would have caught |
| **Design direction (optional)** | Nothing; the frontend worker writes `session/design-direction.md` and continues | Read it after the first frontend subtask; `/spec update` if it's off | Describing the product's world well in the wizard |

## Before a long run

`/preflight` (or `python3 .claude/scripts/preflight.py`) checks the tools, the GitHub remote, the Render credential and its workspace, every service and database in `render.yaml`, the secrets, and the health endpoints. Each FAIL comes with its fix. The runner also runs it when it pulls a brief from the backlog and parks any failure as a blocker, so a missing account step surfaces in the first minute instead of several turns in.

Then write the brief with care. Specific acceptance criteria and a clear Out of Scope list prevent most `unclear-requirement` blockers, and they are the only ones that cost you real thinking time.
