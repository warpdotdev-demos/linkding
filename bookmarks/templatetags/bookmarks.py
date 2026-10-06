from django import forms, template

from bookmarks.forms import BookmarkSearchForm
from bookmarks.models import BookmarkSearch
from bookmarks.services.search_scope import SearchScope

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
    request = context["request"]
    scope = SearchScope(request, request.GET, mode, search.bundle)
    if scope.origin:
        for form in (search_form, preferences_form):
            form.fields["return_bundle"] = forms.CharField(
                initial=scope.origin.id, widget=forms.HiddenInput(), required=False
            )
    return {
        "request": context["request"],
        "app_version": context["app_version"],
        "search": search,
        "search_form": search_form,
        "preferences_form": preferences_form,
        "mode": mode,
        "scope": scope,
    }
