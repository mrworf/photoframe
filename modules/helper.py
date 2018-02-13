import subprocess
import socket
import logging

class helper:
	@staticmethod
	def getResolution():
		res = None
		output = subprocess.check_output(['/bin/fbset'], stderr=DEVNULL)
		for line in output.split('\n'):
			line = line.strip()
			if line.startswith('mode "'):
				res = line[6:-1]
				break
		return res

	@staticmethod
	def getIP():
		ip = None
		try:
			s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
			s.connect(("photoframe.sensenet.nu", 80))
			ip = s.getsockname()[0]
			s.close()
		except:
			pass
		return ip

	@staticmethod
	def getExtension(mime):
		mapping = {
			'image/jpeg' : 'jpg',
			'image/png' : 'png',
		}
		mime = mime.lower()
		if mime in mapping:
			return mapping[mime]
		logging.warning('Mime %s unsupported' % mime)
		return 'xxx'

