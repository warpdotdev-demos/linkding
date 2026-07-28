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

    # Build URLs for the global search toggle links
    request = context["request"]
    current_params = request.GET.copy()

    # global_search_url: add global_search=1, remove page
    global_params = current_params.copy()
    global_params["global_search"] = "1"
    global_params.pop("page", None)
    global_search_url = "?" + global_params.urlencode()

    # bundle_search_url: remove global_search, remove page
    bundle_params = current_params.copy()
    bundle_params.pop("global_search", None)
    bundle_params.pop("page", None)
    bundle_search_url = "?" + bundle_params.urlencode()

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
