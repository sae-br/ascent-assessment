# Assessments App Specifications

This app handles the full lifecycle of the assessment itself, from setup and email distribution to response collection and scoring (the scores get passed to Reports).

Right now it's set up using the OrgHealth Ascent Model, but the models, questions, and scoring can all be adjusted for different IP.

## Features

- Admins can create new assessments for specific teams
- Team members receive unique links to submit their responses
- Questions are grouped under "Peaks" (key categories)
- Responses are scored, grouped, and analyzed

## Models

### Peak

Represents a category or theme that groups questions.

name: Unique name for the peak (e.g. "Trust", "Clarity")

### Question

Belongs to a Peak and defines a prompt users respond to.

peak: ForeignKey to Peak
text: The question itself
order: Integer used to control display order

### Answer

Stores each team member's response to a question.

team_member: ForeignKey to TeamMember
question: ForeignKey to Question
value: Integer between 0–3 (Likert scale)
submitted_at: Timestamp of submission

Unique constraint ensures one answer per member per question.

### Assessment

Represents a specific cycle of feedback for a team. One assessment = one report. The same team might do another assessment at a future date, which will be a different assessment as per this model.

team: ForeignKey to Team
deadline: Deadline for submission
created_at: Timestamp of creation


## Views

### Admin Views

new_assessment – Select team and deadline to set up a new assessment
confirm_launch – Preview and send invites to team members with unique tokens

### Respondent Views

start_assessment – Accessed via token, displays questions to the unique respondent
submit_assessment – Confirms submission (optionally separated route)


## Email Flow

- Triggered from confirm_launch
- Uses each team member's unique_token to send them an individualized survey link
- Link structure: /assessments/start/<uuid:token>/


## Scoring Logic

(As per this incomplete MVP using the Ascent Model) 8 questions, grouped under 4 Peaks (2 questions per peak)

Scoring is on a 4-point scale:
- 3 = Consistently true
- 2 = Somewhat true
- 1 = Somewhat untrue
- 0 = Consistently untrue

Reports aggregate the data of the whole team, presenting:
- A percentage score for the team per peak
- A percentage score for the team per question
- Overall visualization is based on all submitted answers

See the README in Reports for other specifics.


## Notes for Development

- Adding new questions or peaks requires updating the database (no dynamic form builder yet)
- Tokens are managed in the TeamMember model
- All templates/assessments/ are organized by view


## URL Patterns

```python
urlpatterns = [
    path('start/<uuid:token>/', views.start_assessment, name='start_assessment'),
    path('submit/', views.submit_assessment, name='submit_assessment'),
    path('assessments/new/', views.new_assessment, name='new_assessment'),
    path('assessments/confirm/', views.confirm_launch, name='confirm_launch'),
]
```

This is a core app in the project and tightly integrated with teams, reports, and dashboard. Changes to its models or views may affect downstream features.
