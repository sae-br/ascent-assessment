from apps.assessments.models import Assessment, Peak

def get_report_context_data(assessment_id):
    assessment = Assessment.objects.select_related("team").get(id=assessment_id)
    peaks = Peak.objects.all()

    return {
        "assessment": assessment,
        "peaks": peaks,
    }