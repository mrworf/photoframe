

class remember:
	def __init__(self, filename, count):
		self.filename = os.path.splitext(filename)[0] + '_memory.json'
		self.count = count
		if os.path.exists(self.filename):
			with open(self.filename, 'rb') as f:
				self.memory = json.load(f)
		else:
			self.memory = {'seen':[]}

	def forget(self):
		self.memory = {'seen':[]}
		if os.path.exists(self.filename):
			os.unlink(self.filename)		

	def saw(self, index):
		if index not in self.memory['seen']:
			self.memory['seen'].append(index)
			with open(self.filename, 'wb') as f:
				json.dump(self.memory, f)

	def seenAll(self):
		return len(self.memory['seen']) == self.count

	def seen(self, index):
		return index in self.memory['seen']
