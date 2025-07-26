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
        line=dict(color='rgba(0, 147, 237, 1)'),
        hoverinfo='x+y',
        name=peak_name
    ))

    fig.update_layout(
        title=None,
        xaxis=dict(title='', showgrid=False, tickangle=0, tickfont=dict(size=14)),
        yaxis=dict(title='', showgrid=False, visible=False),
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        showlegend=False,
        margin=dict(l=0, r=0, t=0, b=0)
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

# Bar chart for each question - generate chart
def generate_question_bar_chart(question_text, rating_counts, output_path):
    labels = ["Consistently\nUntrue", "Somewhat\nUntrue", "Somewhat\nTrue", "Consistently\nTrue"]

    fig = go.Figure(data=[
        go.Bar(x=labels, y=rating_counts, text=rating_counts, textposition="outside", marker_color="#0093ED")
    ])

    fig.update_layout(
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        margin=dict(l=0, r=0, t=0, b=10),  # t=0 instead of 10
        height=180,
        width=320,
        showlegend=False
    )

    fig.write_image(output_path, width=320, height=180, format="svg")

# Creates temp pngs for graphs/charts
@contextmanager
def temporary_plotly_images(figures, format="svg"):
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