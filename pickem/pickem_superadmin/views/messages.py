from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import render
from django.urls import reverse

from pickem_api.models import Family, Pool
from pickem_homepage.models import MessageBoardComment, MessageBoardPost
from pickem_superadmin.decorators import superadmin_required

KINDS = ('post', 'comment')


def _family_board_urls(family_ids):
    """family_id -> that family's message board URL (via its active default
    pool, else its newest active pool), resolved in one query."""
    urls = {}
    pools = (
        Pool.objects.filter(family_id__in=family_ids, status=Pool.Status.ACTIVE)
        .select_related('family')
        .order_by('family_id', '-is_default', '-season', 'slug')
    )
    for pool in pools:
        if pool.family_id not in urls:
            urls[pool.family_id] = reverse(
                'family_pool_messages',
                kwargs={'family_slug': pool.family.slug, 'pool_slug': pool.slug},
            )
    return urls


class _MergedStream:
    """Newest-first merge of several querysets, sliceable for Paginator.

    A page ending at row N only needs the newest N rows of each source, so
    nothing beyond that is loaded however large the boards get.
    """

    def __init__(self, sources):
        self.sources = sources  # [(kind, queryset, title_fn), ...]

    def count(self):
        return sum(queryset.count() for _kind, queryset, _title in self.sources)

    def __getitem__(self, window):
        stop = window.stop
        rows = []
        for kind, queryset, title in self.sources:
            for obj in queryset.order_by('-created_at', '-id')[:stop]:
                rows.append({
                    'kind': kind, 'obj': obj, 'title': title(obj),
                    'created_at': obj.created_at,
                })
        rows.sort(key=lambda row: row['created_at'], reverse=True)
        return rows[window.start:stop]


@superadmin_required
def message_board(request):
    """Every family's message board posts and comments in one read-only
    stream, newest first — for scanning site feedback across leagues."""
    family_slug = request.GET.get('family', '').strip()
    query = request.GET.get('q', '').strip()
    kind = request.GET.get('kind', '').strip()
    if kind not in KINDS:
        kind = ''
    show_hidden = request.GET.get('hidden') == '1'

    posts = MessageBoardPost.objects.select_related('family', 'user')
    comments = MessageBoardComment.objects.select_related('family', 'user', 'post')
    if family_slug:
        posts = posts.filter(family__slug=family_slug)
        comments = comments.filter(family__slug=family_slug)
    if not show_hidden:
        posts = posts.filter(is_active=True)
        comments = comments.filter(is_active=True)
    if query:
        posts = posts.filter(
            Q(title__icontains=query) | Q(content__icontains=query)
            | Q(user__username__icontains=query)
        )
        comments = comments.filter(
            Q(content__icontains=query) | Q(post__title__icontains=query)
            | Q(user__username__icontains=query)
        )

    sources = []
    if kind != 'comment':
        sources.append(('post', posts, lambda p: p.title))
    if kind != 'post':
        sources.append((
            'comment', comments.defer('post__content'), lambda c: c.post.title,
        ))

    page = Paginator(_MergedStream(sources), 50).get_page(request.GET.get('page'))
    board_urls = _family_board_urls(
        {item['obj'].family_id for item in page if item['obj'].family_id}
    )
    for item in page:
        item['board_url'] = board_urls.get(item['obj'].family_id)

    return render(request, 'superadmin/messages.html', {
        'items': page,
        'families': Family.objects.order_by('name', 'slug'),
        'family_filter': family_slug,
        'query': query,
        'kind_filter': kind,
        'show_hidden': show_hidden,
    })
