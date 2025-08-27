# Reports App

This app is responsible for generating visualized summary reports based on responses submitted through the assessments app. Reports are grouped by team and organized by “peaks” (assessment categories).

## Functionality Overview
	•	Lists all teams with available assessments to generate reports.
	•	Displays percentage scores for each peak and each question within a peak.
	•	Calculates these scores using all team member answers — not averages of individuals.

## Utilities

### Get Score Range Label

Describes the range for a peak’s score (e.g., LOW = 0–33%, MEDIUM = 34–66%, HIGH = 67–100%).


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

### PeakInsights

Bullet points offering a short interpretation of the team’s result for a given peak in a specific score range.

### PeakActions

Suggested leadership actions based on score range for a given peak.


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