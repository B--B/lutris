"""Extended combobox with search"""

from gi.repository import GLib, GObject, Gtk

from lutris.gui.dialogs import display_error


class SearchableCombobox(Gtk.Box):
    """Combo box with autocompletion.
    Well fitted for large lists.
    """

    __gsignals__ = {
        "changed": (GObject.SIGNAL_RUN_FIRST, None, (str,)),
    }

    def __init__(self, choice_func, initial=None):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL)
        self.initial = initial
        self.liststore = Gtk.ListStore(str, str)
        self.entry = Gtk.Entry()

        self.completion = Gtk.EntryCompletion()
        self.completion.set_model(self.liststore)
        self.completion.set_text_column(0)
        self.completion.set_match_func(self.search_store)
        self.entry.set_icon_from_icon_name(
            Gtk.EntryIconPosition.PRIMARY,
            "content-loading-symbolic"
        )
        self.entry.set_completion(self.completion)

        self.entry.connect("changed", self.on_combobox_change)
        self.entry.connect("scroll-event", self._on_combobox_scroll)
        # pack_start deprecated in Gtk4, append should be used
        self.pack_start(self.entry, True, True, 0)
        GLib.idle_add(self._populate_combobox_choices, choice_func)

    def get_model(self):
        """Proxy to the liststore"""
        return self.liststore

    def get_active_id(self):
        """Proxy to the get_active method"""
        text = self.entry.get_text()
        for row in self.liststore:
            if row[0] == text:
                return row[1]
        return None

    @staticmethod
    def get_has_entry():
        """The entry present is not for editing custom values, only search"""
        return False

    def search_store(self, _completion, string, _iter):
        """Return true if any word of a string is present in a row"""
        for word in string.split():
            if word not in self.liststore[_iter][0].lower():  # search is always lower case
                return False
        return True

    def _populate_combobox_choices(self, choice_func):
        try:
            for choice in choice_func():
                self.liststore.append(choice)
            if self.initial:
                for row in self.liststore:
                    if row[1] == self.initial:
                        self.entry.set_text(row[0])
                        break
        except Exception as ex:
            self.entry.set_icon_from_icon_name(
                Gtk.EntryIconPosition.PRIMARY,
                "dialog-error-symbolic"
            )
            # get_toplevel deprecated in Gtk4, get_root should be used
            display_error(ex, parent=self.get_toplevel())

        self.entry.set_icon_from_icon_name(
            Gtk.EntryIconPosition.PRIMARY,
            None
        )

    @staticmethod
    def _on_combobox_scroll(combobox, _event):
        """Prevents users from accidentally changing configuration values
        while scrolling down dialogs.
        """
        combobox.stop_emission_by_name("scroll-event")
        return False

    def on_combobox_change(self, _widget):
        """Action triggered on combobox 'changed' signal."""
        active_id = self.get_active_id()  # Obtain the active ID
        if active_id is None:
            return
        self.emit("changed", active_id)
