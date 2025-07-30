# Ascent Assessment for Teams

The Ascent Assessment is a secure, web-based application that enables leadership teams to measure, understand, and act on the health of their organization. Built with Django and PostgreSQL, the platform facilitates data collection, report generation, and tailored recommendations based on the OrgHealth Ascent Model.

## 🚀 Features

- Team assessments with private, invite-only access
- Scored PDF reports with dynamic visuals and insights
- Suggested discussion points and actions based on results
- Admin dashboard for managing teams, assessments, and reports
- Secure, scalable PostgreSQL backend
- Flexible report rendering via HTML-to-PDF pipeline

## 🔧 Tech Stack

- Python 3.13
- Django 5.2
- PostgreSQL 
- WeasyPrint (PDF generation), testing to be replaced with DocRaptor
- Planned: Deployment via Render, email via MailGun, payments via Stripe

## 📁 Project Structure

I've organized the project using an `apps/` directory to keep it modular and scalable. This is not default Django, so it's important to specify the changes. Here's the general structure:

```
ascent-assessment/
├── apps/
│   ├── accounts/     # users
│   ├── assessments/  # assessment categories, questions, start new, etc
│   ├── common/       # some core functions ie markdown, etc
│   ├── dashboard/    # dashboard displays
│   ├── payments/     # billing, checkout, Stripe, etc
│   ├── pdfexport/    # HTML-to-PDF generation, report design
│   ├── reports/      # scoring, web report, dynamic content, report storage
│   └── teams/        # manage teams and team members specific to user
├── assessment_tool/  # project settings, root urls
├── static/           # project-wide CSS/JS/images
├── templates/        # shared templates (base.html, 404.html, etc)
├── scripts/          # helper scripts for admin/dev tasks
├── docs/             # planning docs, architecture notes, etc
├── manage.py
├── .env.example
└── README.md
```

## 📦 Deployment

See `docs/deployment.md` for deployment instructions on Render and environment setup using `.env`.

## 📝 Licensing

This application is licensed for internal use only under a custom OrgHealth license. See `LICENSE.md` for terms.
