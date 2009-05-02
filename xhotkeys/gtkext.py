#!/usr/bin/python
import gtk

from kiwi.ui import gadgets
from kiwi.ui.delegates import Delegate, SlaveDelegate
from kiwi.ui.objectlist import ObjectList, Column
from kiwi.ui.dialogs import yesno

#####  ObjectListBox start
def get_current_row_iter(treeview):
    model = treeview.get_model()
    iter1 = treeview.get_selection().get_selected()[1]
    return iter1

def can_current_row_move(treeview, offset):
    """Swap selected row on a GTK Treeview"""
    iter1 = get_current_row_iter(treeview)
    if not iter1:
        return False            
    model = treeview.get_model()
    path = model.get_path(iter1)[0]                
    return (path+offset >= 0 and path+offset < len(model))

def move_current_row(treeview, offset):
    """Swap selected row on a GTK Treeview"""         
    if not can_current_row_move(treeview, offset):
        return
    iter1 = get_current_row_iter(treeview)
    model = treeview.get_model()
    path1 = model.get_path(iter1)[0]
    iter2 = model.get_iter(path1+offset)
    model.swap(iter1, iter2)

class ObjectListBox(gtk.HBox):
    def __init__(self, columns, values):
        gtk.HBox.__init__(self)
        # Object list
        object_list = ObjectList(columns, values, sortable=False)
        self.object_list = object_list
        self.pack_start(object_list)
        actions_box = gtk.VBox()
        self.pack_start(actions_box, expand=False, fill=False)
        object_list.connect('selection-changed', self.on_item_selected)
        # Actions box
        self.actions_box = actions_box
        move_up = gtk.Button(label="Move Up", stock=gtk.STOCK_GO_UP)
        actions_box.pack_start(move_up, expand=False, fill=False)
        move_up.connect("clicked", self.on_move_up__clicked)
        move_down = gtk.Button(label="Move Down", stock=gtk.STOCK_GO_DOWN)
        move_down.connect("clicked", self.on_move_down__clicked)
        actions_box.pack_start(move_down, expand=False, fill=False)
        self.move_up = move_up
        self.move_down = move_down
        # Set initial up/down buttons sensitivity
        self.on_item_selected(self.object_list, None)

    def on_item_selected(self, object_list, item):
        can_move_up = can_current_row_move(self.object_list.get_treeview(), -1)
        self.move_up.set_sensitive(can_move_up)
        can_move_down = can_current_row_move(self.object_list.get_treeview(), +1)
        self.move_down.set_sensitive(can_move_down)
            
    def on_move_up__clicked(self, button):
        move_current_row(self.object_list.get_treeview(), -1)
        self.on_item_selected(self.object_list, None)

    def on_move_down__clicked(self, button):
        move_current_row(self.object_list.get_treeview(), +1)
        self.on_item_selected(self.object_list, None)

#####  ObjectListBox end

