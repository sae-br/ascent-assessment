from django.shortcuts import render, get_object_or_404, redirect
from apps.teams.models import Team
from apps.assessments.models import Peak, Question, Answer, Assessment, AssessmentParticipant
from django.db.models import Sum, Count
from django.contrib.auth.decorators import login_required

@login_required
def generate_report(request):
    assessments = Assessment.objects.filter(team__admin=request.user).select_related('team')
    return render(request, 'reports/generate.html', {'assessments': assessments})

@login_required
def review_team_report(request, assessment_id):
    assessment = get_object_or_404(Assessment, id=assessment_id, team__admin=request.user)
    participants = assessment.participants.select_related('team_member')
    total_participants = participants.count()

    peaks_data = []

    for peak in Peak.objects.prefetch_related('questions'):
        peak_total_score = 0
        peak_max_score = 0
        question_data = []

        for question in peak.questions.all():
            answers = Answer.objects.filter(question=question, participant__in=participants)
            total_score = answers.aggregate(score_sum=Sum('value'))['score_sum'] or 0
            response_count = answers.count()
            max_score = response_count * 3  # max score per answer is 3

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
        'team': assessment.team,
        'assessment': assessment,
        'peaks': peaks_data
    })

@login_required
def review_team_report_redirect(request):
    assessment_id = request.GET.get('assessment_id')
    return redirect('review_team_report', assessment_id=assessment_id)