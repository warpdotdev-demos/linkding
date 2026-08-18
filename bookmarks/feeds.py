import unicodedata
from dataclasses import dataclass

from django.contrib.syndication.views import Feed
from django.db.models import QuerySet, prefetch_related_objects
from django.http import HttpRequest
from django.urls import reverse

from bookmarks import queries
from bookmarks.models import Bookmark, BookmarkSearch, FeedToken, User, UserProfile
from bookmarks.views import access


@dataclass
class FeedContext:
    request: HttpRequest
    feed_token: FeedToken | None
    query_set: QuerySet[Bookmark]
    # The single user that the feed is scoped to, if any
    user: User | None = None


def sanitize(text: str):
    if not text:
        return ""
    # remove control characters
    valid_chars = ["\n", "\r", "\t"]
    return "".join(
        ch for ch in text if ch in valid_chars or unicodedata.category(ch)[0] != "C"
    )


def qualify_with_user(text: str, user: User | None):
    """Qualifies a feed title or description with the user that the feed is
    scoped to, so that feeds of different users can be told apart in a feed
    reader."""
    return f"{text} ({user.username})" if user else text


class BaseBookmarksFeed(Feed):
    # Base title and description, qualified with the feed's user if the feed is
    # scoped to a single user. Declared without a default so that a subclass
    # that does not set them fails loudly instead of rendering empty metadata.
    base_title: str
    base_description: str

    def get_object(self, request, feed_key: str | None):
        feed_token = FeedToken.objects.get(key__exact=feed_key) if feed_key else None
        bundle = None
        bundle_id = request.GET.get("bundle")
        if bundle_id:
            bundle = access.bundle_read(request, bundle_id)

        search = BookmarkSearch(
            q=request.GET.get("q", ""),
            user=request.GET.get("user", ""),
            unread=request.GET.get("unread", ""),
            shared=request.GET.get("shared", ""),
            bundle=bundle,
        )
        user = self.get_user(feed_token, search)
        query_set = self.get_query_set(feed_token, search, user)
        return FeedContext(request, feed_token, query_set, user)

    def get_user(
        self, feed_token: FeedToken | None, search: BookmarkSearch
    ) -> User | None:
        """Returns the single user that the feed is scoped to, if any. Feeds that
        belong to a single user opt in by overriding this, so that a feed which
        contains the bookmarks of several users cannot end up labeled with the
        name of one of them."""
        return None

    def get_query_set(
        self, feed_token: FeedToken | None, search: BookmarkSearch, user: User | None
    ):
        raise NotImplementedError

    def title(self, context: FeedContext):
        return qualify_with_user(self.base_title, context.user)

    def description(self, context: FeedContext):
        return qualify_with_user(self.base_description, context.user)

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
    base_title = "All bookmarks"
    base_description = "All bookmarks"

    def get_user(
        self, feed_token: FeedToken | None, search: BookmarkSearch
    ) -> User | None:
        return feed_token.user

    def get_query_set(
        self, feed_token: FeedToken | None, search: BookmarkSearch, user: User | None
    ):
        return queries.query_bookmarks(feed_token.user, feed_token.user.profile, search)

    def link(self, context: FeedContext):
        return reverse("linkding:feeds.all", args=[context.feed_token.key])


class UnreadBookmarksFeed(BaseBookmarksFeed):
    base_title = "Unread bookmarks"
    base_description = "All unread bookmarks"

    def get_user(
        self, feed_token: FeedToken | None, search: BookmarkSearch
    ) -> User | None:
        return feed_token.user

    def get_query_set(
        self, feed_token: FeedToken | None, search: BookmarkSearch, user: User | None
    ):
        return queries.query_bookmarks(
            feed_token.user, feed_token.user.profile, search
        ).filter(unread=True)

    def link(self, context: FeedContext):
        return reverse("linkding:feeds.unread", args=[context.feed_token.key])


class SharedBookmarksFeed(BaseBookmarksFeed):
    base_title = "Shared bookmarks"
    base_description = "All shared bookmarks"

    # This feed contains the shared bookmarks of all users, not just the ones of
    # the feed token's user, so it is not scoped to a single user and keeps the
    # base implementation of get_user

    def get_query_set(
        self, feed_token: FeedToken | None, search: BookmarkSearch, user: User | None
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

    def get_user(
        self, feed_token: FeedToken | None, search: BookmarkSearch
    ) -> User | None:
        if not search.user:
            return None
        # Raises User.DoesNotExist, which the syndication framework turns into a
        # 404, for unknown usernames. That way a broken subscription is visible
        # instead of silently returning the bookmarks of all users.
        return User.objects.get(username=search.user)

    def get_query_set(
        self, feed_token: FeedToken | None, search: BookmarkSearch, user: User | None
    ):
        return queries.query_shared_bookmarks(user, UserProfile(), search, True)

    def link(self, context: FeedContext):
        return reverse("linkding:feeds.public_shared")
