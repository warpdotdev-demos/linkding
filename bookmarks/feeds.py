import unicodedata
from dataclasses import dataclass

from django.contrib.auth.models import User
from django.contrib.syndication.views import Feed
from django.db.models import QuerySet, prefetch_related_objects
from django.http import HttpRequest
from django.urls import reverse

from bookmarks import queries
from bookmarks.models import Bookmark, BookmarkSearch, FeedToken, UserProfile
from bookmarks.views import access


@dataclass
class FeedContext:
    request: HttpRequest
    feed_token: FeedToken | None
    user: User | None
    query_set: QuerySet[Bookmark]


def sanitize(text: str):
    if not text:
        return ""
    # remove control characters
    valid_chars = ["\n", "\r", "\t"]
    return "".join(
        ch for ch in text if ch in valid_chars or unicodedata.category(ch)[0] != "C"
    )


def qualify_with_user(text: str, user: User | None) -> str:
    return f"{text} by {user.username}" if user else text


class BaseBookmarksFeed(Feed):
    def get_object(self, request, feed_key: str | None):
        feed_token = FeedToken.objects.get(key__exact=feed_key) if feed_key else None
        bundle = None
        bundle_id = request.GET.get("bundle")
        if bundle_id:
            bundle = access.bundle_read(request, bundle_id)

        search = BookmarkSearch(
            q=request.GET.get("q", ""),
            unread=request.GET.get("unread", ""),
            shared=request.GET.get("shared", ""),
            bundle=bundle,
        )
        user = self.get_user(request, feed_token)
        query_set = self.get_query_set(feed_token, search, user)
        return FeedContext(request, feed_token, user, query_set)

    def get_user(self, request, feed_token: FeedToken | None) -> User | None:
        return None

    def get_query_set(
        self, feed_token: FeedToken, search: BookmarkSearch, user: User | None
    ):
        raise NotImplementedError

    def items(self, context: FeedContext):
        limit = context.request.GET.get("limit", 100)
        data = context.query_set[: int(limit)] if limit else list(context.query_set)
        prefetch_related_objects(data, "tags")
        return data

    def item_title(self, item: Bookmark):
        return sanitize(item.resolved_title)

    def item_description(self, item: Bookmark):
        return sanitize(item.resolved_description)

    def item_link(self, item: Bookmark):
        return item.url

    def item_pubdate(self, item: Bookmark):
        return item.date_added

    def item_categories(self, item: Bookmark):
        return item.tag_names


class AllBookmarksFeed(BaseBookmarksFeed):
    title = "All bookmarks"
    description = "All bookmarks"

    def get_query_set(
        self, feed_token: FeedToken, search: BookmarkSearch, user: User | None
    ):
        return queries.query_bookmarks(feed_token.user, feed_token.user.profile, search)

    def link(self, context: FeedContext):
        return reverse("linkding:feeds.all", args=[context.feed_token.key])


class UnreadBookmarksFeed(BaseBookmarksFeed):
    title = "Unread bookmarks"
    description = "All unread bookmarks"

    def get_query_set(
        self, feed_token: FeedToken, search: BookmarkSearch, user: User | None
    ):
        return queries.query_bookmarks(
            feed_token.user, feed_token.user.profile, search
        ).filter(unread=True)

    def link(self, context: FeedContext):
        return reverse("linkding:feeds.unread", args=[context.feed_token.key])


class SharedBookmarksFeed(BaseBookmarksFeed):
    title = "Shared bookmarks"
    description = "All shared bookmarks"

    def get_query_set(
        self, feed_token: FeedToken, search: BookmarkSearch, user: User | None
    ):
        return queries.query_shared_bookmarks(
            None, feed_token.user.profile, search, False
        )

    def link(self, context: FeedContext):
        return reverse("linkding:feeds.shared", args=[context.feed_token.key])


class PublicSharedBookmarksFeed(BaseBookmarksFeed):
    base_title = "Public shared bookmarks"
    base_description = "All public shared bookmarks"

    def get_object(self, request):
        return super().get_object(request, None)

    def get_user(self, request, feed_token: FeedToken | None) -> User | None:
        username = request.GET.get("user")
        if not username:
            return None
        return User.objects.get(username=username)

    def title(self, context: FeedContext):
        return qualify_with_user(self.base_title, context.user)

    def description(self, context: FeedContext):
        return qualify_with_user(self.base_description, context.user)

    def get_query_set(
        self, feed_token: FeedToken, search: BookmarkSearch, user: User | None
    ):
        return queries.query_shared_bookmarks(user, UserProfile(), search, True)

    def link(self, context: FeedContext):
        return reverse("linkding:feeds.public_shared")
