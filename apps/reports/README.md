# Reports App

This app is responsible for generating visualized summary reports based on responses submitted through the assessments app. Reports are grouped by team and organized by “peaks” (assessment categories).

## Functionality Overview
	•	Lists all teams with available assessments to generate reports.
	•	Displays percentage scores for each peak and each question within a peak.
	•	Calculates these scores using all team member answers — not averages of individuals.

## Models

All range-based models use one of:
- LOW
- MID
- HIGH

These labels are defined as constants and shared across models to ensure consistency.

### ResultsSummary

Stores short insight text based on the combination of the highest and lowest scoring peaks.
- Includes a summary_type to optionally support other summary categories later.
- Only one entry per (high_peak, low_peak) combo.

### PeakRange

Describes a range for a peak’s score (e.g., LOW = 0–33%, MEDIUM = 34–66%, HIGH = 67–100%).

### PeakInsight

Text block offering a short interpretation of the team’s result for a given peak in a specific score range.

### PeakAction

Suggested leadership actions based on score range for a given peak.

## Views

generate_report
	•	URL: /generate/
	•	Purpose: Presents a form to choose a team to generate a report for.
	•	Template: reports/generate.html

review_team_report_redirect
	•	URL: /team_report/
	•	Purpose: Simple redirect handler that grabs team_id from GET parameters and sends user to the correct team report URL.

review_team_report
	•	URL: /team_report/<team_id>/
	•	Purpose:
    	•	Fetches the specified team and its members.
    	•	For each peak:
            •	Retrieves all questions under that peak.
            •	Aggregates all answers submitted by that team’s members.
            •	Calculates a percentage score per question and per peak:
                •	question_score = total_score / (responses * 3) * 100
                •	peak_score = sum(question_scores) / max_possible_score * 100
            •	All scores are rounded to whole percentages.
        •	Passes the full dataset to the report template.
	•	Template: reports/team_report.html

Dependencies
	•	apps.teams: To fetch team and member data
	•	apps.assessments: To retrieve peaks, questions, and answers
	•	django.db.models: Used to aggregate data (Sum, Count)

## Report Summary Component

The `team_report.html` template includes a summary table showing each Peak's percentage score.

### Data Source:
The `peaks` context variable passed into the template contains:
- `name`: Peak name (e.g., "Collaborative Culture")
- `score`: Average percentage across its questions
- `questions`: A list of dicts with `text` and `score`

### Updating for More Questions:
The number of questions per peak doesn't affect the table; this component just shows the **aggregated score** per peak. To add more questions, update the database seed or admin panel — the backend view will aggregate them automatically.

### Future Enhancements:
- Add color-coded score ranges (e.g., red < 35%, yellow 35–65%, green > 65%)
- Convert to a styled visual with CSS or use a component framework
- Use this same block as the first page of a future PDF export

⸻

For any new views added here, make sure to update urls.py and confirm templates exist at templates/reports/.