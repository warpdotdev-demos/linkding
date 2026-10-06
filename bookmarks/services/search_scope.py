from django.http import QueryDict
from django.urls import reverse

from bookmarks.models import BookmarkBundle, BookmarkSearch


def resolve_bundle(user, value):
    """Resolve an owner-only bundle ID without passing invalid integers to the DB."""
    if not user.is_authenticated or not value:
        return None
    value = str(value)
    if len(value) > 19 or not value.isascii() or not value.isdecimal():
        return None
    bundle_id = int(value)
    if not 0 < bundle_id <= 2**63 - 1:
        return None
    return BookmarkBundle.objects.filter(owner=user, pk=bundle_id).first()


class SearchScope:
    """Navigation state only: return_bundle never participates in a search."""

    def __init__(self, request, params, mode="", bundle=None):
        self.enabled = mode != "shared" and request.user.is_authenticated
        self.bundle = (
            bundle or resolve_bundle(request.user, params.get("bundle"))
            if self.enabled
            else None
        )
        self.origin = (
            resolve_bundle(request.user, params.get("return_bundle"))
            if self.enabled and not self.bundle
            else None
        )
        self.label = "All archived bookmarks" if mode == "archived" else "All bookmarks"
        self.remove_label = f"Search {self.label.lower()}"
        route = (
            "linkding:bookmarks.archived"
            if mode == "archived"
            else "linkding:bookmarks.index"
        )
        self.index_url = reverse(route)
        self.params = QueryDict(mutable=True)
        for param in BookmarkSearch.params:
            if param != "bundle" and param in params:
                self.params.setlist(param, params.getlist(param))
        self.unbundle_url = self._url(origin=self.bundle or self.origin)
        self.return_url = self._url(bundle=self.origin) if self.origin else ""

    def normalize_origin(self, params):
        params.pop("return_bundle", None)
        if self.origin:
            params["return_bundle"] = str(self.origin.id)

    def _url(self, bundle=None, origin=None):
        params = self.params.copy()
        if bundle:
            params["bundle"] = str(bundle.id)
        elif origin:
            params["return_bundle"] = str(origin.id)
        query = params.urlencode()
        return self.index_url + ("?" + query if query else "")
