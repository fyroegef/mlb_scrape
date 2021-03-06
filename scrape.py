from datetime import datetime
import urllib2
import xml.etree.ElementTree as et
import numpy as np

class gameScraper(object):
	def __init__(self,custom_date=False,fetch=True):
		## To lookup a historical date, use custom date = (YYYY,MM,DD)
		## If to save time you want to manually lookup individual games, use fetch=False
		if custom_date:
			self.year,self.month,self.day = custom_date
		else:
			dt_temp = datetime.now()
			self.year,self.month,self.day = dt_temp.strftime('%Y'),dt_temp.strftime('%m'),dt_temp.strftime('%d')
		self.schedule = self._getSchedule()
		self.game_datas = {}
		if fetch:
			for game_id in self.schedule:
				self.game_datas[game_id] = self._getXML(game_id)

	def _getSchedule(self):
		## Semi-private method to lookup games on a particular day
		self.path = 'http://gd2.mlb.com/components/game/mlb/year_' + self.year + '/month_' + self.month + '/day_' + self.day + '/'
		req = urllib2.Request(self.path)
		schedule_page = urllib2.urlopen(req).read()
		game_ids = []
		for item in schedule_page.split('href="gid_')[1:]:
			game_ids.append(item.split('/">')[0])
		return game_ids

	def _getXML(self,game_id):
		## Semi-private method to lookup a game's xml and convert it into a list/dictionary structure that is default to ElementTree
		game_path = self.path + 'gid_' + game_id + '/inning/inning_all.xml'
		print game_path
		try:
			req = urllib2.Request(game_path)
			pbp_xml = urllib2.urlopen(req).read().split('-->')[1]
			game_data = et.fromstring(pbp_xml)
			return game_data
		except:
			return None

def pitchFX(game_data,game_id):
	## Converts the ElementTree default structure into a list of all pitchF/X info for the whole game
	## all units are converted to MKS
	if not game_data:
		return None
	home_id = game_id.split('_')[-2][:3]
	away_id = game_id.split('_')[-3][:3]
	timestamp = ''.join(game_id.split('_')[:3])

	fx_data = []
	for i,inning in enumerate(game_data):
		for half_inning in inning:
			for item in half_inning:
				if item.tag == 'atbat':
					for subitem in item:
						if subitem.tag == 'pitch':
							try:
								pitch_temp = {}
								pitch_temp['batter_id'] = item.attrib['batter']
								pitch_temp['pitcher_id'] = item.attrib['pitcher']
								pitch_temp['timestamp'] = timestamp
								pitch_temp['home_id'] = home_id
								pitch_temp['away_id'] = away_id
								pitch_temp['inning_num'] = i+1
								if subitem.attrib['type'] == 'X':
									pitch_temp['result'] = item.attrib['event']
								else:
									pitch_temp['result'] = None
								pitch_temp['call'] = subitem.attrib['type']

								pitch_temp['spd'] = float(subitem.attrib['start_speed']) * 0.447
								pitch_temp['sz'] = (float(subitem.attrib['sz_bot'])*0.3048,float(subitem.attrib['sz_top'])*0.3048)
								pitch_temp['pos_i'] = (float(subitem.attrib['x0'])*0.3048,float(subitem.attrib['y0'])*0.3048,float(subitem.attrib['z0'])*0.3048)
								pitch_temp['pos_f'] = (float(subitem.attrib['px'])*0.3048,0,float(subitem.attrib['pz'])*0.3048)
								pitch_temp['ddt'] = (float(subitem.attrib['pfx_x'])*0.0254,0,float(subitem.attrib['pfx_z'])*0.0254)
								pitch_temp['y_mxbr'] = float(subitem.attrib['break_y'])*0.3048
								pitch_temp['br_ang'] = float(subitem.attrib['break_angle'])*np.pi/180
								pitch_temp['br_len'] = float(subitem.attrib['break_length'])*0.0254

								fx_data.append(pitch_temp)
							except:
								continue
	return fx_data


def baseData(game_data,game_id):
	## Converts the ElementTree default structure into 'base data'.
	## each element has an initial and final state in terms of: base occupancy, outs, runs for each team
	## this state-space is intended for simple Markov models, like RE24 or related
	base_dict = {'':0,'1B':1,'2B':2,'3B':4}
	home_id = game_id.split('_')[-2][:3]
	away_id = game_id.split('_')[-3][:3]
	timestamp = ''.join(game_id.split('_')[:3])

	base_data = {}
	base_data['home_id'] = home_id
	base_data['away_id'] = away_id
	base_data['timestamp'] = timestamp
	base_data['plays'] = []

	home_score = 0
	away_score = 0
	for inning in game_data:
		inning_temp = []
		for half_inning in inning:
			outs = 0
			base_state = 0					## weighted sum of bases: 1st = 1, 2nd = 2, 3rd = 4
			runners = ['','','']
			half_inning_temp = []
			for item in half_inning:
				if item.tag == 'atbat':
					atbat = {}
					atbat['batter_id'] = item.attrib['batter']
					atbat['pitcher_id'] = item.attrib['pitcher']
					atbat['outs_i'] = outs
					atbat['base_i'] = base_state
					atbat['outs_f'] = int(item.attrib['o'])
					atbat['runners_i'] = runners
					atbat['home_score_i'],atbat['away_score_i'] = home_score,away_score
					outs = int(item.attrib['o'])
					for subitem in item:
						if subitem.tag == 'runner':
							base_state -= base_dict[subitem.attrib['start']]
							base_state += base_dict[subitem.attrib['end']]
							if not subitem.attrib['end'] == '':
								runners[int(np.log2(base_dict[subitem.attrib['end']]))] = subitem.attrib['id']
							if 'score' in subitem.attrib and subitem.attrib['score'] == 'T':
								if half_inning.tag == 'top':
									away_score += 1
								else:
									home_score += 1
					atbat['base_f'] = base_state
					atbat['home_score_f'],atbat['away_score_f'] = home_score,away_score
					atbat['runners_f'] = runners
					atbat['text_short'] = item.attrib['event']
					half_inning_temp.append(atbat)
			inning_temp.append(half_inning_temp)
		base_data['plays'].append(inning_temp)
	return base_data


