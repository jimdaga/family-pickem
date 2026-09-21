"""Geometry for the standings breakdown sparkline.

Pure functions only — no models, no request, no ORM — so the shape of the
line can be tested directly. The sparkline is rendered as inline SVG with no
JavaScript and no charting library: the standings page pulls GSAP from a CDN
for its entrance animation, and a reader must never lose data because that
CDN failed or because they run with reduced motion on.

The coordinate space is deliberately wide (560x56) so the SVG can scale
*uniformly* to the row's width. An earlier version used a 120x28 box with
``preserveAspectRatio="none"``, which stretched the drawing ~7x horizontally
and would have turned any vertex marker into a flat ellipse.
"""

# The drawing's coordinate space. The rendered SVG is `w-full`, so it scales
# uniformly to whatever width the ribbon gives it and takes its height from
# this aspect ratio. 10:1 is the compromise that keeps the chart a sensible
# height on a wide desktop card (~87px) without collapsing to a hairline on a
# 390px phone (~30px).
SPARKLINE_WIDTH = 560
SPARKLINE_HEIGHT = 56

# Padding keeps the end dots and the stroke's round cap inside the viewBox.
SPARKLINE_PAD = 6

# Correct-pick percentage is a fixed 0-100 quantity, so the axis is fixed too.
# Auto-scaling to each player's own min/max would make a 61-64% season look as
# dramatic as a 20-90% one, and would stop two cards on the same page from
# being comparable at a glance -- the opposite of what the sparkline is for.
_AXIS_MIN = 0.0
_AXIS_MAX = 100.0


def _coords(series, width, height, pad):
    """Shared geometry: one (x, y) per entry, in viewBox coordinates."""
    if not series:
        return []

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
        return [(pad + usable_width / 2, y_for(series[0]['accuracy']))]

    step = usable_width / (len(series) - 1)
    return [
        (pad + i * step, y_for(entry['accuracy']))
        for i, entry in enumerate(series)
    ]


def sparkline_points(series, width=SPARKLINE_WIDTH, height=SPARKLINE_HEIGHT,
                     pad=SPARKLINE_PAD):
    """Map a weekly-accuracy series to an SVG polyline ``points`` string.

    ``series`` is the list of ``{'week', 'accuracy', ...}`` dicts produced by
    ``build_pool_standings_stats``, already ordered by week. Returns "" for an
    empty series (the caller omits the sparkline entirely); a single-entry
    series returns one point, which the template renders as a lone dot.
    """
    return " ".join(
        f"{x:.1f},{y:.1f}" for x, y in _coords(series, width, height, pad)
    )


def sparkline_area(series, width=SPARKLINE_WIDTH, height=SPARKLINE_HEIGHT,
                   pad=SPARKLINE_PAD):
    """The same line closed down to the baseline, for a soft fill under it.

    Returns "" whenever there is nothing to fill — an empty series, or a
    single point (one vertical sliver would read as a stray tick, not a
    trend). The fill is decorative: the line itself carries the data.
    """
    coords = _coords(series, width, height, pad)
    if len(coords) < 2:
        return ""
    baseline = height - pad
    body = " ".join(f"{x:.1f},{y:.1f}" for x, y in coords)
    return f"{coords[0][0]:.1f},{baseline:.1f} {body} {coords[-1][0]:.1f},{baseline:.1f}"


def sparkline_dots(series, width=SPARKLINE_WIDTH, height=SPARKLINE_HEIGHT,
                   pad=SPARKLINE_PAD):
    """One marker per graded week, so the reader can count the weeks.

    A bare polyline reads as a smooth shape rather than a series of weekly
    results; the markers restore "these are 18 discrete weeks". Each entry
    carries its week and accuracy so the marker can title itself, and
    ``is_last`` lets the template emphasise the most recent week.
    """
    coords = _coords(series, width, height, pad)
    last_index = len(coords) - 1
    return [
        {
            'x': round(x, 1),
            'y': round(y, 1),
            'week': entry['week'],
            'accuracy': entry['accuracy'],
            'correct': entry['correct'],
            'total': entry['total'],
            'is_last': i == last_index,
        }
        for i, (entry, (x, y)) in enumerate(zip(series, coords))
    ]


def sparkline_midline(width=SPARKLINE_WIDTH, height=SPARKLINE_HEIGHT,
                      pad=SPARKLINE_PAD):
    """y of the 50% gridline — the reference that makes the line legible.

    Without it a rising line says nothing about whether the player is above
    or below a coin flip, which is the comparison that actually matters.
    """
    usable_height = max(height - 2 * pad, 1)
    return round(pad + usable_height / 2, 1)
