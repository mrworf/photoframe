from threading import Thread
import select
import time
import subprocess

class shutdown(Thread):
	def __init__(self):
		Thread.__init__(self)
		self.daemon = True
		self.gpio = 26
		self.start()


	def run(self):
		# Shutdown can be initated from GPIO26
		poller = select.poll()
		try:
			with open('/sys/class/gpio/export', 'wb') as f:
				f.write('%d' % self.gpio)
		except:
			# Usually it means we ran this before
			pass
		with open('/sys/class/gpio/gpio%d/direction' % self.gpio, 'wb') as f:
			f.write('in')
		with open('/sys/class/gpio/gpio%d/edge' % self.gpio, 'wb') as f:
			f.write('both')
		with open('/sys/class/gpio/gpio%d/value' % self.gpio, 'rb') as f:
			data = f.read()
			poller.register(f, select.POLLPRI)
			i = poller.poll(None)
			subprocess.call(['/sbin/poweroff'], stderr=DEVNULL);
			logging.debug('Shutdown GPIO triggered')
