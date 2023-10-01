import binascii # Login
import json

import base64 # Both
import storer

import requests as rq # EcoleDirecte
from bs4 import BeautifulSoup as bs
from datetime import date, timedelta, datetime

# -- Note: If there are some comments you dont understand, try to translate them in french, then, again in english. That should work...
# -- 	   I hope my code is readable :)...

# Logging
import logger
from logger import *
logger.MAINPREFIX = "[EcoleDirecte]"

logger.INFO  = True
logger.DEBUG = True
logger.ERROR = True

# Constants
DEFAULTFRESHNESS = timedelta(hours = 4)

data = storer.Storer("ed")

# Tools
## Base64
def b64in(b64, **b64decodeArgs):
	return base64.b64decode(b64.encode("utf8"), **b64decodeArgs).decode("utf-8", "ignore")

def b64out(string, **b64decodeArgs):
	return base64.b64encode(string.encode("utf8"), **b64decodeArgs).decode("utf-8", "ignore")

## Json
def setupFile() -> None:
	"""Check and "repair" the data for compatibility"""
	data.pull()

	if "ids" not in data.data: data["ids"] = {} # Add dicts if not already present ...
	if "data" not in data.data: data["data"] = {}

	data.push() # Write out to file


# Classes
class Login():
	"""Class to save, load and encrypt id in homeworks_dictionnary json file"""
	def __init__(self, id_: str = "", mdp: str = "", linkId: str = "" ,*, storeIds: bool = True):
		self.id = id_
		self.mdp = mdp

		if linkId == "": linkId = id_
		self.linkId = linkId

		if storeIds: self.setIds()


	def getIds(self) -> list | int:
		"""Read, decrypt and return password, return 1 if password is incorrect (bad encryption), return 2 if given id hasnt been registered"""
		data.pull() # Extract json

		id_ = self.id
		linkId = self.linkId

		if id_ == "": # If empty, return
			warn("No id were given while getting password in getIds()")
			return 1

		if linkId == "":
			linkId = id_

		# encId for encryptedId
		encId = b64out(id_)

		if linkId in data["ids"]:
			if encId in data["ids"][linkId]:
				mdp = data["ids"][linkId][encId] # Extract password
			else:
				warn(f"\"{id_}\" is not registered in file \"{storer.file}\"")
				return 2
		else:
			warn(f"The link id \"{linkId}\" is not registered in file \"{storer.file}\"")
			return 3

		if mdp == "": # If empty, return
			error(f"The password associated to \"{id_}\" is empty")
			return 1

		try: # Decode identifiants
			mdp = b64in(mdp)

			self.id  = id_ # Re-set object vars
			self.mdp = mdp

			return [id_, mdp]
		except binascii.Error: # Except invalid base64, reset ids
			data["ids"][linkId][encId] = ""
			data.push()
			error(f"The password associated to \"{id_}\" contains encoding error(s)")
			return 1


	def setIds(self, id_: str = "", mdp: str = "", linkId: str = "") -> None:
		"""Encrypt and write ids in the file  -- Note: DONT change the id before calling this func (NO -> obj.id = "newId"), DO just pass the new id in the func (YES -> obj.setIds("newId"))"""
		if id_ == "": id_ = self.id # Set to object vars if empty
		if mdp == "": mdp = self.mdp
		if linkId == "": linkId = self.linkId
		if linkId == "": linkId = id_

		data.pull() # Extract json

		oldEncId = b64out(self.id) # Encode ids in base64
		encId    = b64out(id_)
		encMdp   = b64out(mdp)

		if self.linkId != linkId:
			if self.linkId in data["ids"]:
				if oldEncId in data["ids"][self.linkId]:
					tmp = data["ids"][self.linkId][oldEncId]
					del data["ids"][self.linkId][oldEncId]

					if data["ids"][self.linkId] == {}: del data["ids"][self.linkId]
					if linkId not in data["ids"]: data["ids"][linkId] = {}

					data["ids"][linkId][oldEncId] = tmp

		if oldEncId != encId: # Dont delete the id if its the same
			if linkId in data["ids"]: # If he has already homeworks_dictionnary password registered in, delete old id + password
				if oldEncId in data["ids"][linkId]:
					del data["ids"][linkId][oldEncId]

		if not (encId == "" or encMdp == ""):
			if linkId not in data["ids"]: data["ids"][linkId] = {}
			data["ids"][linkId][encId] = encMdp
			info(f"Saving new id and/or password for \"{id_}\"")
		else: # If he has no id or no password, we dont save anything
			if encId == "":
				warn("No id were given while trying to save ids in setIds()")
			else:
				warn("No password were given while trying to save ids in setIds()")

		self.id  = id_ # Re-set object vars
		self.mdp = mdp

		data.push() # Save change to the file


	def clearIds(self) -> None:
		"""Clear id stored in file"""
		self.mdp = ""
		tmp = self.id
		self.setIds("randomIdTooLongToBeRegisteredInEcoledirecte.com/Website:)")
		self.id = ""
		info(f"Cleared \"{tmp}\" from file \"{storer.file}\"")

###########################################
###########################################
###########################################

class EcoleDirecte():
	"""Class used to fetch marks, homeworks, planning and message. Need homeworks_dictionnary Login object or str infos"""
	def __init__(self, login: Login):
		self.name, self.token = 2*[""]
		self.id = 0
		self.result = {}
		self.ids = login

		r = self.reloadIds() # Load ids
		if r == 1:
			error("Error while trying to get ids")
			raise Exception # 


	def login(self) -> None | str:
		"""Log in EcoleDirecte with the previously given Login object"""
		r = self.reloadIds() # Reload if ids changed
		if type(r) == int:
			return r
		#        vvvvv Note that ecoledirecte uses homeworks_dictionnary strange data format (i call it stringedJSON), this is json surround in homeworks_dictionnary string by "data=". Idk why they did that...
		data = f'data={{"identifiant": "{self.username}","motdepasse": "{self.mdp}"}}'
		url = "https://api.ecoledirecte.com/v3/login.awp?v=4.18.3"
		self.post(url, auto=False, data=data) # Post request with custom data to login

		if self.result["code"] != 200: # Return (error message + code) if login not ok
			return f'{str(self.result["code"])} : {self.result["message"]}'

		info(f"Successfully logged in EcoleDirecte with id \"{self.username}\"")

		account = self.result["data"]["accounts"][0] # Get account infos...

		self.name = f'{account["prenom"]} {account["nom"]}' # Names...
		self.id = account["id"] # And user id (in order to build homeworks_dictionnary correct url for other infos)
		self.setToken() # Setting token for the same reason



	def fetchHomeworks(self, dataFreshness: timedelta =  DEFAULTFRESHNESS) -> dict:
		"""Fetch homeworks"""
		data = self.getJson("homeworks", dataFreshness)
		if type(data) == dict:
			return data

		url = f"https://api.ecoledirecte.com/v3/Eleves/{self.id}/cahierdetexte.awp?v=4.18.3&verbe=get&"
		self.post(url)

		result = {}
		dates = list(self.result["data"]) # Get all dates where are homeworks
		for date_ in dates: # Get date one at time
			url = f"https://api.ecoledirecte.com/v3/Eleves/{self.id}/cahierdetexte/{date_}.awp?v=4.18.3&verbe=get&"
			self.post(url)
			#print(json.dumps(self.result, indent=4))

			topic = self.result['data']['matieres'] # Get subjects of the date
			result[date_] = {}

			for homework in topic: # Get every homeworks for the current date
				if "aFaire" in homework: # Decoding & Formatting
					content = homework['aFaire']['contenu'] # Get base64 encoded content of the homework
					content = rq.utils.unquote(b64in(content)) # Decode from base64 & reformat text (e.g "%20" -> " ")
					content = bs(content, "lxml").text # Keep only text (deleting html tags)
					result[date_][homework["matiere"].lower()] = {"text": content, "controle": homework["interrogation"]} # Store the content in homeworks_dictionnary big dictionnary

		info("Fetched homeworks")
		
		self.storeJson(result, "homeworks")
		return result

	# Json management
	def storeJson(self, json: any, key: str) -> None | int:
		if type(json) == int:
			error("You cannot save int type in json due future errors")
			return 1

		data.pull()
		encId = b64out(self.username)

		if encId not in data["data"]: data["data"][encId] = {}
		data["data"][encId][key] = {}
		data["data"][encId][key]["lastUpdated"] = datetime.today().isoformat()
		data["data"][encId][key]["data"] = json

		data.push()

	def getJson(self, key: str, dataFreshness: timedelta = None) -> any:
		data.pull()
		encId = b64out(self.username)

		if encId not in data["data"]:
			error(f"\"{self.username}\" has no saved data")
			return 1

		if key not in data["data"][encId]:
			error(f"Requested data has not been saved early. Data key: {key}")
			return 1

		now = datetime.today()
		lastUpdate = datetime.fromisoformat(data["data"][encId][key]["lastUpdated"])
		json = data["data"][encId][key]["data"]
		
		if dataFreshness == None:
			return json

		if lastUpdate + dataFreshness < now:
			return 2

		return json


	# Tools
	def setToken(self) -> None:
		"""Set token from previous request"""
		self.token = self.result["token"]

	def getToken(self) -> str:
		"""Get token from previous request"""
		return self.token

	def getBuiltToken(self) -> str:
		"""Get token surrounded by special post data"""
		return f'data={{"token": "{self.getToken()}"}}'

	def post(self, url: str, *, auto: bool = True, headers: dict = {}, **rq_postArgs) -> dict:
		"""Post request if auto, auto send & set token"""
		if "user-agent" not in headers: headers["user-agent"] = "homeworks_dictionnary" # If no "user-agent", add it (because EcoleDirecte do not answer requests if there is no user-agent)
		if auto: data = rq_postArgs["data"] = self.getBuiltToken() # Get token if auto

		result = rq.post(url, **rq_postArgs, headers=headers).json() # Post request & get json

		if auto: self.setToken() # Re-set token if auto

		self.result = result
		return result

	def reloadIds(self) -> list | int:
		"""Get ids, store them in object and return them"""
		ids = self.ids.getIds() # Get ids
		if type(ids) == int: # If error, return
			return ids

		self.username = ids[0] # Store result
		self.mdp = ids[1]
		return ids # Return result

	def delKeys(dictionary: dict, *keys: str) -> dict:
		"""Deletes keys from dictionary, print keyerror(s)"""
		unMatched = []

		for key in keys:
			if key in dictionary:
				del dictionary[key]
			else:
				unMatched += [key]

		if len(unMatched) != 0:
			warn(f"Some keys weren't in the dict:", *unMatched)

		return dictionary

###########################################
###########################################
###########################################

# Startup
setupFile() # Setup json just in case


if __name__ == '__main__':
	print("This is homeworks_dictionnary lib, it is not supposed to run as main.")
	logger.MAINPREFIX = ""
	logger.INFO = True

# End, Hope you enjoyed my code ._. ^^
