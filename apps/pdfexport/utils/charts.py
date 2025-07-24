import plotly.graph_objects as go
from collections import Counter
from apps.assessments.models import Answer, Question
import tempfile
from contextlib import contextmanager
import os


# Area chart for each peak -- generate chart and create png
def generate_peak_distribution_chart(peak_name, percentages, output_path):
    labels = [
        "Consistently<br>Untrue",
        "Somewhat<br>Untrue",
        "Somewhat<br>True",
        "Consistently<br>True"
    ]

    # Create the area chart
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=labels,
        y=percentages,
        fill='tozeroy',
        mode='lines+text',
        line=dict(color='steelblue'),
        hoverinfo='x+y',
        text=[f"{p}%" for p in percentages],  # Adds % text under each point
        textposition="bottom center",         # You could use "top center" if you prefer
        name=peak_name
    ))

    fig.update_layout(
        title=None,
        xaxis=dict(title='', showgrid=False, tickangle=0, tickfont=dict(size=14)),
        yaxis=dict(title='', showgrid=False, visible=False),
        plot_bgcolor='white',
        paper_bgcolor='lightblue',
        showlegend=False,
        margin=dict(l=10, r=10, t=10, b=10)
    )

    fig.write_image(output_path, width=500, height=300)


# Area chart for each peak -- get needed data
def get_peak_rating_distribution(assessment, peak_code):
    """
    Returns a list of percentages (0-100) for the distribution of response values
    for a given assessment and peak_code.
    
    The order is: [Consistently Untrue, Somewhat Untrue, Somewhat True, Consistently True]
    Which maps to: [0, 1, 2, 3]
    """
    # Get all questions for this peak
    questions = Question.objects.filter(peak__code=peak_code)

    # Get all answers to those questions for this assessment
    answers = Answer.objects.filter(
        participant__assessment=assessment,
        question__in=questions
    ).values_list("value", flat=True)

    total = len(answers)
    counter = Counter(answers)

    if total == 0:
        return [0, 0, 0, 0]

    # Calculate percentages in the correct order
    return [round((counter.get(i, 0) / total) * 100) for i in range(4)]


# Creates temp pngs for graphs/charts
@contextmanager
def temporary_plotly_images(figures, format="png"):
    """
    Saves multiple Plotly figures as temporary image files.
    Yields a list of file paths. Cleans up all files after use.
    """
    temp_paths = []

    try:
        for fig in figures:
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=f".{format}")
            tmp.close()
            fig.write_image(tmp.name)
            temp_paths.append(tmp.name)

        yield temp_paths

    finally:
        for path in temp_paths:
            if os.path.exists(path):
                os.remove(path)