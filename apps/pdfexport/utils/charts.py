from collections import Counter
from apps.assessments.models import Answer, Question
import tempfile
from contextlib import contextmanager
import os
import matplotlib
matplotlib.use("Agg")  # headless
import matplotlib.pyplot as plt
import numpy as np


def generate_peak_mountain_chart(title, percentages, output_path):
    """
    Render a minimalist 'mountain' area chart for a 0–3 rating distribution.

    Args:
        title (str): Peak name (not rendered for now)
        percentages (list[float|int]): Four values for ratings 0..3
        output_path (str): PNG path to save to
    """
    import numpy as np
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    # Defensive / normalize
    vals = [(float(percentages[i]) if i < len(percentages) else 0.0) for i in range(4)]
    total = sum(vals) or 1.0
    vals = [v * 100.0 / total for v in vals]  # keep on a 0–100 scale

    # x = four buckets; build a smoothed line between them
    x_base = np.array([0, 1, 2, 3], dtype=float)
    y_base = np.array(vals, dtype=float)
    x = np.linspace(0, 3, 121)
    y = np.interp(x, x_base, y_base)

    # Wide/short figure so it tucks into the score panel
    fig, ax = plt.subplots(figsize=(6.5, 2.2), dpi=180)

    ax.fill_between(x, 0, y, color="#0093ED")       # filled area
    ax.plot(x, y, linewidth=1.0, color="#0b81cb")   # thin outline

    # Minimal axes: only x labels, no y axis, no spines
    ax.set_xlim(0, 3)
    ax.set_ylim(bottom=0)
    ax.set_xticks([0, 1, 2, 3], labels=[
        "Consistently\nUntrue",
        "Somewhat\nUntrue",
        "Somewhat\nTrue",
        "Consistently\nTrue",
    ])
    ax.tick_params(axis="x", labelsize=14, pad=8)

    ax.set_yticks([])
    for side in ("top", "right", "left", "bottom"):
        ax.spines[side].set_visible(False)

    plt.tight_layout(pad=0.2)
    fig.savefig(output_path, bbox_inches="tight", pad_inches=0.02, transparent=True)
    plt.close(fig)


# def generate_peak_distribution_chart(title: str, percentages, output_path: str):
#     # percentages is a list of length 4 for ratings 0..3
#     fig, ax = plt.subplots(figsize=(4, 2.5), dpi=150)
#     ax.bar(range(4), percentages)
#     ax.set_title(title)
#     ax.set_xlabel("Rating (0–3)")
#     ax.set_ylabel("Percent")
#     ax.set_xticks([0, 1, 2, 3])
#     ax.set_ylim(0, 100)
#     fig.tight_layout()
#     fig.savefig(output_path, format="png")
#     plt.close(fig)

# # Area chart for each peak -- generate chart and create png
# def generate_peak_distribution_chart(peak_name, percentages, output_path):
#     labels = [
#         "Consistently<br>Untrue",
#         "Somewhat<br>Untrue",
#         "Somewhat<br>True",
#         "Consistently<br>True"
#     ]

#     # Create the area chart
#     fig = go.Figure()
#     fig.add_trace(go.Scatter(
#         x=labels,
#         y=percentages,
#         fill='tozeroy',
#         mode='lines+text',
#         line=dict(color='rgba(0, 147, 237, 1)'),
#         hoverinfo='x+y',
#         name=peak_name
#     ))

#     fig.update_layout(
#         title=None,
#         xaxis=dict(title='', showgrid=False, tickangle=0, tickfont=dict(size=14)),
#         yaxis=dict(title='', showgrid=False, visible=False),
#         plot_bgcolor='rgba(0,0,0,0)',
#         paper_bgcolor='rgba(0,0,0,0)',
#         showlegend=False,
#         margin=dict(l=0, r=0, t=0, b=0)
#     )

#     fig.write_image(output_path, width=500, height=300)


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


# # Bar chart for each question - generate chart
def generate_question_bar_chart(question_text: str, counts, output_path: str):
    """
    Render a compact, minimalist bar chart for a single question (answers 0..3).

    - Blue brand bars
    - No y-axis or spines
    - Diagonal x tick labels (Consistently Untrue .. Consistently True)
    - Small numeric labels above each bar
    - Transparent background so it sits on your PDF panel nicely
    """
    import numpy as np
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    # Defensive: force 4 values for 0..3
    vals = [(int(counts[i]) if i < len(counts) else 0) for i in range(4)]
    labels = [
        "Consistently\nUntrue",
        "Somewhat\nUntrue",
        "Somewhat\nTrue",
        "Consistently\nTrue",
    ]

    # Compact figure that tucks to the right of the question text
    fig, ax = plt.subplots(figsize=(3.6, 1.8), dpi=180)
    x = np.arange(4)
    bars = ax.bar(x, vals, width=0.65, color="#0093ED")

    # Minimal styling
    for side in ("top", "right", "left", "bottom"):
        ax.spines[side].set_visible(False)

    ax.set_xticks(x, labels=labels)
    ax.tick_params(axis="x", labelsize=10, pad=2, rotation=32)
    # Ensure right alignment for multi-line tick labels after rotation
    for t in ax.get_xticklabels():
        t.set_ha("right")

    ax.set_yticks([])
    ax.set_ylabel("")
    ax.set_xlabel("")

    # Pad the top a bit so value labels don't clip
    ymax = max(vals + [1])
    ax.set_ylim(0, ymax * 1.35)

    # Value labels above bars
    for rect in bars:
        h = rect.get_height()
        ax.text(
            rect.get_x() + rect.get_width() / 2,
            h + ymax * 0.04,
            f"{int(h)}",
            ha="center",
            va="bottom",
            fontsize=12,
        )

    fig.tight_layout(pad=0.2)
    fig.savefig(output_path, bbox_inches="tight", pad_inches=0.02, transparent=True)
    plt.close(fig)

# def generate_question_bar_chart(question_text, rating_counts, output_path):
#     labels = ["Consistently\nUntrue", "Somewhat\nUntrue", "Somewhat\nTrue", "Consistently\nTrue"]

#     fig = go.Figure(data=[
#         go.Bar(x=labels, y=rating_counts, text=rating_counts, textposition="outside", marker_color="#0093ED")
#     ])

#     fig.update_layout(
#         plot_bgcolor='rgba(0,0,0,0)',
#         paper_bgcolor='rgba(0,0,0,0)',
#         margin=dict(l=0, r=0, t=0, b=10),  # t=0 instead of 10
#         height=180,
#         width=320,
#         showlegend=False
#     )

#     fig.write_image(output_path, width=320, height=180, format="svg")

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