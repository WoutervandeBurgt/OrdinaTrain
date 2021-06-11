import streamlit as st
import numpy as np
import pandas as pd
import json
import http.client, urllib.request, urllib.parse, urllib.error, base64
import math
import datetime as dt
import pickle
import iso8601
from datetime import timedelta, datetime
import re

#load in machine learned trained model: Random Forest classifier.
#model = pickle.load(open("Alexandra_model.sav", 'rb'))
model = pickle.load(open("knnc.sav", 'rb'))
#Load in stationNumbers, this is used to select the stations.
stationNumbers = pd.read_csv("stationNumbers2.csv", usecols = ["index", "FullName", "StationCode", "id"])
#the loaded in model to train uses traintypes, like sprinter, labelencoded. This returns the types of the trains
#so that they can be used to make predictions on the model.
trainTypeNumbers = pd.read_csv("trainTypesNumbers.csv", usecols = ["0"])
snow = 3
predText = []
st.write("""
# Prototype Ordina choosing best travel option.
""")

#requests from the NS api.
def getRoute(startstation, endstation, datetime):
    if startstation == endstation:
        return "", "", "", "", "", ""
    #return startstation + endstation
    headers = {
        # Request headers
        'Authorization': '',
        'Ocp-Apim-Subscription-Key': 'a39857d1e9524a20bb6b0b666392089a',
    }

    params = urllib.parse.urlencode({
        'fromStation': startstation,
        'toStation': endstation,
        'dateTime': datetime

    })

    try:
        conn = http.client.HTTPSConnection('gateway.apiportal.ns.nl')
        conn.request("GET", "/reisinformatie-api/api/v3/trips?%s" % params, "{body}", headers)
        response = conn.getresponse()
        data = response.read()
        #print(data)
        conn.close()
    except Exception as e:
        print("[Errno {0}] {1}".format(e.errno, e.strerror))

    stations = []
    tracks = []
    times = []
    operators = []
    types = []
    crowds = []
    trip = json.loads(data)
    #st.write(trip)
    if 'trips' not in trip:
        return "", "", "", "", "", ""
    for i in range (len(trip['trips'][0]['legs'])):
            stations.append(trip['trips'][0]['legs'][i]['origin']['name'])
            if 'plannedTrack' in trip['trips'][0]['legs'][i]['origin']:
                tracks.append(trip['trips'][0]['legs'][i]['origin']['plannedTrack'])
            times.append(str(iso8601.parse_date(trip['trips'][0]['legs'][i]['origin']['plannedDateTime'])-timedelta(hours = 2)))
            stations.append(trip['trips'][0]['legs'][i]['destination']['name'])
            if 'plannedTrack' in trip['trips'][0]['legs'][i]['destination']:
                tracks.append(trip['trips'][0]['legs'][i]['destination']['plannedTrack'])
            times.append(str(iso8601.parse_date(trip['trips'][0]['legs'][i]['destination']['plannedDateTime'])-timedelta(hours = 2)))
            operators.append(trip['trips'][0]['legs'][i]['product']['operatorName'])
            types.append(trip['trips'][0]['legs'][i]['product']['longCategoryName'])
            if 'crowdForecast' in trip["trips"][0]["legs"][i]:
                crowds.append(trip["trips"][0]["legs"][i]['crowdForecast'])
    seperator = ', '
    return stations, tracks, times, operators, types, crowds


base = "http://api.openweathermap.org/data/2.5/forecast?id="
key = "25afd7cf3a4af3968518540a29d265f7"
keyadd = "&appid=25afd7cf3a4af3968518540a29d265f7&units=metric"

#openweathermap weather api.
def getweather(city, time):
    #city = 2755003 #haarlem
    #city = "2756253" #Eindhoven
    checkTime = datetime.strptime(time, "%Y-%m-%d %H:%M:%S")
    if checkTime > dt.datetime.now() + dt.timedelta(days = 5):
        return 0,0,0,0,0,0,0,0,3
    request = urllib.request.Request(
            base+city+keyadd,
            None,
        )
    response = urllib.request.urlopen(request).read().decode("utf-8")
    response = json.loads(response)
    for i in range (0, len(response["list"])):
        if response["list"][i]['dt_txt'] == time:
            direct = response['list'][i]['wind']['deg']
            windspeed = response['list'][i]['wind']['speed']
            gust = response['list'][i]['wind']['gust']
            temp = response['list'][i]['main']['temp']
            humidity = response['list'][i]['main']['humidity']
            pressure = response['list'][i]['main']['pressure']
            hourrain = 0
            if 'rain' in response['list'][i]:
                hourrain = response['list'][i]['rain']['3h']/3
                rain = 1
                snow = 0
            else:
                hourrain = 0
                rain = 0
            if 'snow' in response['list'][i]:
                snow = 1
                rain = 1
            else:
                snow = 0
            return direct, windspeed, gust, temp, humidity, pressure, hourrain, rain, snow
            break;
    return 0,0,0,0,0,0,0,0,3

def inputs(newArrshort = "0", newDepshort = "0", departure = '0', destination = '0', date5 = '0', hour = '0', minute = '0'):

    if newArrshort != "0":
        return newArrshort, newDepshort, departure, destination, date5, hour, minute

    departure = st.selectbox('Enter your departure station', (stationNumbers["FullName"]))
    destination = st.selectbox('Enter your destination station', (stationNumbers["FullName"]))
    destinationshort = stationNumbers[stationNumbers["FullName"]==destination]["StationCode"].values[0]
    departureshort = stationNumbers[stationNumbers["FullName"]==departure]["StationCode"].values[0]
    currentDateTime = dt.datetime.now()
    date = currentDateTime.date()
    date5 = st.date_input('start date', dt.date(int(date.strftime("%Y")),int(date.strftime("%#m")),int(date.strftime("%#d"))))
    hour = st.number_input('Hour', 0, 23, int(currentDateTime.strftime("%#H")))
    minute = st.number_input('Minute', 0, 59, int(currentDateTime.strftime("%#M")))
    return departureshort, destinationshort, departure, destination, date5, hour, minute

def user_input_features(newArrshort = "0", newDepshort = "0", departure = '0', destination = '0', date5 = '0', hour = '0', minute = '0'):
    currentDateTime = dt.datetime.now()
    date = currentDateTime.date()
    #departure = st.selectbox('Enter your departure station', (stationNumbers["FullName"]))
    #departureshort = stationNumbers[stationNumbers["FullName"]==departure]["StationCode"].values[0]
    #destination = st.selectbox('Enter your destination station', (stationNumbers["FullName"]))
    #destinationshort = stationNumbers[stationNumbers["FullName"]==destination]["StationCode"].values[0]
    if newArrshort == "0":
        departureshort, destinationshort, departure, destination, date5, hour, minute = inputs()
    else:
        departureshort, destinationshort, departure, destination, date5, hour, minute = inputs(newArrshort, newDepshort, departure, destination, date5, int(hour), int(minute))

    #year = st.text_input('Year', 2021)
    #year = date.strftime("%Y")
    year = date5.year
    month = date5.month
    day = date5.day
    #city = data2[data2["LongName"]==departure]["id"].values[0].astype(str)
    city = stationNumbers[stationNumbers["FullName"]==departure]["id"].values[0].astype(str)
    #city = departureshort

    year = str(year)
    if hour == 23:
        roundedhour = 21
    else:
        roundedhour = round(hour/3)*3
    if month < 10:
        month = "0" + str(month)
    else:
        month = str(month)
    if day < 10:
        day = "0" + str(day)
    else:
        day = str(day)
    if hour < 10:
        hour = "0" + str(hour)
    else:
        hour = str(hour)
    if minute < 10:
        minute = "0" + str(minute)
    else:
        minute = str(minute)
    if roundedhour < 10:
        roundedhour = "0" + str(roundedhour)
    else: roundedhour = str(roundedhour)
    datetimens = year + "-" + month + "-" + day + "T"+ hour + ":" + minute + ":00.00Z"
    weatherdate = year+"-"+month+"-"+day+" "+roundedhour+":00:00"
    direct, windspeed, gust, temp, humidity, pressure, hourrain, rain, snow = getweather(city[:7], weatherdate)
    stations, tracks, times, operators, types, crowds = getRoute(departureshort, destinationshort, datetimens)
    #stationInt = stationNumbers.index.get_loc(stationNumbers.index[stationNumbers["0"] == "Utrecht Centraal"][0])
    #stationInt = stationNumbers.loc[176][1]

    hour = int(hour)
    fitarray = []
    predtest = []
    Detours = int(len(times)/2)
    if snow == 3 or departureshort == destinationshort or len(times) == 0 or types == "":
        noWeatherMessage = "No Weatherdata, no prediction"
        prediction = []
        for i in range(0, Detours):
            prediction.append(noWeatherMessage)
    else:
        for i in range(0, Detours):
            if operators[i] == "NS":
                operint = 1
            elif operators[i] == "Arriva":
                operint = 0
            else:
                operint = 2 #problem
            stationInt = stationNumbers.index.get_loc(stationNumbers.index[stationNumbers["FullName"] == stations[i]][0])
            #stationInt = stationNumbers[stationNumbers["FullName"] == stations[i]]["index"]
            typeInt = trainTypeNumbers.index.get_loc(trainTypeNumbers.index[trainTypeNumbers["0"] == types[i]][0])
            city = stationNumbers[stationNumbers["index"]==stationInt]["id"].values[0].astype(str)

            direct, windspeed, gust, temp, humidity, pressure, hourrain, rain, snow = getweather(city[:7], weatherdate)
            #"StationCode", "Vervoerder", "ReisInformatieTijdstip", "LangeNaam", "Hourly sum of the rain"
            #"RitDatum", "StationCode", "Vervoerder", "Station", "ReisInformatieTijdstip", "LangeNaam", "Hourly sum of the rain"
            #tofit = [stationInt, operint, typeInt, re.search(r'\d+', tracks[int(i/2)]).group(), hour, hour, direct, windspeed, gust, temp, hourrain, pressure, humidity, rain, snow, 1]
            testdate = year+month+day+str(hour)+minute+"000000"
            tofit = [stationInt, operint, testdate, stationInt, hourrain]

            fitarray.append(tofit)
            #fitarray = [[10, operint, 3, tracks[0], hour, hour, direct, windspeed, gust, temp, hourrain, pressure, humidity, rain, snow, 1]]
        prediction = model.predict(fitarray)

        #2: No Delay
        #3: Small Delay
        #1: Medium Delay
        #0: Big Delay
        for j in range(0, len(prediction)):
            if prediction[j] == 2:
                predappend = dt.timedelta(minutes = 0)
                predText.append("No Delay")
            elif prediction[j] == 3:
                predappend = dt.timedelta(minutes = 5)
                predText.append("Small Delay")
            elif prediction[j] == 1:
                predappend = dt.timedelta(minutes = 15)
                predText.append("Medium Delay")
            else:
                predappend = dt.timedelta(minutes = 0)
                predText.append("error")
            if j != len(prediction)-1:
                if datetime.strptime(times[j*2+1][:19], '%Y-%m-%d %H:%M:%S')+predappend > datetime.strptime(times[j*2+2][:19], '%Y-%m-%d %H:%M:%S'):
                    newDepshort = stationNumbers[stationNumbers["FullName"]==stations[j*2+1]]["StationCode"].values[0]
                    newArrshort = stationNumbers[stationNumbers["FullName"]==stations[-1]]["StationCode"].values[0]
                    user_input_features(newArrshort, newDepshort, departure, destination, date5, hour, minute)

    if departure == destination or types =="":
        totalTime = 0
    else:
        totalTime = iso8601.parse_date(times[len(times)-1])-iso8601.parse_date(times[0])
    if Detours > 0:
        Detours = Detours -1
    else:
        Detours = 0
    data = {'From': departure,
            'To': destination,
            '# Detours': Detours,
            'Total Time': str(totalTime)
            }
    route_features = pd.DataFrame(list(zip(stations, times, tracks)), columns =["Station", "Time", "Track"])
    pred_df = pd.DataFrame(predText, columns = ["Prediction"])
    route_info = pd.DataFrame(list(zip(operators, types, crowds)), columns = ["Operator", "Train Type", "crowds"])
    features = pd.DataFrame(data, index=[0])
    return features, route_features, route_info, pred_df



df, df_route, route_info, pred_df = user_input_features()
st.write(df)
dfFrame = pd.merge(df_route.drop_duplicates('Station'), df_route, on = "Station", how = "outer").drop_duplicates('Station', keep = "last")

dfFrame.columns = ["Station", "Arrivaltime", "ArrivalPlatform", "Departuretime", "DeparturePlatform"]

dfFrame = dfFrame.reset_index()

dfFrame.loc[0, "Arrivaltime"] = np.NaN
dfFrame.loc[len(dfFrame)-1, "Departuretime"] = np.NaN
dfFrame.loc[0, "ArrivalPlatform"] = np.NaN
dfFrame.loc[len(dfFrame)-1, "DeparturePlatform"] = np.NaN

dfFrame = dfFrame.drop(["index"], axis = 1)

dfFrame = dfFrame.dropna(how = "all")

dfFrame["Arrivaltime"] = dfFrame["Arrivaltime"].str.slice(0, -9)
dfFrame["Departuretime"] = dfFrame["Departuretime"].str.slice(0, -9)

dfFrame["Arrivaltime"] = dfFrame["Arrivaltime"].str.slice(5)
dfFrame["Departuretime"] = dfFrame["Departuretime"].str.slice(5)

dfFrame["Arrivaltime"] = dfFrame["Arrivaltime"].str.replace(r' ', " | ")
dfFrame["Departuretime"] = dfFrame["Departuretime"].str.replace(r' ', " | ")
dfFrame = pd.concat([dfFrame, route_info, pred_df], axis = 1)
dfFrame["Arrival"] = dfFrame["Arrivaltime"] + " P" + dfFrame["ArrivalPlatform"]
dfFrame["Departure"] = dfFrame["Departuretime"] + " P" + dfFrame["DeparturePlatform"]
dfFrame = dfFrame.drop(["Arrivaltime", "Departuretime", "ArrivalPlatform", "DeparturePlatform", "Operator", "Train Type"], axis = 1)
st.write(dfFrame)
