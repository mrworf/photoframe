#!/usr/bin/env python3

import sys
import requests
import json

#Gets first keyword entered when running the script
keywordsin = str(sys.argv[1])

#Add a keyword from user entry
def postKeyword():
    postUrl = 'http://localhost:7777/keywords/add'
    payload = {'keywords': keywordsin}
    r = requests.post(postUrl, json=payload)

#Get current keywords
def getKeywords():
    getUrl = 'http://localhost:7777/keywords'
    r = requests.get(getUrl)
    result = r.json()
    return(result)

#Add user keyword
#Iterate through existing keywords deleting first item in array until just user entry is left
def updateKeywords():
    deleteUrl = 'http://localhost:7777/keywords/delete'
    postKeyword()
    keywords = getKeywords()
    list = []
    for element in keywords['keywords']:
        list.append(element)
    print("Current keywords: " + str(list))
    newlist = [keywordsin]
    countTotal = len(list)
    countNew = len(newlist)
    print("You entered: " + keywordsin)
    n = 0
    n = countTotal - countNew
    deleteID = {'id': 0}
    #keywords are added incrementing to existing array - remove keyword 0 again and again
    #until we arrive at the updated list
    while (n > 0):
        r = requests.post(deleteUrl, json=deleteID)
        n = (n - 1)

    result = getKeywords()
    print(result)
#Allow user to choose whether to add new keyword or replace existing
def option():
    selection = input("Add keyword or replace the current keyword(s) with a new one? ")
    if (selection.lower() == 'add'):
        postKeyword()
    elif (selection.lower() == 'replace'):
        updateKeywords()
    else:
        input("Invalid option - type Add or Replace - hit any key to try again")
        option()

option()
