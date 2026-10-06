import { html } from "lit";
import { api } from "../api.js";
import { TurboLitElement } from "../utils/element.js";
import {
  clampText,
  debounce,
  getCurrentWord,
  getCurrentWordBounds,
} from "../utils/input.js";
import { PositionController } from "../utils/position-controller.js";
import { SearchHistory } from "../utils/search-history.js";
import { cache } from "../utils/tag-cache.js";

export class SearchAutocomplete extends TurboLitElement {
  static properties = {
    inputName: { type: String, attribute: "input-name" },
    inputPlaceholder: { type: String, attribute: "input-placeholder" },
    inputValue: { type: String, attribute: "input-value" },
    mode: { type: String },
    user: { type: String },
    shared: { type: String },
    unread: { type: String },
    bundle: { type: String },
    sort: { type: String },
    modifiedSince: { type: String, attribute: "modified-since" },
    addedSince: { type: String, attribute: "added-since" },
    scopeName: { type: String, attribute: "scope-name" },
    scopeLabel: { type: String, attribute: "scope-label" },
    removeLabel: { type: String, attribute: "remove-label" },
    unbundleUrl: { type: String, attribute: "unbundle-url" },
    returnName: { type: String, attribute: "return-name" },
    returnUrl: { type: String, attribute: "return-url" },
    target: { type: String },
    isFocus: { state: true },
    isOpen: { state: true },
    suggestions: { state: true },
    selectedIndex: { state: true },
  };

  constructor() {
    super();
    this.inputName = "";
    this.inputPlaceholder = "";
    this.inputValue = "";
    this.mode = "";
    this.target = "_blank";
    this.isFocus = false;
    this.isOpen = false;
    this.suggestions = {
      recentSearches: [],
      bookmarks: [],
      tags: [],
      total: [],
    };
    this.selectedIndex = undefined;
    this.input = null;
    this.menu = null;
    this.suggestionRequest = 0;
    this.searchHistory = new SearchHistory();
    this.debouncedLoadSuggestions = debounce(() => this.loadSuggestions());
  }

  firstUpdated() {
    this.style.setProperty("--menu-max-height", "400px");
    this.input = this.querySelector("input");
    this.menu = this.querySelector(".menu");
    // Track current search query after loading the page
    this.searchHistory.pushCurrent();
    this.updateSuggestions();
    this.positionController = new PositionController({
      // Keep the scope/Back row outside the suggestion overlay.
      anchor: this.scopeLabel ? this : this.input,
      overlay: this.menu,
      autoWidth: true,
      placement: "bottom-start",
    });
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    this.close();
  }
  updated(changed) {
    const searchAttributes = [
      "inputValue",
      "mode",
      "user",
      "bundle",
      "sort",
      "shared",
      "unread",
      "modifiedSince",
      "addedSince",
    ];
    if (searchAttributes.some((name) => changed.has(name))) {
      this.close();
    }
  }

  changeScope(e, target) {
    if (
      e.currentTarget instanceof HTMLAnchorElement &&
      (e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey)
    ) {
      return;
    }
    e.preventDefault();
    const url = new URL(target, window.location.origin);
    const query = this.input.value;
    if (query) {
      url.searchParams.set("q", query);
    } else {
      url.searchParams.delete("q");
    }
    this.close();
    window.Turbo.visit(url.href);
  }

  handleFocus() {
    this.isFocus = true;
  }

  handleBlur() {
    this.isFocus = false;
    this.close();
  }

  handleInput(e) {
    this.inputValue = e.target.value;
    this.debouncedLoadSuggestions();
  }

  handleKeyDown(e) {
    // Enter
    if (
      this.isOpen &&
      this.selectedIndex !== undefined &&
      (e.keyCode === 13 || e.keyCode === 9)
    ) {
      const suggestion = this.suggestions.total[this.selectedIndex];
      if (suggestion) this.completeSuggestion(suggestion);
      e.preventDefault();
    }
    // Escape
    if (e.keyCode === 27) {
      this.close();
      e.preventDefault();
    }
    // Up arrow
    if (e.keyCode === 38) {
      this.updateSelection(-1);
      e.preventDefault();
    }
    // Down arrow
    if (e.keyCode === 40) {
      if (!this.isOpen) {
        this.loadSuggestions();
      } else {
        this.updateSelection(1);
      }
      e.preventDefault();
    }
  }

  open() {
    this.isOpen = true;
    this.positionController.enable();
  }

  close() {
    this.suggestionRequest++;
    this.isOpen = false;
    this.updateSuggestions();
    this.selectedIndex = undefined;
    this.positionController?.disable();
  }

  hasSuggestions() {
    return this.suggestions.total.length > 0;
  }

  async loadSuggestions() {
    if (!this.isConnected || !this.input) return;
    const request = ++this.suggestionRequest;
    const query = this.inputValue;
    let suggestionIndex = 0;

    function nextIndex() {
      return suggestionIndex++;
    }

    // Tag suggestions
    const tags = await cache.getTags();
    let tagSuggestions = [];
    const currentWord = getCurrentWord(this.input);
    if (currentWord && currentWord.length > 1 && currentWord[0] === "#") {
      const searchTag = currentWord.substring(1, currentWord.length);
      tagSuggestions = (tags || [])
        .filter(
          (tag) =>
            tag.name.toLowerCase().indexOf(searchTag.toLowerCase()) === 0,
        )
        .slice(0, 5)
        .map((tag) => ({
          type: "tag",
          index: nextIndex(),
          label: `#${tag.name}`,
          tagName: tag.name,
        }));
    }

    // Recent search suggestions
    const recentSearches = this.searchHistory
      .getRecentSearches(query, 5)
      .map((value) => ({
        type: "search",
        index: nextIndex(),
        label: value,
        value,
      }));

    // Bookmark suggestions
    let bookmarks = [];

    if (query && query.length >= 3) {
      const path = this.mode ? `/${this.mode}` : "";
      const suggestionSearch = {
        user: this.user,
        shared: this.shared,
        unread: this.unread,
        q: query,
      };
      if (this.mode !== "shared") {
        Object.assign(suggestionSearch, {
          sort: this.sort,
          modified_since: this.modifiedSince,
          added_since: this.addedSince,
        });
        if (this.bundle) suggestionSearch.bundle = this.bundle;
      }
      const fetchedBookmarks = await api.listBookmarks(suggestionSearch, {
        limit: 5,
        offset: 0,
        path,
      });
      bookmarks = fetchedBookmarks.map((bookmark) => {
        const fullLabel = bookmark.title || bookmark.url;
        const label = clampText(fullLabel, 60);
        return {
          type: "bookmark",
          index: nextIndex(),
          label,
          bookmark,
        };
      });
    }

    if (
      request !== this.suggestionRequest ||
      query !== this.inputValue ||
      !this.isConnected
    ) {
      return;
    }
    this.updateSuggestions(recentSearches, bookmarks, tagSuggestions);

    if (this.hasSuggestions()) {
      this.open();
    } else {
      this.close();
    }
  }

  updateSuggestions(recentSearches, bookmarks, tagSuggestions) {
    recentSearches = recentSearches || [];
    bookmarks = bookmarks || [];
    tagSuggestions = tagSuggestions || [];
    this.suggestions = {
      recentSearches,
      bookmarks,
      tags: tagSuggestions,
      total: [...tagSuggestions, ...recentSearches, ...bookmarks],
    };
  }

  completeSuggestion(suggestion) {
    if (suggestion.type === "search") {
      this.inputValue = suggestion.value;
      this.close();
    }
    if (suggestion.type === "bookmark") {
      window.open(suggestion.bookmark.url, this.target);
      this.close();
    }
    if (suggestion.type === "tag") {
      const bounds = getCurrentWordBounds(this.input);
      const inputValue = this.input.value;
      this.input.value =
        inputValue.substring(0, bounds.start) +
        `#${suggestion.tagName} ` +
        inputValue.substring(bounds.end);
      this.inputValue = this.input.value;
      this.close();
    }
  }

  updateSelection(dir) {
    const length = this.suggestions.total.length;

    if (length === 0) return;

    if (this.selectedIndex === undefined) {
      this.selectedIndex = dir > 0 ? 0 : Math.max(length - 1, 0);
      return;
    }

    let newIndex = this.selectedIndex + dir;

    if (newIndex < 0) newIndex = Math.max(length - 1, 0);
    if (newIndex >= length) newIndex = 0;

    this.selectedIndex = newIndex;
  }

  renderSuggestions(suggestions, title) {
    if (suggestions.length === 0) return "";

    return html`
      <li class="menu-item group-item">${title}</li>
      ${suggestions.map(
        (suggestion) => html`
          <li
            class="menu-item ${this.selectedIndex === suggestion.index
              ? "selected"
              : ""}"
          >
            <a
              href="#"
              @mousedown=${(e) => {
                e.preventDefault();
                this.completeSuggestion(suggestion);
              }}
            >
              ${suggestion.label}
            </a>
          </li>
        `,
      )}
    `;
  }

  render() {
    return html`
      <div class="form-autocomplete">
        <div
          class="form-autocomplete-input form-input ${this.isFocus
            ? "is-focused"
            : ""}"
        >
          ${this.scopeName
            ? html`
                <span class="search-scope-chip">
                  <span class="search-scope-name" title=${this.scopeName}
                    >In: ${this.scopeName}</span
                  >
                  <button
                    type="button"
                    class="btn btn-link search-scope-remove"
                    aria-label=${this.removeLabel}
                    title=${this.removeLabel}
                    @click=${(e) => this.changeScope(e, this.unbundleUrl)}
                  >
                    <span aria-hidden="true">×</span>
                  </button>
                </span>
              `
            : ""}
          <input
            type="search"
            class="form-input"
            name="${this.inputName}"
            placeholder="${this.inputPlaceholder}"
            autocomplete="off"
            .value="${this.inputValue}"
            @input=${this.handleInput}
            @keydown=${this.handleKeyDown}
            @focus=${this.handleFocus}
            @blur=${this.handleBlur}
          />
        </div>

        <ul class="menu ${this.isOpen ? "open" : ""}">
          ${this.renderSuggestions(this.suggestions.tags, "Tags")}
          ${this.renderSuggestions(
            this.suggestions.recentSearches,
            "Recent Searches",
          )}
          ${this.renderSuggestions(this.suggestions.bookmarks, "Bookmarks")}
        </ul>
      </div>
      ${this.scopeLabel && !this.scopeName
        ? html`
            <div class="search-scope-row">
              <span>${this.scopeLabel}</span>
              ${this.returnUrl
                ? html`
                    <a
                      href=${this.returnUrl}
                      title="Back to ${this.returnName}"
                      @click=${(e) => this.changeScope(e, this.returnUrl)}
                      >Back to ${this.returnName}</a
                    >
                  `
                : ""}
            </div>
          `
        : ""}
    `;
  }
}

customElements.define("ld-search-autocomplete", SearchAutocomplete);
