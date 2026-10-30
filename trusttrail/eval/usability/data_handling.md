# Data-handling note: consent screen study

This note says what the TrustTrail usability study collects, where it is kept, who can see it
and when it is deleted. Give it to participants with the consent form; the team follows it.

## What is collected

| Data | Example | Why |
|---|---|---|
| Participant code | `P07` | to keep one person's answers together |
| Screen shown, task, choice made | "TrustTrail screen, task P, shared department + year" | did people choose what they intended? |
| Time to decide | 4.2 s | context only |
| Answers to the questions (multiple choice, 1–5 scales) | "Until 28 April 2027" | did people understand what was shared? |
| Optional comment | free text | qualitative feedback |

**Not collected:** names, roll numbers, emails, phone numbers, IP addresses, device details,
screen recordings. The study pages don't log IP addresses, and every login uses the same
invented demo persona.

The signed consent forms (paper or a separate scan) are the **only** link between a code and
a person. They are stored apart from the answers.

## Where it is kept

- Answers are in `study.db` inside the TrustTrail Docker volume on **one team laptop**, which
  is password-protected. They are not on any cloud service.
- The analysis script writes anonymised CSVs and a summary to `trusttrail/eval/results/`.
  Those files contain codes and answers only. Free-text comments go in a separate file
  (`study_comments.csv`), so they can be left out of anything shared.
- Consent forms are kept by **[team member]**, in **[place, e.g. a sealed envelope or a private folder]**.

## Who can see it

The three team members and, if asked, the course instructor. The report shows only group
numbers and unattributed quotes.

## Deletion

- **On request:** until **[date]**, a participant can ask for their answers to be deleted, by
  code. The team deletes their rows from `study.db` and records that it did so (code and date
  only).
- **After the report:** once the report is graded (expected **[date]**), delete the raw data:
  ```bash
  docker compose exec trusttrail python -m eval.analyze_study --delete-all --yes
  ```
  Then shred or delete the consent forms. Keep only the aggregate tables used in the report.
- `docker compose down -v` also deletes the volume that holds `study.db`.

## Before running the study

- **Check with your instructor whether IIIT Dharwad requires ethics approval** (or a
  departmental sign-off) for a study with classmates, even a minimal-risk one. Do this before
  recruiting.
- Recruit 15–20 classmates by open invitation. Nobody who is graded or assessed by a team
  member should be asked directly, and nobody should be pressured.
- Don't run sessions on a laptop that also holds unrelated personal data in the same Docker volume.
