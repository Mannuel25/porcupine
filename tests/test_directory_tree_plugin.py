import shutil
import sys
from pathlib import Path

import pytest

from porcupine.plugins import directory_tree as plugin_module
from porcupine.plugins.directory_tree import _focus_treeview, _stringify_path, get_path


def test_adding_nested_projects(tree, tmp_path):
    def get_paths():
        return [get_path(project) for project in tree.get_children()]

    (tmp_path / "a" / "b").mkdir(parents=True)
    assert get_paths() == []
    tree.add_project(tmp_path / "a")
    assert get_paths() == [tmp_path / "a"]
    tree.add_project(tmp_path / "a" / "b")
    assert get_paths() == [tmp_path / "a" / "b", tmp_path / "a"]
    tree.add_project(tmp_path)
    assert get_paths() == [tmp_path, tmp_path / "a" / "b", tmp_path / "a"]


@pytest.mark.skipif(sys.platform == "win32", reason="rmtree can magically fail on windows")
def test_deleting_project(tree, tmp_path, tabmanager):
    def get_project_names():
        return [get_path(project).name for project in tree.get_children()]

    (tmp_path / "a").mkdir(parents=True)
    (tmp_path / "b").mkdir(parents=True)
    (tmp_path / "a" / "README").touch()
    (tmp_path / "b" / "README").touch()

    a_tab = tabmanager.open_file(tmp_path / "a" / "README")
    assert get_project_names() == ["a"]

    tabmanager.close_tab(a_tab)
    shutil.rmtree(tmp_path / "a")
    tabmanager.open_file(tmp_path / "b" / "README")
    assert get_project_names() == ["b"]


def test_autoclose(tree, tmp_path, tabmanager, monkeypatch):
    def get_project_names():
        return [get_path(project).name for project in tree.get_children()]

    (tmp_path / "a").mkdir(parents=True)
    (tmp_path / "b").mkdir(parents=True)
    (tmp_path / "c").mkdir(parents=True)
    (tmp_path / "a" / "README").touch()
    (tmp_path / "b" / "README").touch()
    (tmp_path / "c" / "README").touch()
    monkeypatch.setattr(plugin_module, "_MAX_PROJECTS", 2)

    assert get_project_names() == []

    a_tab = tabmanager.open_file(tmp_path / "a" / "README")
    assert get_project_names() == ["a"]
    b_tab = tabmanager.open_file(tmp_path / "b" / "README")
    assert get_project_names() == ["b", "a"]
    c_tab = tabmanager.open_file(tmp_path / "c" / "README")
    assert get_project_names() == ["c", "b", "a"]

    tabmanager.close_tab(b_tab)
    assert get_project_names() == ["c", "a"]
    tabmanager.close_tab(c_tab)
    assert get_project_names() == ["c", "a"]
    tabmanager.close_tab(a_tab)
    assert get_project_names() == ["c", "a"]


def open_as_if_user_clicked(tree, item):
    tree.selection_set(item)
    tree.item(item, open=True)
    tree.event_generate("<<TreeviewOpen>>")
    tree.update()


def test_select_file(tree, tmp_path, tabmanager):
    (tmp_path / "a").mkdir(parents=True)
    (tmp_path / "b").mkdir(parents=True)
    (tmp_path / "a" / "README").touch()
    (tmp_path / "b" / "README").touch()
    (tmp_path / "b" / "file1").touch()
    (tmp_path / "b" / "file2").touch()

    a_readme = tabmanager.open_file(tmp_path / "a" / "README")
    b_file1 = tabmanager.open_file(tmp_path / "b" / "file1")
    b_file2 = tabmanager.open_file(tmp_path / "b" / "file2")
    tree.update()

    tabmanager.select(a_readme)
    tree.update()
    assert get_path(tree.selection()[0]) == tmp_path / "a"

    tabmanager.select(b_file1)
    tree.update()
    assert get_path(tree.selection()[0]) == tmp_path / "b"

    open_as_if_user_clicked(tree, tree.selection()[0])
    tabmanager.select(b_file1)
    tree.update()
    assert get_path(tree.selection()[0]) == tmp_path / "b" / "file1"

    tabmanager.select(b_file2)
    tree.update()
    assert get_path(tree.selection()[0]) == tmp_path / "b" / "file2"

    b_file2.save_as(tmp_path / "b" / "file3")
    tree.update()
    assert get_path(tree.selection()[0]) == tmp_path / "b" / "file3"

    tabmanager.close_tab(a_readme)
    tabmanager.close_tab(b_file1)
    tabmanager.close_tab(b_file2)


def test_focusing_treeview_with_keyboard_updates_selection(tree, tmp_path):
    (tmp_path / "README").touch()
    (tmp_path / "hello.py").touch()
    tree.add_project(tmp_path, refresh=False)
    _focus_treeview(tree)
    assert tree.selection()


def test_all_files_deleted(tree, tmp_path, tabmanager):
    (tmp_path / "README").touch()
    (tmp_path / "hello.py").touch()
    tree.add_project(tmp_path)
    project_id = tree.get_children()[0]
    tree.selection_set(project_id)

    # Simulate user opening selected item
    tree.item(tree.selection()[0], open=True)
    tree.event_generate("<<TreeviewOpen>>")
    tree.update()
    assert len(tree.get_children(project_id)) == 2

    (tmp_path / "README").unlink()
    (tmp_path / "hello.py").unlink()
    tree.refresh()
    assert tree.contains_dummy(project_id)


def test_nested_projects(tree, tmp_path, tabmanager):
    (tmp_path / "README").touch()
    (tmp_path / "subdir").mkdir()
    (tmp_path / "subdir" / "README").touch()

    tree.add_project(tmp_path)
    [outer_project_id] = [id for id in tree.get_children("") if get_path(id) == tmp_path]

    open_as_if_user_clicked(tree, outer_project_id)
    [subdir_inside_other_project] = [
        item_id
        for item_id in tree.get_children(outer_project_id)
        if get_path(item_id) == tmp_path / "subdir"
    ]
    open_as_if_user_clicked(tree, subdir_inside_other_project)

    assert not tree.contains_dummy(subdir_inside_other_project)
    tree.add_project(tmp_path / "subdir")
    assert tree.contains_dummy(subdir_inside_other_project)
    dummy_id = tree.get_children(subdir_inside_other_project)[0]
    assert tree.item(dummy_id, "text") == "(open as a separate project)"
    [subdir_id] = [id for id in tree.get_children("") if get_path(id) == tmp_path / "subdir"]

    tree.select_file(tmp_path / "subdir" / "README")
    assert tree.selection() == (subdir_id,)
    open_as_if_user_clicked(tree, subdir_id)
    tree.select_file(tmp_path / "subdir" / "README")
    assert get_path(tree.selection()[0]) == tmp_path / "subdir" / "README"


def test_home_folder_displaying():
    assert _stringify_path(Path.home()) == "~"
    assert _stringify_path(Path.home() / "lol") in ["~/lol", r"~\lol"]
    assert "~" not in _stringify_path(Path.home().parent / "asdfggg")


def test_cycling_through_items(tree, tmp_path, tabmanager):
    (tmp_path / "README").touch()
    (tmp_path / "foo.txt").touch()
    (tmp_path / "bar.txt").touch()
    (tmp_path / "baz.txt").touch()

    tree.add_project(tmp_path)
    [project_id] = [id for id in tree.get_children("") if get_path(id) == tmp_path]
    open_as_if_user_clicked(tree, project_id)
    open_as_if_user_clicked(tree, tree.get_children(project_id)[0])

    tree.update()
    tree.focus_force()

    tree.event_generate("f")
    assert get_path(tree.selection()[0]) == tmp_path / "foo.txt"
    tree.event_generate("b")
    assert get_path(tree.selection()[0]) == tmp_path / "bar.txt"
    tree.event_generate("b")
    assert get_path(tree.selection()[0]) == tmp_path / "baz.txt"
    tree.event_generate("b")
    assert get_path(tree.selection()[0]) == tmp_path / "bar.txt"
    tree.event_generate("R")
    assert get_path(tree.selection()[0]) == tmp_path / "README"
    tree.event_generate("R")
    assert get_path(tree.selection()[0]) == tmp_path / "README"
    tree.event_generate("x")
    assert get_path(tree.selection()[0]) == tmp_path / "README"
