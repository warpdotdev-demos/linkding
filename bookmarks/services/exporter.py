import csv
import html
import io

from bookmarks.models import Bookmark

BookmarkDocument = list[str]

CSV_HEADERS = [
    "URL",
    "Title",
    "Description",
    "Tags",
    "Date added",
    "Archived",
    "Unread",
    "Shared",
]


def export_netscape_html(bookmarks: list[Bookmark]):
    doc = []
    append_header(doc)
    append_list_start(doc)
    [append_bookmark(doc, bookmark) for bookmark in bookmarks]
    append_list_end(doc)

    return "\n\r".join(doc)


def append_header(doc: BookmarkDocument):
    doc.append("<!DOCTYPE NETSCAPE-Bookmark-file-1>")
    doc.append('<META HTTP-EQUIV="Content-Type" CONTENT="text/html; charset=UTF-8">')
    doc.append("<TITLE>Bookmarks</TITLE>")
    doc.append("<H1>Bookmarks</H1>")


def append_list_start(doc: BookmarkDocument):
    doc.append("<DL><p>")


def append_bookmark(doc: BookmarkDocument, bookmark: Bookmark):
    url = bookmark.url
    title = html.escape(bookmark.resolved_title or "")
    desc = html.escape(bookmark.resolved_description or "")
    if bookmark.notes:
        desc += f"[linkding-notes]{html.escape(bookmark.notes)}[/linkding-notes]"
    tag_names = bookmark.tag_names
    if bookmark.is_archived:
        tag_names.append("linkding:bookmarks.archived")
    tags = ",".join(html.escape(tag) for tag in tag_names)
    toread = "1" if bookmark.unread else "0"
    private = "0" if bookmark.shared else "1"
    added = int(bookmark.date_added.timestamp())
    modified = int(bookmark.date_modified.timestamp())

    doc.append(
        f'<DT><A HREF="{url}" ADD_DATE="{added}" LAST_MODIFIED="{modified}" PRIVATE="{private}" TOREAD="{toread}" TAGS="{tags}">{title}</A>'
    )

    if desc:
        doc.append(f"<DD>{desc}")


def append_list_end(doc: BookmarkDocument):
    doc.append("</DL><p>")


def _format_bool(value: bool) -> str:
    return "true" if value else "false"


def _format_csv_date(value) -> str:
    return value.isoformat().replace("+00:00", "Z")


def export_csv(bookmarks: list[Bookmark]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow(CSV_HEADERS)

    for bookmark in bookmarks:
        writer.writerow(
            [
                bookmark.url,
                bookmark.title,
                bookmark.description,
                ",".join(bookmark.tag_names),
                _format_csv_date(bookmark.date_added),
                _format_bool(bookmark.is_archived),
                _format_bool(bookmark.unread),
                _format_bool(bookmark.shared),
            ]
        )

    return buffer.getvalue()
