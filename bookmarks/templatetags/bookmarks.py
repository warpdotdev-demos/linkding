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

    bookmark_list = context.get("bookmark_list")
    search_everywhere_url = (
        getattr(bookmark_list, "search_everywhere_url", None) if bookmark_list else None
    )
    back_to_bundle_url = (
        getattr(bookmark_list, "back_to_bundle_url", None) if bookmark_list else None
    )

    return {
        "request": context["request"],
        "app_version": context["app_version"],
        "search": search,
        "search_form": search_form,
        "preferences_form": preferences_form,
        "mode": mode,
        "search_everywhere_url": search_everywhere_url,
        "back_to_bundle_url": back_to_bundle_url,
    }
