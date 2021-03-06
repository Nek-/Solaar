#
#
#

from __future__ import absolute_import, division, print_function, unicode_literals

from gi.repository import Gtk, GLib

from logitech.unifying_receiver import settings as _settings

#
#
#

try:
	from Queue import Queue as _Queue
except ImportError:
	from queue import Queue as _Queue
_apply_queue = _Queue(4)

def _process_apply_queue():
	def _write_start(sbox):
		_, failed, spinner, control = sbox.get_children()
		control.set_sensitive(False)
		failed.set_visible(False)
		spinner.set_visible(True)
		spinner.start()

	while True:
		task = _apply_queue.get()
		assert isinstance(task, tuple)
		# print ("task", *task)
		if task[0] == 'write':
			_, setting, value, sbox = task
			GLib.idle_add(_write_start, sbox, priority=0)
			value = setting.write(value)
		elif task[0] == 'read':
			_, setting, force_read, sbox = task
			value = setting.read(not force_read)
		GLib.idle_add(_update_setting_item, sbox, value, priority=99)

from threading import Thread as _Thread
_queue_processor = _Thread(name='SettingsProcessor', target=_process_apply_queue)
_queue_processor.daemon = True
_queue_processor.start()

#
#
#

def _switch_notify(switch, _, setting, spinner):
	# print ("switch notify", switch, switch.get_active(), setting)
	if switch.get_sensitive():
		# value = setting.write(switch.get_active() == True)
		# _update_setting_item(switch.get_parent(), value)
		_apply_queue.put(('write', setting, switch.get_active() == True, switch.get_parent()))


def _combo_notify(cbbox, setting, spinner):
	# print ("combo notify", cbbox, cbbox.get_active_id(), setting)
	if cbbox.get_sensitive():
		_apply_queue.put(('write', setting, cbbox.get_active_id(), cbbox.get_parent()))


# def _scale_notify(scale, setting, spinner):
# 	_apply_queue.put(('write', setting, scale.get_value(), scale.get_parent()))


# def _snap_to_markers(scale, scroll, value, setting):
# 	value = int(value)
# 	candidate = None
# 	delta = 0xFFFFFFFF
# 	for c in setting.choices:
# 		d = abs(value - int(c))
# 		if d < delta:
# 			candidate = c
# 			delta = d

# 	assert candidate is not None
# 	scale.set_value(int(candidate))
# 	return True


def _add_settings(box, device):
	for s in device.settings:
		sbox = Gtk.HBox(homogeneous=False, spacing=8)
		sbox.pack_start(Gtk.Label(s.label), False, False, 0)

		spinner = Gtk.Spinner()
		spinner.set_tooltip_text('Working...')

		failed = Gtk.Image.new_from_icon_name('dialog-warning', Gtk.IconSize.SMALL_TOOLBAR)
		failed.set_tooltip_text('Failed to read value from the device.')

		if s.kind == _settings.KIND.toggle:
			control = Gtk.Switch()
			control.connect('notify::active', _switch_notify, s, spinner)
		elif s.kind == _settings.KIND.choice:
			control = Gtk.ComboBoxText()
			for entry in s.choices:
				control.append(str(entry), str(entry))
			control.connect('changed', _combo_notify, s, spinner)
		# elif s.kind == _settings.KIND.range:
		# 	first, second = s.choices[:2]
		# 	last = s.choices[-1:][0]
		# 	control = Gtk.HScale.new_with_range(first, last, second - first)
		# 	control.set_draw_value(False)
		# 	control.set_has_origin(False)
		# 	for entry in s.choices:
		# 		control.add_mark(int(entry), Gtk.PositionType.TOP, str(entry))
		# 	control.connect('change-value', _snap_to_markers, s)
		# 	control.connect('value-changed', _scale_notify, s, spinner)
		else:
			raise NotImplemented

		control.set_sensitive(False)  # the first read will enable it
		sbox.pack_end(control, False, False, 0)
		sbox.pack_end(spinner, False, False, 0)
		sbox.pack_end(failed, False, False, 0)

		if s.description:
			sbox.set_tooltip_text(s.description)

		sbox.show_all()
		spinner.start()  # the first read will stop it
		failed.set_visible(False)
		box.pack_start(sbox, False, False, 0)
		yield sbox


def _update_setting_item(sbox, value):
	_, failed, spinner, control = sbox.get_children()
	spinner.set_visible(False)
	spinner.stop()

	# print ("update", control, "with new value", value)
	if value is None:
		control.set_sensitive(False)
		failed.set_visible(True)
		return

	failed.set_visible(False)
	if isinstance(control, Gtk.Switch):
		control.set_active(value)
	elif isinstance(control, Gtk.ComboBoxText):
		control.set_active_id(str(value))
	# elif isinstance(control, Gtk.Scale):
	# 	control.set_value(int(value))
	else:
		raise NotImplemented
	control.set_sensitive(True)

#
#
#

def create():
	b = Gtk.VBox(homogeneous=False, spacing=4)
	b.set_property('margin', 8)
	return b


def update(frame):
	box = frame._config_box
	assert box
	device = frame._device

	if device is None:
		# remove all settings widgets
		# if another device gets paired here, it will add its own widgets
		_remove_children(box)
		return

	if not box.get_visible():
		# no point in doing this right now, is there?
		return

	if not device.settings:
		# nothing to do here
		return

	force_read = False
	items = box.get_children()
	if len(device.settings) != len(items):
		_remove_children(box)
		if device.status:
			items = list(_add_settings(box, device))
			assert len(device.settings) == len(items)
			force_read = True

	device_active = bool(device.status)
	# if the device just became active, re-read the settings
	force_read |= device_active and not box.get_sensitive()
	box.set_sensitive(device_active)
	if device_active:
		for sbox, s in zip(items, device.settings):
			_apply_queue.put(('read', s, force_read, sbox))


def _remove_children(container):
	container.foreach(lambda x, _: container.remove(x), None)

