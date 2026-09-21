"""Geometry for the standings breakdown sparkline.

Pure functions only — no models, no request, no ORM — so the shape of the
line can be tested directly. The sparkline is rendered as inline SVG with no
JavaScript and no charting library: the standings page pulls GSAP from a CDN
for its entrance animation, and a reader must never lose data because that
CDN failed or because they run with reduced motion on.

The viewBox is an arbitrary internal coordinate space: the SVG renders with
``preserveAspectRatio="none"`` so it stretches to the row's width while the
CSS pins its height, keeping the chart at sparkline scale no matter how wide
the card gets. That non-uniform stretch is why nothing here draws a circle —
a marker would smear into an ellipse. The line uses non-scaling-stroke so its
weight stays even, and the one end-marker is a round line-cap, not a circle.
"""

# Internal coordinate space only — the rendered height is set in CSS, not by
# this ratio, because the SVG stretches rather than scaling uniformly.
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


def sparkline_end_point(series, width=SPARKLINE_WIDTH, height=SPARKLINE_HEIGHT,
                        pad=SPARKLINE_PAD):
    """The latest week as a one-point polyline, drawn as a round line-cap.

    A single marker for "where they are now" is worth the ink; one per week
    was not. Rendered via ``stroke-dasharray="0 N"`` with a round cap rather
    than a ``<circle>`` so it survives the SVG's horizontal stretch as a
    circle instead of an ellipse.
    """
    coords = _coords(series, width, height, pad)
    if not coords:
        return ""
    x, y = coords[-1]
    return f"{x:.1f},{y:.1f}"


def sparkline_ticks(series, max_ticks=5, width=SPARKLINE_WIDTH,
                    pad=SPARKLINE_PAD):
    """Evenly spaced week labels for under the chart.

    Returns ``[{'week', 'left'}]`` where ``left`` is a percent of the SVG's
    width, so the template can position each label with CSS and have it line
    up with the point it names even as the chart stretches. Always includes
    the first and last week; thins the middle so labels never collide.
    """
    coords = _coords(series, width, SPARKLINE_HEIGHT, pad)
    if not coords:
        return []
    count = len(coords)
    if count <= max_ticks:
        indexes = range(count)
    else:
        step = (count - 1) / (max_ticks - 1)
        indexes = sorted({round(i * step) for i in range(max_ticks)})
    return [
        {
            'week': series[i]['week'],
            'left': round(coords[i][0] / width * 100, 2),
        }
        for i in indexes
    ]


def sparkline_average(accuracy, height=SPARKLINE_HEIGHT, pad=SPARKLINE_PAD):
    """Where the player's season accuracy sits, as a reference line.

    Returns ``{'y', 'top'}`` — ``y`` in viewBox units for the dashed rule,
    ``top`` as a percent of height so the HTML label beside the chart can sit
    at the same level. Replaces a fixed 50% gridline: "above or below my own
    average" is the comparison that makes a weekly line legible.
    """
    if accuracy is None:
        return None
    usable_height = max(height - 2 * pad, 1)
    clamped = min(max(float(accuracy), _AXIS_MIN), _AXIS_MAX)
    ratio = (clamped - _AXIS_MIN) / (_AXIS_MAX - _AXIS_MIN)
    y = pad + (1 - ratio) * usable_height
    return {'y': round(y, 1), 'top': round(y / height * 100, 2)}
