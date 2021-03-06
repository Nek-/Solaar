#
#
#

from __future__ import absolute_import, division, print_function, unicode_literals

#
#
#

import fcntl as _fcntl
import os.path as _path
import os as _os


def check():
	# ensure no more than a single instance runs at a time
	lock_fd = None
	for p in _os.environ.get('XDG_RUNTIME_DIR'), '/run/lock', '/var/lock', _os.environ.get('TMPDIR', '/tmp'):
		if p and _path.isdir(p) and _os.access(p, _os.W_OK):
			lock_path = _path.join(p, 'solaar.single-instance.%d' % _os.getuid())
			try:
				lock_fd = open(lock_path, 'wb')
				# print ("Single instance lock file is %s" % lock_path)
				break
			except:
				pass

	if lock_fd:
		try:
			_fcntl.flock(lock_fd, _fcntl.LOCK_EX | _fcntl.LOCK_NB)
			return lock_fd
		except IOError as e:
			if e.errno == 11:
				import sys
				sys.exit("solaar: error: Solaar is already running.")
			else:
				raise
	else:
		import sys
		print ("solaar: warning: failed to create single instance lock file, ignoring.", file=sys.stderr)


def close(lock_fd):
	if lock_fd:
		_fcntl.flock(lock_fd, _fcntl.LOCK_UN)
		lock_fd.close()
