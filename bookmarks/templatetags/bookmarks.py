from django import template

from bookmarks.forms import BookmarkSearchForm
from bookmarks.models import BookmarkSearch

register = template.Library()


def _build_toggle_url(request, add_params=None, remove_params=None):
    """Build a URL from the current request's GET params, adding/removing specified keys."""
    params = request.GET.copy()
    # Remove pagination when toggling global search state
    params.pop("page", None)
    if remove_params:
        for key in remove_params:
            params.pop(key, None)
    if add_params:
        for key, value in add_params.items():
            params[key] = value
    query_string = params.urlencode()
    return f"?{query_string}" if query_string else "?"


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

    request = context["request"]
    global_search_url = _build_toggle_url(request, add_params={"global_search": "1"})
    bundle_search_url = _build_toggle_url(request, remove_params=["global_search"])

    return {
        "request": request,
        "app_version": context["app_version"],
        "search": search,
        "search_form": search_form,
        "preferences_form": preferences_form,
        "mode": mode,
        "global_search_url": global_search_url,
        "bundle_search_url": bundle_search_url,
    }
