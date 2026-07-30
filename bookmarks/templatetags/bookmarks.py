from urllib.parse import urlencode

from django import template

from bookmarks.forms import BookmarkSearchForm
from bookmarks.models import BookmarkSearch

register = template.Library()


@register.inclusion_tag(
    "bookmarks/search.html", name="bookmark_search", takes_context=True
)
def bookmark_search(context, search: BookmarkSearch, mode: str = ""):
    search_form = BookmarkSearchForm(search, editable_fields=["q"])

    if mode == "shared":
        preferences_form = BookmarkSearchForm(search, editable_fields=["sort"])
    else:
        preferences_form = BookmarkSearchForm(
            search, editable_fields=["sort", "shared", "unread"]
        )

    global_search_url = None
    request = context["request"]
    if search.bundle is not None and search.q:
        params = request.GET.copy()
        params.pop("bundle", None)
        params.pop("page", None)
        global_search_url = ("?" + urlencode(params)) if params else request.path

    return {
        "request": request,
        "app_version": context["app_version"],
        "search": search,
        "search_form": search_form,
        "preferences_form": preferences_form,
        "mode": mode,
        "global_search_url": global_search_url,
    }
