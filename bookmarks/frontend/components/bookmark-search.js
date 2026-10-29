import { visit } from "@hotwired/turbo";
import { HeadlessElement } from "../utils/element.js";

class BookmarkSearch extends HeadlessElement {
  init() {
    this.querySelector("[data-search-all]")?.addEventListener("click", () => {
      const form = this.querySelector("#search");
      const fields = new FormData(form);
      const url = new URL(this.dataset.allBookmarksUrl, window.location.origin);
      for (const name of [
        "q",
        "sort",
        "shared",
        "unread",
        "modified_since",
        "added_since",
      ]) {
        if (fields.has(name)) {
          url.searchParams.set(name, fields.get(name));
        }
      }
      visit(url.href, { action: "advance" });
    });
  }
}

customElements.define("ld-bookmark-search", BookmarkSearch);
