# Teams App

This app manages teams and their members, forming the foundation for organizing assessments. It also integrates cleanly with the assessments system by tracking participation on a per-assessment basis.

## Models

Team
	•	name: CharField - Name of the team
	•	admin: ForeignKey(User) - The user who created and owns this team
	•	created_at: DateTimeField - Timestamp when the team was created

TeamMember
	•	team: ForeignKey(Team) - Team to which the member belongs
	•	name: CharField - Member’s name
	•	email: EmailField - Member’s email address
	•	unique_token: UUIDField - Used to invite team members securely

AssessmentParticipant (Defined in the assessments app)
	•	assessment: ForeignKey(Assessment) - Which assessment this participation refers to
	•	team_member: ForeignKey(TeamMember) - Who the participant is
	•	has_submitted: BooleanField - Whether they’ve submitted their responses

AssessmentParticipant connects a TeamMember to a specific Assessment and tracks their submission status. This enables teams to launch multiple assessments over time without overwriting member status.


## Key Relationships
	•	A User (admin) can own many Teams
	•	A Team has many TeamMembers
	•	Each Assessment is linked to a single Team
	•	Each TeamMember can be invited to multiple assessments via AssessmentParticipant


## Adding New Teams or Members
	•	Users can create a team and immediately add members from the dashboard or during assessment setup.
	•	Each TeamMember is stored once per team.
	•	When launching a new assessment, AssessmentParticipant records are created to track each invited member’s progress.


## Related Apps
	•	accounts: Handles user sign-up/login
	•	assessments: Launches assessments, stores answers, and manages participant state
	•	dashboard: Renders a summary of all teams and assessments owned by the logged-in user