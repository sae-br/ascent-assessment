# Reports App

This app is responsible for generating visualized summary reports based on responses submitted through the assessments app. Reports are grouped by team and organized by “peaks” (assessment categories).

## Functionality Overview
	•	Lists all teams with available assessments to generate reports.
	•	Displays percentage scores for each peak and each question within a peak.
	•	Calculates these scores using all team member answers — not averages of individuals.

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

## Output

The final report includes:
	•	Team name
	•	Assessment date
	•	One section per Peak:
    	•	Overall score for that Peak
    	•	Each Question:
            •	Text
            •	Percentage score (across all team members)

Future Considerations
	•	Add support for filtering by assessment deadline.
	•	Style the output for print/export.
	•	Add support for comparing scores over time (across multiple assessments).

⸻

For any new views added here, make sure to update urls.py and confirm templates exist at templates/reports/.