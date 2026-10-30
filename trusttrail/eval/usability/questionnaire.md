# Questionnaire: paper backup

The study app asks these questions on screen and scores them automatically
(`trusttrail/app/study.py`, wording in `config/study.yaml`). Use this printout only if the
laptop fails mid-session; then enter the answers by hand. The answer key is at the end, for
the team only, so don't hand that page to participants.

Participant code: P __ __    Screen: ☐ Keycloak  ☐ TrustTrail    Task: ☐ P  ☐ F

## After each task

**1. Which of these does the [Learning System / Examination Portal] now have?** Tick all that apply.

☐ Your full name ☐ Your email address ☐ Your roll number ☐ Your department ☐ Your programme
☐ Your year of study ☐ An ID that only this service uses
☐ Your university account ID (the same for every service) ☐ Nothing at all

**2. How sure are you?** (1 = guessing, 5 = completely sure)  1 ☐ 2 ☐ 3 ☐ 4 ☐ 5 ☐

## After both tasks on one screen

**3. What did the Learning System say it would use your data for?**
☐ Enrol you in the courses of your department, programme and year.
☐ To show you advertising from partner companies
☐ The screen did not say
☐ I don't know

**4. Until when may the Learning System keep your data?**
☐ Until [date shown on the screen] ☐ For as long as it likes ☐ The screen did not say ☐ I don't know

**5. How much do you agree?** (1 = strongly disagree, 5 = strongly agree)

| | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|
| I understood exactly what I was agreeing to share. | ☐ | ☐ | ☐ | ☐ | ☐ |
| I could share exactly what I wanted to. | ☐ | ☐ | ☐ | ☐ | ☐ |
| I would be comfortable using this kind of screen for real university services. | ☐ | ☐ | ☐ | ☐ | ☐ |

**6. Anything else?** (optional; please no names) ______________________________________

---

## Answer key (team only)

**Q1** is correct when the ticks match exactly what the service received:

| Screen | Choice | The service received |
|---|---|---|
| Keycloak | Yes | name, email, roll number, department, programme, year, university account ID |
| Keycloak | No | nothing |
| TrustTrail | Share selected | the ticked items + "an ID that only this service uses" |
| TrustTrail | Don't share anything | nothing |

The Keycloak page lists only "User profile, Email address, User roles", but this client also
receives roll number, department, programme and year through attribute mappers. That gap is
exactly what Q1 measures.

**Q3 and Q4:** Keycloak → "The screen did not say"; TrustTrail → the stated purpose and the
delete-by date.

**Did they choose what they intended?** Task P: exactly department, programme and year were
shared. Task F: all six items were shared.
