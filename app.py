import math
import requests
import datetime

from flask import Flask, render_template, send_from_directory, request
from zeep import Client, xsd
# Import custom config
import config

config.commonstations={'train':config.train_stations,'tram':config.tram_stations,'bus':config.bus_stations}
app = Flask(__name__)

@app.route('/')
def showhelp_root():
    return render_template('travel.help.html')

@app.route('/js/<path:path>')
def send_js(path):
    return send_from_directory('static', path)

@app.route('/css/<path:path>')
def send_css(path):
    return send_from_directory('static', path)

@app.route('/<mode>/departures/')
def showhelp(mode):
    return render_template(mode+'.help.html', stops=config.commonstations[mode])

@app.route('/tube/status')
def showstatus():
    tubeJson = requests.get(
        "https://api.tfl.gov.uk/Line/Mode/tube/Status?detail=true&app_id=" + config.tfl_appid + "&app_key=" + config.tfl_appkey).json()
    overgroundJson = requests.get(
        "https://api.tfl.gov.uk/Line/Mode/overground/Status?detail=true&app_id=" + config.tfl_appid + "&app_key=" + config.tfl_appkey).json()
    tubestatus = []
    for line in tubeJson:
        ts = {}
        ts['name'] = line['name']
        ts['id'] = line['id']
        ts['status'] = line['lineStatuses'][0]['statusSeverityDescription']
        if 10 > line['lineStatuses'][0]['statusSeverity'] > 5:
            ts['statuscode'] = "degraded"
        elif line['lineStatuses'][0]['statusSeverity'] < 6:
            ts['statuscode'] = "bad"
        else:
            ts['statuscode'] = "good"
        ts['disrupted'] = line['disruptions']
        tubestatus.append(ts)
    os = {}
    os['name'] = "Overground"
    os['id'] = 'overground'
    os['status'] = overgroundJson[0]['lineStatuses'][0]['statusSeverityDescription']
    if 10 > overgroundJson[0]['lineStatuses'][0]['statusSeverity'] > 5:
        os['statuscode'] = "degraded"
    elif overgroundJson[0]['lineStatuses'][0]['statusSeverity'] < 6:
        os['statuscode'] = "bad"
    else:
        os['statuscode'] = "good"

    os['disrupted'] = overgroundJson[0]['disruptions']
    tubestatus.append(os)
    html = render_template('status.html',config=config, lines=tubestatus)
    return html

@app.route('/train/departures/<station>')
def showtraindepart(station):
    WSDL = 'http://lite.realtime.nationalrail.co.uk/OpenLDBWS/wsdl.aspx?ver=2017-10-01'
    client = Client(wsdl=WSDL)
    header = xsd.Element(
        '{http://thalesgroup.com/RTTI/2013-11-28/Token/types}AccessToken',
        xsd.ComplexType([
            xsd.Element(
                '{http://thalesgroup.com/RTTI/2013-11-28/Token/types}TokenValue',
                xsd.String()),
        ])
    )

    header_value = header(TokenValue=config.LDB_TOKEN)
    res = client.service.GetDepartureBoard(
        numRows=10, crs=station.upper(), _soapheaders=[header_value])

    services = res.trainServices.service
    deps = []
    for service in services:
        traindep = {}
        traindep['deptime'] = service.std
        traindep['dest'] = service.destination.location[0].locationName
        traindep['toc'] = service.operator
        traindep['platform'] = service.platform
        if service.etd == "On time":
            traindep['status'] = service.etd
        elif service.etd == "Cancelled":
            traindep['status'] = service.etd
            traindep['actualtime'] = ""
            traindep['platform'] = " "
        else:
            traindep['status'] = "Late"
            traindep['actdeptime'] = service.etd
        deps.append(traindep)
    html = render_template('train.depart.html',config=config,
                           loc=res.locationName, deps=deps)
    return html


@app.route('/tram/departures/<tramstop>')
def showtramdepart(tramstop):
    tramdeps = []
    for i in range(1, 3):
        tramurl = "https://robinhood.arcticapi.com/network/stops/" + \
            tramstop+str(i)+"/visits"
        tram_data = requests.get(tramurl).json()
        try:
            visits = tram_data["_embedded"]["timetable:visit"]
        except:
            visits = []  # If station is terminus only 1 of the station codes will be valid!
        for visit in visits:
            tramdep = {}
            if visit['isRealTime']:
                tramdep['dest'] = visit['destinationName']
                tramdep['exptime'] = visit['expectedArrivalTime']
                tramdep['aimtime'] = visit['aimedArrivalTime']
                waitstr = visit['displayTime']
                if waitstr == "Due":
                    tramdep['waitnum'] = 0
                else:
                    tramdep['waitnum'] = int(waitstr.split()[0])
                tramdep['waittime'] = waitstr
                if visit['expectedArrivalTime'] == visit['aimedArrivalTime']:
                    tramdep['status'] = "On time"
                else:
                    # Convert expected time from string to date obj
                    exp = datetime.datetime.strptime(
                        visit['expectedArrivalTime'], '%Y-%m-%dT%X+01:00')
                    # Convert aimed time from string to date obj
                    aim = datetime.datetime.strptime(
                        visit['aimedArrivalTime'], '%Y-%m-%dT%X+01:00')
                                    diff = (exp - aim).total_seconds()
                    if diff > 0: # If difference is positive then tram is late
                        minlate = math.ceil(diff / 60)
                        tramdep["status"] = "Late (" + str(minlate) + " min)"
                    else: # else tram is early
                        minearly = math.ceil(diff / -60)
                        tramdep["status"] = "Early (" + str(minearly) + " min)"
                tramdeps.append(tramdep)
    tramdeps = sorted(tramdeps, key=lambda k: k['waitnum'])
    html = render_template('tram.depart.html',config=config, deps=tramdeps, loc=tramstop)
    return html


@app.route('/bus/departures/<busstop>')
def showbusdepart(busstop):
    busdeps = []
    busurl = "https://robinhood.arcticapi.com/network/stops/" + \
        busstop+"/visits"
    print(busurl)
    bus_data = requests.get(busurl).json()
    visits = bus_data["_embedded"]["timetable:visit"]
    for visit in visits:
        busdep = {}
        if visit['isRealTime']:
            busdep['dest'] = visit['destinationName']
            busdep['exptime'] = visit['expectedArrivalTime']
            busdep['aimtime'] = visit['aimedArrivalTime']
            waitstr = visit['displayTime']
            if waitstr == "Due":
                busdep['waitnum'] = 0
            else:
                busdep['waitnum'] = int(waitstr.split()[0])
            busdep['waittime'] = waitstr
            if visit['expectedArrivalTime'] == visit['aimedArrivalTime']:
                busdep['status'] = "On time"
            else:
                # Convert expected time from string to date obj
                exp = datetime.datetime.strptime(
                    visit['expectedArrivalTime'], '%Y-%m-%dT%X+01:00')
                # Convert aimed time from string to date obj
                aim = datetime.datetime.strptime(
                    visit['aimedArrivalTime'], '%Y-%m-%dT%X+01:00')
                # Calculate difference between expected and aimed in min
                minlate = math.ceil((exp-aim).total_seconds()/60)
                busdep['status'] = "Late ("+str(minlate)+" min)"
            busdeps.append(busdep)
    busdeps = sorted(busdeps, key=lambda k: k['waitnum'])
    html = render_template('bus.depart.html',config=config, deps=busdeps, loc=busstop)
    return html


@app.route('/tube/departures/<station>')
def showtubedepartures():
    return "Tube departures not yet implemented"
