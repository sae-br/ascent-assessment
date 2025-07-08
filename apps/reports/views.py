from django.shortcuts import render, get_object_or_404, redirect
from apps.teams.models import Team
from apps.assessments.models import Peak, Question, Answer
from django.db.models import Sum, Count
from django.contrib.auth.decorators import login_required

@login_required
def generate_report(request):
    teams = Team.objects.all()
    return render(request, 'reports/generate.html', {'teams': teams})

@login_required
def review_team_report(request, team_id):
    team = get_object_or_404(Team, id=team_id)
    members = team.members.all()
    total_members = members.count()

    peaks_data = []

    for peak in Peak.objects.prefetch_related('questions'):
        peak_total_score = 0
        peak_max_score = 0
        question_data = []

        for question in peak.questions.all():
            answers = Answer.objects.filter(question=question, team_member__in=members)
            total_score = answers.aggregate(score_sum=Sum('value'))['score_sum'] or 0
            response_count = answers.aggregate(count=Count('id'))['count'] or 0
            max_score = response_count * 3  # 3 is max value per answer

            question_percentage = (total_score / max_score * 100) if max_score else 0

            question_data.append({
                'text': question.text,
                'score': round(question_percentage),
            })

            peak_total_score += total_score
            peak_max_score += max_score

        peak_percentage = (peak_total_score / peak_max_score * 100) if peak_max_score else 0

        peaks_data.append({
            'name': peak.name,
            'score': round(peak_percentage),
            'questions': question_data
        })

    return render(request, 'reports/team_report.html', {
        'team': team,
        'peaks': peaks_data
    })

@login_required
def review_team_report_redirect(request):
    team_id = request.GET.get('team_id')
    return redirect('review_team_report', team_id=team_id)