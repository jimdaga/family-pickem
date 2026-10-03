from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import render
from django.urls import reverse

from pickem_api.models import Family, Pool
from pickem_homepage.models import MessageBoardComment, MessageBoardPost
from pickem_superadmin.decorators import superadmin_required

KINDS = ('post', 'comment')


def _family_board_urls(family_ids):
    """family_id -> that family's message board URL (via its default pool,
    else any active pool), resolved in one query."""
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

    items = []
    if kind != 'comment':
        items += [
            {'kind': 'post', 'obj': p, 'title': p.title, 'created_at': p.created_at}
            for p in posts
        ]
    if kind != 'post':
        items += [
            {'kind': 'comment', 'obj': c, 'title': c.post.title, 'created_at': c.created_at}
            for c in comments
        ]
    items.sort(key=lambda item: item['created_at'], reverse=True)

    page = Paginator(items, 50).get_page(request.GET.get('page'))
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
