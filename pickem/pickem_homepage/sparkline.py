"""Geometry for the standings breakdown sparkline.

Pure functions only — no models, no request, no ORM — so the shape of the
line can be tested directly. The sparkline is rendered as inline SVG with no
JavaScript and no charting library: the standings page pulls GSAP from a CDN
for its entrance animation, and a reader must never lose data because that
CDN failed or because they run with reduced motion on.
"""

# Matches the ribbon's slot in standings.html. Kept here so the template and
# the geometry can never disagree about the viewBox.
SPARKLINE_WIDTH = 120
SPARKLINE_HEIGHT = 28

# Correct-pick percentage is a fixed 0-100 quantity, so the axis is fixed too.
# Auto-scaling to each player's own min/max would make a 61-64% season look as
# dramatic as a 20-90% one, and would stop two cards on the same page from
# being comparable at a glance -- the opposite of what the sparkline is for.
_AXIS_MIN = 0.0
_AXIS_MAX = 100.0


def sparkline_points(series, width=SPARKLINE_WIDTH, height=SPARKLINE_HEIGHT, pad=2):
    """Map a weekly-accuracy series to an SVG polyline ``points`` string.

    ``series`` is the list of ``{'week', 'accuracy', ...}`` dicts produced by
    ``build_pool_standings_stats``, already ordered by week. Returns "" for an
    empty series (the caller omits the sparkline entirely); a single-entry
    series returns one point, which the template renders as a dot rather than
    a line, since a one-point polyline draws nothing.
    """
    if not series:
        return ""

    usable_width = max(width - 2 * pad, 1)
    usable_height = max(height - 2 * pad, 1)
    span = _AXIS_MAX - _AXIS_MIN

    def y_for(accuracy):
        # Clamp defensively: a stray out-of-range value should flatten against
        # the edge, never draw outside the viewBox.
        clamped = min(max(float(accuracy or 0), _AXIS_MIN), _AXIS_MAX)
        ratio = (clamped - _AXIS_MIN) / span
        # SVG y grows downward, so a high percentage needs a low y.
        return pad + (1 - ratio) * usable_height

    if len(series) == 1:
        return f"{pad + usable_width / 2:.1f},{y_for(series[0]['accuracy']):.1f}"

    step = usable_width / (len(series) - 1)
    return " ".join(
        f"{pad + i * step:.1f},{y_for(entry['accuracy']):.1f}"
        for i, entry in enumerate(series)
    )


def sparkline_area(series, width=SPARKLINE_WIDTH, height=SPARKLINE_HEIGHT, pad=2):
    """The same line closed down to the baseline, for a soft fill under it.

    Returns "" whenever there is nothing to fill — an empty series, or a
    single point (one vertical sliver would read as a stray tick, not a
    trend). The fill is decorative: the line itself carries the data.
    """
    line = sparkline_points(series, width=width, height=height, pad=pad)
    if not line or len(series) < 2:
        return ""
    points = line.split()
    first_x = points[0].split(",")[0]
    last_x = points[-1].split(",")[0]
    baseline = height - pad
    return f"{first_x},{baseline:.1f} {line} {last_x},{baseline:.1f}"
