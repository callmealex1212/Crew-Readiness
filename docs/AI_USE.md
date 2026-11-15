# Use of Super Intelligence (SI) / AI assistance (task N3)

**Status: draft for Davud to review before submission.** The Space Apps guide asks teams to say clearly where and how SI tools were
used, and says SI should not be used to come up with the idea of how to solve the challenge. This is the account, neither overstated
nor hidden.

## Paste-ready answer (for the "Use of Super Intelligence (SI)" field)

Yes. We used AI coding assistants as tools; the idea and every decision were the team's.

- **Who decided what.** The team lead set the direction before any code was written: decision support that compares each person
  only with their own usual pattern, a human always decides, privacy first, and no claims about health. The team lead made every
  product and claim decision, and ran the volunteer pilot with a teammate. The volunteers' sessions are real; the AI did not
  produce any pilot data. It did help check the pilot files and correct one volunteer's session labels to match what was
  recorded (stated in the pilot data pull request).
- **What the AI did.** An AI coding assistant (Claude, by Anthropic, used through Claude Code) wrote much of the code, the tests and
  the documentation, and proposed some features that the team lead reviewed and approved. A second Claude Code session, run by our
  teammate Alex, wrote the attention check, the Privacy & limits page, keyboard and phone fixes, the pilot tooling, the NASA data
  search and the NASA bed-rest analysis script, the self-test and the backup tool. AI also helped draft submission text, which the
  team edited.
- **Images, audio, video.** The product contains **no AI-generated image**. An earlier AI-generated logo was removed on 2026-11-15
  and replaced by a mark drawn in code. The other images are a public-domain painting and a NASA photograph (see References).
  There is no AI-generated audio or video.
- **Code and data.** AI-written code is acknowledged here, at the top of the README and in the page metadata
  (`<meta name="ai-assistance">`). Every number shown is produced by code from a result file (simulated benchmark, the volunteer
  pilot, the NASA bed-rest analysis), not typed by hand or by an AI.
- **Inside the product.** The running app calls no AI service. Its "machine learning" is classical statistics (robust medians, a
  count model, bootstrap intervals).
- **No NASA branding** (logos, insignia, mission identifiers) appears in any generated content.

## Where to see it
- Privacy & limits page, section "How AI was used" (`/about#ai-use`).
- `README.md`, top paragraph.
- Page metadata on every page: `<meta name="ai-assistance" ...>`.
- Commit history: AI-written commits carry a `Co-Authored-By: Claude` line.

## For Davud to check before submitting
1. The Privacy page calls the teammate's agent "a second coding agent"; it is also Claude (Claude Code). If you want the page to
   match this file word for word, that is a one-line change in `app/templates/about.html` (owned by Claude).
2. The list of what the teammate's agent wrote comes from that session's own pull requests; correct anything you remember differently.
