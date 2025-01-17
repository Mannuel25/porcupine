# TODO: test overlapping matches

import itertools
import random
import sys

import pytest

from porcupine import get_main_window
from porcupine.plugins import find


@pytest.fixture
def filetab_and_finder(filetab):
    [finder] = [w for w in filetab.bottom_frame.winfo_children() if isinstance(w, find.Finder)]
    get_main_window().event_generate("<<Menubar:Edit/Find and Replace>>")
    return (filetab, finder)


# i don't know why, but this does not work on windows
@pytest.mark.skipif(
    sys.platform == "win32", reason="focus_get() doesn't work on windows like this test assumes"
)
def test_key_bindings_that_are_annoying_if_they_dont_work(filetab_and_finder):
    filetab, finder = filetab_and_finder
    assert filetab.focus_get() is filetab.textwidget

    get_main_window().event_generate("<<Menubar:Edit/Find and Replace>>")
    filetab.update()
    assert filetab.focus_get() is finder.find_entry

    finder.hide()
    filetab.update()
    assert filetab.focus_get() is filetab.textwidget


# invoke doesn't work with disabled button
# but key bindings can do what clicking the button would do
def click_disabled_button(button):
    assert str(button["state"]) == "disabled"
    button.tk.eval(button["command"])


def test_initial_button_states(filetab_and_finder):
    finder = filetab_and_finder[1]
    all_buttons = [
        finder.previous_button,
        finder.next_button,
        finder.replace_this_button,
        finder.replace_all_button,
    ]

    # all buttons should be disabled because the find entry is empty
    assert finder.statuslabel["text"] == "Type something to find."
    for button in all_buttons:
        assert str(button["state"]) == "disabled"

    # i had a bug that occurred when typing something to the find area and
    # backspacing it out because it called highlight_all_matches()
    finder.highlight_all_matches()
    assert finder.statuslabel["text"] == "Type something to find."
    for button in all_buttons:
        assert str(button["state"]) == "disabled"


def test_initial_checkbox_states(filetab_and_finder):
    finder = filetab_and_finder[1]
    assert not finder.ignore_case_var.get()


def test_finding(filetab_and_finder):
    filetab, finder = filetab_and_finder
    filetab.textwidget.insert("end", "this is a test\nthis is fun")

    def search_for(substring):
        finder.find_entry.delete(0, "end")
        finder.find_entry.insert(0, substring)
        assert finder.find_entry.get() == substring
        result = list(map(str, filetab.textwidget.tag_ranges("find_highlight")))

        buttons = [finder.previous_button, finder.next_button, finder.replace_all_button]
        states = {str(button["state"]) for button in buttons}
        assert len(states) == 1, "not all buttons have the same state"

        if finder.statuslabel["text"] in {"Found no matches :(", "Type something to find."}:
            assert states == {"disabled"}
        else:
            assert states == {"normal"}

        return result

    assert search_for("is") == [
        # thIS is a test
        "1.2",
        "1.4",
        # this IS a test
        "1.5",
        "1.7",
        # thIS is fun
        "2.2",
        "2.4",
        # this IS fun
        "2.5",
        "2.7",
    ]
    assert finder.statuslabel["text"] == "Found 4 matches."

    assert search_for("n") == ["2.10", "2.11"]  # fuN
    assert finder.statuslabel["text"] == "Found 1 match."

    # corner case: match in the beginning of file
    assert search_for("this is a") == ["1.0", "1.9"]
    assert finder.statuslabel["text"] == "Found 1 match."

    assert search_for("This Is A") == []
    assert finder.statuslabel["text"] == "Found no matches :("


def test_ignore_case_and_full_words_only(filetab_and_finder):
    filetab, finder = filetab_and_finder

    def find_stuff():
        finder.highlight_all_matches()
        return list(map(str, filetab.textwidget.tag_ranges("find_highlight")))

    filetab.textwidget.insert("1.0", "Asd asd dasd asd asda asd ASDA ASD")
    finder.find_entry.insert(0, "asd")

    assert find_stuff() == [
        "1.4",
        "1.7",
        "1.9",
        "1.12",
        "1.13",
        "1.16",
        "1.17",
        "1.20",
        "1.22",
        "1.25",
    ]

    finder.full_words_var.set(True)
    assert find_stuff() == ["1.4", "1.7", "1.13", "1.16", "1.22", "1.25"]

    finder.ignore_case_var.set(True)
    assert find_stuff() == [
        "1.0",
        "1.3",
        "1.4",
        "1.7",
        "1.13",
        "1.16",
        "1.22",
        "1.25",
        "1.31",
        "1.34",
    ]

    finder.full_words_var.set(False)
    assert find_stuff() == [
        "1.0",
        "1.3",
        "1.4",
        "1.7",
        "1.9",
        "1.12",
        "1.13",
        "1.16",
        "1.17",
        "1.20",
        "1.22",
        "1.25",
        "1.26",
        "1.29",
        "1.31",
        "1.34",
    ]


def test_full_words_can_contain_anything(filetab_and_finder):
    filetab, finder = filetab_and_finder
    finder.full_words_var.set(True)
    filetab.textwidget.insert("1.0", "foo.bar foo.baz")

    finder.find_entry.insert(0, "foo.")
    assert finder.statuslabel["text"].startswith('"foo." is not a valid word')
    assert not get_match_ranges(finder)

    finder.find_entry.insert("end", "bar")  # "foo." + "bar"
    assert finder.statuslabel["text"] == "Found 1 match."
    assert get_match_ranges(finder) == [("1.0", "1.7")]


def test_basic_statuses_and_previous_and_next_match_buttons(filetab_and_finder):
    filetab, finder = filetab_and_finder
    filetab.textwidget.insert("1.0", "asd asd asd\nasd asd")
    filetab.textwidget.mark_set("insert", "1.0")

    finder.find_entry.insert(0, "no matches for this")
    finder.highlight_all_matches()
    assert finder.statuslabel["text"] == "Found no matches :("

    for button in [finder.previous_button, finder.next_button, finder.replace_all_button]:
        assert str(button["state"]) == "disabled"

    for button in [finder.previous_button, finder.next_button]:
        click_disabled_button(button)  # shouldn't do anything
        assert finder.statuslabel["text"] == "Found no matches :("

    finder.find_entry.delete(0, "end")
    finder.find_entry.insert(0, "asd")

    finder.highlight_all_matches()
    assert finder.statuslabel["text"] == "Found 5 matches."

    def get_selected():
        start, end = map(str, filetab.textwidget.tag_ranges("sel"))
        start2, end2 = map(str, filetab.textwidget.tag_ranges("find_highlight_selected"))
        assert start == start2
        assert end == end2
        assert filetab.textwidget.index("insert") == start
        return (start, end)

    selecteds = [("1.0", "1.3"), ("1.4", "1.7"), ("1.8", "1.11"), ("2.0", "2.3"), ("2.4", "2.7")]

    tag_locations = filetab.textwidget.tag_ranges("find_highlight")
    flatten = itertools.chain.from_iterable
    assert list(map(str, tag_locations)) == list(flatten(selecteds))

    finder.next_button.invoke()  # highlight first match
    assert finder.statuslabel["text"] == "Match 1/5"
    assert get_selected() == selecteds[0]

    index = 0
    for lol in range(500):  # many times back and forth to check corner cases
        if random.choice([True, False]):
            finder.previous_button.invoke()
            index = (index - 1) % len(selecteds)
        else:
            finder.next_button.invoke()
            index = (index + 1) % len(selecteds)

        assert finder.statuslabel["text"] == f"Match {index + 1}/5"
        assert get_selected() == selecteds[index]


def get_match_ranges(finder):
    return [
        (finder._textwidget.index(f"{tag}.first"), finder._textwidget.index(f"{tag}.last"))
        for tag in finder.get_match_tags()
    ]


def test_replace(filetab_and_finder):
    # replacing 'asd' with 'asda' tests corner cases well because:
    #   - 'asda' contains 'asd', so must avoid infinite loops
    #   - replacing 'asd' with 'asda' throws off indexes after the replaced
    #     area, and the finder must handle this
    filetab, finder = filetab_and_finder
    filetab.textwidget.insert("1.0", "asd asd asd")
    finder.find_entry.insert(0, "asd")
    finder.replace_entry.insert(0, "asda")

    finder.highlight_all_matches()
    assert str(finder.replace_this_button["state"]) == "disabled"
    assert get_match_ranges(finder) == [("1.0", "1.3"), ("1.4", "1.7"), ("1.8", "1.11")]

    click_disabled_button(finder.replace_this_button)
    assert finder.statuslabel["text"] == 'Click "Previous match" or "Next match" first.'

    finder.next_button.invoke()
    assert str(finder.replace_this_button["state"]) == "normal"
    assert get_match_ranges(finder) == [("1.0", "1.3"), ("1.4", "1.7"), ("1.8", "1.11")]

    finder.replace_this_button.invoke()
    assert str(finder.replace_this_button["state"]) == "normal"
    assert finder.statuslabel["text"] == "Replaced a match. There are 2 more matches."
    assert get_match_ranges(finder) == [("1.5", "1.8"), ("1.9", "1.12")]

    finder.replace_this_button.invoke()
    assert str(finder.replace_this_button["state"]) == "normal"
    assert finder.statuslabel["text"] == "Replaced a match. There is 1 more match."
    assert get_match_ranges(finder) == [("1.10", "1.13")]

    assert str(finder.previous_button["state"]) == "normal"
    assert str(finder.next_button["state"]) == "normal"

    finder.replace_this_button.invoke()
    filetab.update()
    assert str(finder.replace_this_button["state"]) == "disabled"
    assert str(finder.previous_button["state"]) == "disabled"
    assert str(finder.next_button["state"]) == "disabled"
    assert str(finder.replace_all_button["state"]) == "disabled"
    assert finder.statuslabel["text"] == "Replaced the last match."
    assert get_match_ranges(finder) == []


# if this passes with no code to specially handle this, the replacing code
# seems to handle corner cases well
def test_replace_asd_with_asd(filetab_and_finder):
    filetab, finder = filetab_and_finder
    filetab.textwidget.insert("1.0", "asd asd")
    finder.find_entry.insert(0, "asd")
    finder.replace_entry.insert(0, "asd")

    finder.highlight_all_matches()
    assert str(finder.replace_this_button["state"]) == "disabled"
    assert get_match_ranges(finder) == [("1.0", "1.3"), ("1.4", "1.7")]

    finder.next_button.invoke()
    assert str(finder.replace_this_button["state"]) == "normal"
    assert get_match_ranges(finder) == [("1.0", "1.3"), ("1.4", "1.7")]

    finder.replace_this_button.invoke()
    assert str(finder.replace_this_button["state"]) == "normal"
    assert finder.statuslabel["text"] == "Replaced a match. There is 1 more match."
    assert get_match_ranges(finder) == [("1.4", "1.7")]

    finder.replace_this_button.invoke()
    filetab.update()
    assert str(finder.replace_this_button["state"]) == "disabled"
    assert finder.statuslabel["text"] == "Replaced the last match."
    assert get_match_ranges(finder) == []


def test_replace_all(filetab_and_finder):
    filetab, finder = filetab_and_finder
    filetab.textwidget.insert("1.0", "asd asd asd")
    finder.find_entry.insert(0, "asd")
    finder.replace_entry.insert(0, "asda")

    finder.highlight_all_matches()
    assert str(finder.replace_this_button["state"]) == "disabled"
    assert get_match_ranges(finder) == [("1.0", "1.3"), ("1.4", "1.7"), ("1.8", "1.11")]

    finder.next_button.invoke()
    assert str(finder.replace_this_button["state"]) == "normal"
    assert get_match_ranges(finder) == [("1.0", "1.3"), ("1.4", "1.7"), ("1.8", "1.11")]

    finder.replace_this_button.invoke()
    assert str(finder.replace_this_button["state"]) == "normal"
    assert finder.statuslabel["text"] == "Replaced a match. There are 2 more matches."
    assert get_match_ranges(finder) == [("1.5", "1.8"), ("1.9", "1.12")]

    finder.replace_all_button.invoke()
    assert str(finder.replace_this_button["state"]) == "disabled"
    assert str(finder.previous_button["state"]) == "disabled"
    assert str(finder.next_button["state"]) == "disabled"
    assert str(finder.replace_all_button["state"]) == "disabled"
    assert finder.statuslabel["text"] == "Replaced 2 matches."
    assert get_match_ranges(finder) == []
    assert filetab.textwidget.get("1.0", "end - 1 char") == "asda asda asda"

    filetab.textwidget.delete("1.3", "end")
    assert filetab.textwidget.get("1.0", "end - 1 char") == "asd"
    finder.highlight_all_matches()
    assert str(finder.replace_all_button["state"]) == "normal"
    finder.replace_all_button.invoke()
    assert filetab.textwidget.get("1.0", "end - 1 char") == "asda"
    assert finder.statuslabel["text"] == "Replaced 1 match."


def test_selecting_messing_up_button_disableds(filetab_and_finder):
    filetab, finder = filetab_and_finder
    filetab.textwidget.insert("end", "asd")

    finder.find_entry.insert(0, "asd")
    finder.highlight_all_matches()

    finder.next_button.invoke()
    assert str(finder.replace_this_button["state"]) == "normal"

    # "Replace this match" doesn't make sense after changing the selection
    # because no match is selected to be the "this" match
    filetab.textwidget.tag_remove("sel", "1.2", "end")
    filetab.update()
    assert filetab.textwidget.get("sel.first", "sel.last") == "as"
    assert str(finder.replace_this_button["state"]) == "disabled"


def test_find_selected(filetab_and_finder):
    filetab, finder = filetab_and_finder
    finder.hide()
    filetab.textwidget.insert("end", "foo bar baz bar")
    filetab.textwidget.mark_set("insert", "1.4")
    filetab.textwidget.tag_add("sel", "1.4", "1.7")

    finder.show()
    assert finder.find_entry.get() == "bar"
    assert finder.find_entry.selection_present()
    assert not finder.replace_entry.get()
    assert list(map(str, filetab.textwidget.tag_ranges("find_highlight"))) == [
        "1.4",
        "1.7",
        "1.12",
        "1.15",
    ]

    finder.hide()
    assert filetab.textwidget.index("insert") == "1.4"


def test_highlight_text(filetab_and_finder):
    filetab, finder = filetab_and_finder
    finder.find_entry.insert("end", "foo")
    finder.find_entry.icursor(1)
    finder.hide()
    finder.show()

    assert finder.find_entry.get() == "foo"
    assert finder.find_entry.selection_present()
    assert finder.find_entry.index("insert") == 1  # remember cursor location


def test_highight_on_undo(filetab_and_finder):
    filetab, finder = filetab_and_finder
    filetab.textwidget.insert("end", "foo")
    finder.find_entry.insert("end", "foo")

    finder.replace_entry.insert("end", "baz")
    finder.replace_all_button.invoke()
    assert filetab.textwidget.get("1.0", "end - 1 char") == "baz"
    filetab.update()
    filetab.textwidget.event_generate("<<Undo>>")
    assert filetab.textwidget.get("1.0", "end - 1 char") == "foo"
    filetab.update()
    assert filetab.textwidget.tag_ranges("find_highlight")


def test_undo_replace_all(filetab_and_finder):
    filetab, finder = filetab_and_finder
    filetab.textwidget.insert("end", "foo bar foo")
    finder.find_entry.insert("end", "foo")

    finder.replace_entry.insert("end", "baz")
    finder.replace_all_button.invoke()
    assert filetab.textwidget.get("1.0", "end - 1 char") == "baz bar baz"
    filetab.textwidget.edit_undo()
    assert filetab.textwidget.get("1.0", "end - 1 char") == "foo bar foo"


def test_replace_this_match(filetab_and_finder):
    filetab, finder = filetab_and_finder
    filetab.textwidget.insert("end", "foo bar baz")
    finder.find_entry.insert("end", "bar")
    finder.replace_entry.insert("end", "lol")

    finder.next_button.invoke()
    finder.replace_this_button.invoke()
    assert filetab.textwidget.get("1.0", "end - 1 char") == "foo lol baz"
    filetab.textwidget.edit_undo()
    assert filetab.textwidget.get("1.0", "end - 1 char") == "foo bar baz"


def test_replace_this_greyed_out(filetab_and_finder):
    filetab, finder = filetab_and_finder
    filetab.textwidget.insert("end", "foo bar foo")
    filetab.textwidget.mark_set("insert", "1.0")
    filetab.textwidget.tag_add("sel", "1.0", "1.3")  # Select foo so it goes to find entry
    finder.show()

    finder.replace_entry.insert("end", "baz")
    assert str(finder.replace_this_button["state"]) == "disabled"


def test_find_r_from_rr(filetab_and_finder):
    filetab, finder = filetab_and_finder
    filetab.textwidget.insert("end", "rr")
    finder.show()
    finder.find_entry.insert("end", "r")
    assert get_match_ranges(finder) == [("1.0", "1.1"), ("1.1", "1.2")]
