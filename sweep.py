"""Dev-only: open every Anki window and screenshot it, in light and dark.

Run Anki with ANKI_MN_SWEEP=/some/dir. Each window is opened, captured to
<dir>/<light|dark>-<name>.png and closed without accepting, so nothing in the
collection changes. Anki's theme setting is restored at the end. Use it after
a style change to check every window at once.
"""

from __future__ import annotations

import os
import traceback

from aqt import gui_hooks, mw
from aqt.qt import QApplication, QDialog, QTimer

OUT = os.environ["ANKI_MN_SWEEP"]
os.makedirs(OUT, exist_ok=True)
_log = open(os.path.join(OUT, "sweep-log.txt"), "a", buffering=1)


def log(msg: str) -> None:
    _log.write(msg + "\n")


def _visible() -> dict:
    return {id(w): w for w in QApplication.topLevelWidgets() if w.isVisible()}


def _card():
    ids = mw.col.find_cards("")
    return mw.col.get_card(ids[0]) if ids else None


def _windows() -> list[tuple[str, callable]]:
    import aqt

    def card_info():
        from aqt.browser.card_info import CardInfoDialog

        CardInfoDialog(parent=mw, mw=mw, card=_card())

    def change_notetype():
        from aqt.changenotetype import change_notetype_dialog

        change_notetype_dialog(parent=mw, note_ids=[_card().nid])

    def note_types():
        from aqt.models import Models

        Models(mw, parent=mw)

    def fields():
        from aqt.fields import FieldDialog

        FieldDialog(mw, _card().note_type(), parent=mw)

    def card_templates():
        from aqt.clayout import CardLayout

        card = _card()
        CardLayout(mw, card.note(), ord=card.ord, parent=mw, fill_empty=False)

    def filtered_deck():
        from aqt.filtered_deck import FilteredDeckConfigDialog

        FilteredDeckConfigDialog(mw)

    def custom_study():
        from aqt.customstudy import CustomStudy

        CustomStudy.fetch_data_and_show(mw)

    def choose_deck():
        from aqt.studydeck import StudyDeck

        StudyDeck(mw, accept="Choose", title="Choose Deck", parent=mw, callback=lambda _r: None)

    def about():
        from aqt import about as about_window

        about_window.show(mw)

    def addons():
        from aqt.addons import AddonsDialog

        AddonsDialog(mw.addonManager)

    def find_replace():
        from aqt.browser.find_and_replace import FindAndReplaceDialog

        FindAndReplaceDialog(mw, mw=mw, note_ids=[_card().nid])

    def export():
        from aqt.import_export.exporting import ExportDialog

        ExportDialog(mw)

    def import_csv():
        from aqt.import_export.importing import import_file

        path = os.path.join(OUT, "sample.csv")
        with open(path, "w") as f:
            f.write("front,back\nWhat is ATP?,The cell's energy currency\n")
        import_file(mw, path)

    def deck_description():
        from aqt.deckdescription import DeckDescriptionDialog

        DeckDescriptionDialog(mw)

    def set_due_date():
        from aqt.operations.scheduling import set_due_date_dialog

        set_due_date_dialog(parent=mw, card_ids=[_card().id], config_key=None)

    def find_duplicates():
        from aqt.browser.find_duplicates import FindDuplicatesDialog

        FindDuplicatesDialog(browser=aqt.dialogs.open("Browser", mw), mw=mw)

    def empty_cards():
        # Opens only when the collection has empty cards; otherwise Anki shows
        # a tooltip and the sweep logs "no window opened".
        from aqt.emptycards import show_empty_cards

        show_empty_cards(mw)

    def sync_sign_in():
        # Cancelled by the sweep, so nothing is sent.
        from aqt.sync import get_id_and_pass_from_user

        get_id_and_pass_from_user(mw, lambda *_args: None)

    def profiles():
        # The real Profiles window unloads the collection; this is the same
        # form without its handlers, so closing it can't switch or quit.
        from aqt.forms import profiles as profiles_form
        from aqt.qt import QMainWindow

        window = QMainWindow(mw)
        form = profiles_form.Ui_MainWindow()
        form.setupUi(window)
        form.profiles.addItems(mw.pm.profiles())
        form.profiles.setCurrentRow(0)
        window.show()

    def deck_options():
        from aqt.deckoptions import display_options_for_deck_id

        display_options_for_deck_id(mw.col.decks.get_current_id())

    windows = [
        ("browser", lambda: aqt.dialogs.open("Browser", mw)),
        ("add", lambda: aqt.dialogs.open("AddCards", mw)),
        ("preferences", mw.onPrefs),
        ("stats", mw.onStats),
        ("deck-options", deck_options),
        ("filtered-deck", filtered_deck),
        ("custom-study", custom_study),
        ("choose-deck", choose_deck),
        ("note-types", note_types),
        ("export", export),
        ("import-csv", import_csv),
        ("deck-description", deck_description),
        ("addons", addons),
        ("about", about),
        ("empty-cards", empty_cards),
        ("sync-sign-in", sync_sign_in),
        ("profiles", profiles),
    ]
    if _card():
        windows += [
            ("card-info", card_info),
            ("change-notetype", change_notetype),
            ("fields", fields),
            ("card-templates", card_templates),
            ("find-replace", find_replace),
            ("find-duplicates", find_duplicates),
            ("set-due-date", set_due_date),
        ]
    return windows


def _open_and_capture(name: str, opener, done) -> None:
    before = _visible()

    def capture() -> None:
        new = [w for k, w in _visible().items() if k not in before]
        if not new:
            log(f"{name}: no window opened")
            done()
            return
        target = max(new, key=lambda w: w.width() * w.height())
        target.resize(min(target.width(), 1300), min(target.height(), 900))

        def shot() -> None:
            target.grab().save(os.path.join(OUT, f"{name}.png"))
            log(f"{name}: {type(target).__name__}")
            for w in new:
                try:
                    w.reject() if isinstance(w, QDialog) else w.close()
                except Exception:
                    w.close()
            QTimer.singleShot(1200, done)

        QTimer.singleShot(800, shot)

    # Scheduled first: modal dialogs block in opener() until capture closes them.
    QTimer.singleShot(3500, capture)
    try:
        opener()
    except Exception:
        log(f"{name}: failed to open\n{traceback.format_exc()}")


def _set_theme(theme) -> None:
    from aqt.theme import theme_manager

    mw.pm.set_theme(theme)
    theme_manager.apply_style()
    mw.reset()


def _run() -> None:
    from aqt.theme import Theme

    original = mw.pm.theme()
    queue: list = []
    for prefix, theme in (("light", Theme.LIGHT), ("dark", Theme.DARK)):
        queue.append(lambda t=theme: _set_theme(t))
        for name, opener in _windows():
            queue.append((f"{prefix}-{name}", opener))

    def step() -> None:
        if not queue:
            _set_theme(original)
            log("done")
            return
        item = queue.pop(0)
        if callable(item):
            item()
            QTimer.singleShot(1500, step)
        else:
            _open_and_capture(item[0], item[1], step)

    step()


gui_hooks.profile_did_open.append(lambda: QTimer.singleShot(4000, _run))
