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

I've organized the project using an `apps/` directory to keep it modular and scalable. This is not default Django, so it's important to specify the changes. Here's the general structure:

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

### Adding a New Custom App

If you create a new app (e.g., python manage.py startapp example), be sure to follow these custom steps:


1. **Create the app as usual:**

   ```bash
   python manage.py startapp example
   ```

2. **Move the app into the `apps/` folder:**

   ```bash
   mv example apps/
   ```

3. **Update `INSTALLED_APPS` in `settings.py`:**
   Instead of just `'example'`, use the full dotted path:

   ```python
   'apps.example.apps.ExampleConfig',
   ```

4. **Ensure the app's app.py names it correctly:**
    ```python
    class ExampleConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.example'
    ```

5. **Ensure `apps/` is a package:**
   Add an empty `__init__.py` file inside the `apps/` directory if it doesn't already exist:

   ```bash
   touch apps/__init__.py
   ```

6. **App templates location:**
    Store app-specific templates in:

    ```
    'apps/example/templates/example/your_template.html'
    ```

7. **Static files (if used):**
    Store app-specific static files in:

    ```
    'apps/example/static/example/your_file.js'
    ```

8. **Use relative imports within apps:**
    To avoid module errors, use:

    ```python
    from apps.example.models import YourModel
    ```

9.	**Run makemigrations and migrate as normal:**
    Django’s migration system works fine with apps in a subfolder.


## 🔐 Environment Variables

I want to keep things safe and plan for eventual production, so this project uses a `.env` file to manage sensitive settings like database credentials and the Django secret key. 



---

If you’re reading this and have thoughts, suggestions, or want to follow along, I’d love that. You can find me at questadon.com or on Mastodon as @another_sarah_brown.