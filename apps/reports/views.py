from django.shortcuts import render, get_object_or_404, redirect
from apps.teams.models import Team
from apps.assessments.models import Peak, Question, Answer, Assessment, AssessmentParticipant
from apps.reports.models import ResultsSummary, UniformRangeSummary, PeakInsights, PeakActions
from apps.reports.utils import get_score_range_label
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
    peak_scores = {}

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
        peak_score_rounded = round(peak_percentage)
        peak_scores[peak.name] = peak_score_rounded

        # Determine range label using utility
        range_label = get_score_range_label(peak_percentage)

        # Fetch insight and action for this peak/range
        insight = PeakInsights.objects.filter(peak=peak.code, range_label=range_label).first()
        action = PeakActions.objects.filter(peak=peak.code, range_label=range_label).first()

        peaks_data.append({
            'name': peak.name,
            'code': peak.code, 
            'score': round(peak_percentage),
            'questions': question_data,
            'range': range_label,
            'insight': insight.insight_text if insight else None,
            'action': action.action_text if action else None,
        })

    # Determine results summary (high/low peak or uniform range)
    scores_sorted = sorted(peak_scores.items(), key=lambda x: x[1], reverse=True)
    top_peaks = [name for name, score in scores_sorted if score == scores_sorted[0][1]]
    bottom_peaks = [name for name, score in scores_sorted if score == scores_sorted[-1][1]]

    priority_order = ['CC', 'TM', 'LA', 'SM']

    # Create a name-to-code mapping
    name_to_code = {peak['name']: peak['code'] for peak in peaks_data}

    def prioritize(peaks_names, reverse=False):
        ordered = sorted(
            peaks_names,
            key=lambda name: priority_order.index(name_to_code.get(name, 'ZZ'))  # ZZ to push unknowns to end
        )
        return name_to_code.get(ordered[0]) if ordered else None

    high_peak = prioritize(top_peaks, reverse=True)
    low_peak = prioritize(bottom_peaks)

    summary = ResultsSummary.objects.filter(high_peak=high_peak, low_peak=low_peak).first()

    if not summary:
        range_labels = set([get_score_range_label(score) for score in peak_scores.values()])
        if len(range_labels) == 1:
            summary = UniformRangeSummary.objects.filter(range_label=range_labels.pop()).first()

    return render(request, 'reports/team_report.html', {
        'team': assessment.team,
        'assessment': assessment,
        'peaks': peaks_data,
        'summary_text': summary.summary_text if summary else "",
    })

@login_required
def review_team_report_redirect(request):
    assessment_id = request.GET.get('assessment_id')
    return redirect('review_team_report', assessment_id=assessment_id)