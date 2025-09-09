# Ascent Assessment for Teams

The Ascent Assessment is a secure, web-based application that enables leadership teams to measure, understand, and act on the health of their organization. Built with Django and PostgreSQL, the platform facilitates data collection, report generation, and tailored recommendations based on the OrgHealth Ascent Model.

## 🚀 Features

- Team assessments with private, invite-only access
- Scored PDF reports with scores, charts, and dynamic content suggesting discussion points and actions based on results
- Dashboard for managing teams, assessments, and reports
- Secure, scalable PostgreSQL backend

## 🔧 Tech Stack

- Django
- PostgreSQL
- AWS 
- DocRaptor (PDF generation)
- MailGun
- Stripe
- Render (Deployment)

## 📁 Project Structure

I've organized the project using an `apps/` directory to keep it modular and scalable. Here's the general structure:

```
ascent-assessment/
├── apps/
│   ├── accounts/     # users
│   ├── assessments/  # assessment categories, questions, start new, etc
│   ├── common/       # some core functions ie markdown
│   ├── dashboard/    # homepage dashboard displays
│   ├── payments/     # checkout, Stripe, etc
│   ├── pdfexport/    # HTML-to-PDF generation, report design
│   ├── reports/      # scoring, dynamic content, report storage
│   └── teams/        # manage teams and team members specific to user
├── assessment_tool/  # project settings, root urls
├── static/           # project-wide CSS/JS/images
├── templates/        # shared templates (base.html, 404.html, etc)
├── manage.py
├── .env.example
└── README.md
```

## 📝 Licensing

This application is licensed for internal use only under a custom OrgHealth license. See `LICENSE.md` for terms.
