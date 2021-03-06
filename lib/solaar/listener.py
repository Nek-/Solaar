#
#
#

from __future__ import absolute_import, division, print_function, unicode_literals

from logging import getLogger, DEBUG as _DEBUG
_log = getLogger('solaar.listener')
del getLogger

from logitech.unifying_receiver import (Receiver,
										listener as _listener,
										status as _status)

#
#
#

from collections import namedtuple
_GHOST_DEVICE = namedtuple('_GHOST_DEVICE', ['number', 'name', 'kind', 'status', 'max_devices'])
_GHOST_DEVICE.__bool__ = lambda self: False
_GHOST_DEVICE.__nonzero__ = _GHOST_DEVICE.__bool__
del namedtuple

def _ghost(device):
	return _GHOST_DEVICE(number=device.number, name=device.name, kind=device.kind, status=None, max_devices=None)

DUMMY_RECEIVER = _GHOST_DEVICE(0xFF, 'Solaar', None, 'Receiver not found.', 0)

#
#
#

# how often to poll devices that haven't updated their statuses on their own
# (through notifications)
_POLL_TICK = 60  # seconds


class ReceiverListener(_listener.EventsListener):
	"""Keeps the status of a Receiver.
	"""
	def __init__(self, receiver, status_changed_callback):
		super(ReceiverListener, self).__init__(receiver, self._notifications_handler)
		self.tick_period = _POLL_TICK
		self._last_tick = 0

		assert status_changed_callback
		self.status_changed_callback = status_changed_callback
		receiver.status = _status.ReceiverStatus(receiver, self._status_changed)

	def has_started(self):
		_log.info("%s: notifications listener has started (%s)", self.receiver, self.receiver.handle)
		self.receiver.enable_notifications()
		self.receiver.notify_devices()
		# self._status_changed(self.receiver, _status.ALERT.NOTIFICATION)

	def has_stopped(self):
		_log.info("%s: notifications listener has stopped", self.receiver)
		if self.receiver:
			self.receiver.enable_notifications(False)
			self.receiver.close()
		self.receiver = None
		self.status_changed_callback(DUMMY_RECEIVER, _status.ALERT.NOTIFICATION)

	def tick(self, timestamp):
		if _log.isEnabledFor(_DEBUG):
			_log.debug("%s: polling status: %s", self.receiver, list(iter(self.receiver)))

		if self._last_tick > 0 and timestamp - self._last_tick > _POLL_TICK * 3:
			# if we missed a couple of polls, most likely the computer went into
			# sleep, and we have to reinitialize the receiver again
			_log.warn("%s: possible sleep detected, closing this listener", self.receiver)
			self.stop()
			return

		self._last_tick = timestamp

		# read these in case they haven't been read already
		# self.receiver.serial, self.receiver.firmware
		if self.receiver.status.lock_open:
			# don't mess with stuff while pairing
			return

		for dev in self.receiver:
			if dev.status is not None:
				dev.status.poll(timestamp)

	def _status_changed(self, device, alert=_status.ALERT.NONE, reason=None):
		assert device is not None
		if _log.isEnabledFor(_DEBUG):
			_log.debug("%s: status_changed %s: %s, %s (%X) %s", self.receiver, device,
						'active' if device.status else 'inactive',
						device.status, alert, reason or '')

		if device.kind is None:
			# print ("self.receiver: ", self.receiver, id(self.receiver))
			# print ("device: ", device, id(device))
			assert device == self.receiver
			# the status of the receiver changed
			self.status_changed_callback(device, alert, reason)
		else:
			if device.status is None:
				# the device may be paired later, possibly to another receiver?
				# so maybe we shouldn't forget about it
				# configuration.forget(device)

				# device was unpaired, and since the object is weakref'ed
				# it won't be valid for much longer
				device = _ghost(device)

			# elif device.status:
			# 	configuration.sync(device)

			self.status_changed_callback(device, alert, reason)

			if device.status is None:
				# the receiver changed status as well
				self.status_changed_callback(self.receiver)

	def _notifications_handler(self, n):
		assert self.receiver
		# _log.debug("%s: handling %s", self.receiver, n)
		if n.devnumber == 0xFF:
			# a receiver notification
			if self.receiver.status is not None:
				self.receiver.status.process_notification(n)
		else:
			# a device notification
			assert n.devnumber > 0 and n.devnumber <= self.receiver.max_devices
			already_known = n.devnumber in self.receiver
			dev = self.receiver[n.devnumber]

			if not dev:
				_log.warn("%s: received %s for invalid device %d: %r", self.receiver, n, n.devnumber, dev)
				return

			if not already_known:
				# read these as soon as possible, they will be used everywhere
				dev.protocol, dev.codename
				dev.status = _status.DeviceStatus(dev, self._status_changed)
				# the receiver changed status as well
				self._status_changed(self.receiver)

			# status may be None if the device has just been unpaired
			if dev.status is not None:
				dev.status.process_notification(n)
				if self.receiver.status.lock_open and not already_known:
					# this should be the first notification after a device was paired
					assert n.sub_id == 0x41 and n.address == 0x04
					_log.info("%s: pairing detected new device", self.receiver)
					self.receiver.status.new_device = dev

	def __str__(self):
		return '<ReceiverListener(%s,%s)>' % (self.receiver.path, self.receiver.handle)
	__unicode__ = __str__

	@classmethod
	def open(self, status_changed_callback):
		assert status_changed_callback
		receiver = Receiver.open()
		if receiver:
			rl = ReceiverListener(receiver, status_changed_callback)
			rl.start()
			return rl
