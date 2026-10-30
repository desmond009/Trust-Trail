# Facilitator guide: consent screen study

For the team member running sessions. Plan about 15 minutes per participant: 10 minutes of
study plus consent and a short break.

## What the study compares

| | Keycloak default consent (baseline) | TrustTrail consent screen |
|---|---|---|
| What it is | Keycloak's own "Grant Access to … Yes / No" page, unchanged | a prototype screen served by TrustTrail at `/study` |
| Shows | scope names ("User profile", "Email address", "User roles") | each attribute in plain language, purpose, trust level, delete-by date |
| Choice | all or nothing | per attribute, nothing pre-ticked |

Each participant does both screens, two tasks on each:

- **Task P:** share some, not all (department, programme and year, but not email or roll
  number). Only the TrustTrail screen can express this.
- **Task F:** share everything the service asks for. Both screens can do this, so the baseline
  isn't set up to fail every task.

Order is counterbalanced by participant number. Odd codes see Keycloak first, even codes see
TrustTrail first, and the task order alternates in pairs (P01–P02 do P then F, P03–P04 do F
then P, and so on). **Give out codes in order** so the four groups stay balanced.

## What we measure

1. **Did you choose what you intended?** Recorded automatically: what the service ended up
   with, compared with what the task asked for.
2. **Comprehension:** after each task, "Which of these does the service now have?" is
   scored against what it really got.
3. **Screen questions:** after each screen, the stated purpose and retention period, plus
   three 1–5 agreement items and an optional comment.

## Before the first session

- [ ] Ethics or instructor sign-off obtained, if IIIT Dharwad requires it (see `data_handling.md`)
- [ ] Stack running and seeded (`docker compose up -d`, then the seed step from the README)
- [ ] `.venv/bin/python scripts/check_study.py` passes (it uses the reserved codes P98 and P99)
- [ ] **Pilot with one teammate** who didn't build the screens, using code `P99`; fix wording
      in `config/study.yaml` if anything confuses them, then re-run the check
- [ ] Printed: consent forms, data-handling notes, code slips (P01, P02, …), and the sign-up sheet
- [ ] Browser: use one browser window per session, at http://localhost:8000/study

## Session script

1. **Welcome (1 min).** "Thanks for helping. We're testing *screens*, not you; there are no
   wrong answers about your preferences. You'll play an invented student, so nothing is about you."
2. **Consent (2 min).** Hand over the consent form and the data-handling note. Answer
   questions. If they decline, thank them and stop. Keep the signed form apart from the laptop.
3. **Start.** Type the next code from the sheet at `/study` and turn the laptop to them.
4. **Don't help** with the screens themselves. If asked "what should I click?", say "do
   whatever you think matches the task". You may re-read the task aloud. If the Keycloak page
   asks for a login, they use the demo account shown on the task card.
5. **Note-taking (optional).** Write down hesitations or remarks against the code, never a name.
6. **End.** At the "Thank you" page, give them their code slip (needed if they want their data
   deleted) and press "Next participant".

Between participants nothing needs resetting. Keycloak's consent page is forced on every
baseline task, even though everyone uses the same demo account.

## After all sessions

```bash
docker compose exec trusttrail python -m eval.analyze_study    # tables in eval/results/study.md
```

Report n, the tables, and the limits section the script prints, as they are. With 15–20
classmates the results are **indicative only**. Say so in the report, together with these
threats to validity: a convenience sample of students who know the team; a team member as
facilitator; an invented persona; a prototype screen; and task P being impossible on the
baseline screen by design.

Then follow the deletion steps in `data_handling.md`.
