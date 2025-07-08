# Team Assessment Tool

This is a custom Django application I’m building as an MVP to support consultants' team assessment process. The goal is to make it simple for consultants or team leaders to create team assessments, invite members, collect responses, and generate actionable reports. I'm using the OrgHealth Ascent Model as the framework for this initial version.

I'm building this in the open because I'm still new to this and want to offer and benefit from anyone's collaboration. 

## 🧠 What It Does (Eventually)

- Teams can be created and managed
- Assessments can be launched with a deadline (month/year)
- Team members receive unique links to complete their assessments
- Responses are stored and scored
- Reports will be generated based on aggregate team responses

## 🔧 Tech Stack

- Python 3.13
- Django 5.2
- PostgreSQL (local for now)
- HTML/CSS (no front-end framework yet)
- Planned: Deployment via Render, email via SendGrid

## 📁 Project Structure

I've organized the project using an `apps/` directory to keep it modular and scalable. Here's the general structure:

assessmvp/
├── apps/
│   ├── accounts/
│   ├── teams/
│   ├── assessments/
│   ├── reports/
│   ├── dashboard/
│   └── payments/
├── assessment_tool/  # project settings, root urls
├── static/           # project-wide CSS/JS/images
├── templates/        # shared templates (base.html, 404.html, etc)
├── scripts/          # helper scripts for admin/dev tasks
├── docs/             # planning docs, architecture notes, etc
├── manage.py
├── .env.example
└── README.md


## 🔐 Environment Variables

I want to keep things safe and plan for eventual production, so this project uses a `.env` file to manage sensitive settings like database credentials and the Django secret key. 

---

If you’re reading this and have thoughts, suggestions, or want to follow along, I’d love that. You can find me at questadon.com or on Mastodon as @another_sarah_brown.