import mysql.connector
import serial
import time
import datetime
import signal
import sys
from AWSIoTPythonSDK.MQTTLib import AWSIoTMQTTClient
import json

from threading import Timer

arduino = serial.Serial('/dev/ttyUSB0', 9600)

db_config = {
    'user': 'root',
    'password': '1213',
    'host': 'localhost',
    'database': 'sensor_db'
}

# currentTemp = 'Low'
currentAlarm = 'Not triggered'
currentLockStatus = 'Locked'  # Initial lock status
lastTemperature = 0.0
lastHumidity = 0.0
entries = ""

# AWS IoT certificate based connection
myMQTTClient = AWSIoTMQTTClient("PiNode")
myMQTTClient.configureEndpoint("a3qhwyg4jcabb4-ats.iot.ap-southeast-1.amazonaws.com", 8883)
myMQTTClient.configureCredentials(
    "/home/rogeryii1213/security/AmazonRootCA1.pem",
    "/home/rogeryii1213/security/13adf3b856ce0a4489e7d53adaf88b8bd9ce78bbd4e978b019b8fa169e854695-private.pem.key",
    "/home/rogeryii1213/security/13adf3b856ce0a4489e7d53adaf88b8bd9ce78bbd4e978b019b8fa169e854695-certificate.pem.crt"
)
myMQTTClient.configureOfflinePublishQueueing(-1)  # Infinite offline Publish queueing
myMQTTClient.configureDrainingFrequency(2)  # Draining: 2 Hz
myMQTTClient.configureConnectDisconnectTimeout(10)  # 10 sec
myMQTTClient.configureMQTTOperationTimeout(5)  # 5 sec

def handle_signal(signal, frame):
    print("Exiting...")
    myMQTTClient.disconnect()
    sys.exit(0)

signal.signal(signal.SIGINT, handle_signal)

def check_access(card):
    db = mysql.connector.connect(**db_config)
    cursor = db.cursor()
    query = "SELECT Name FROM Registered WHERE ID = %s"
    cursor.execute(query, (card,))
    result = cursor.fetchone()
    cursor.close()
    db.close()
    
    return result[0] if result else ""

def input_access(cardID, Name, Status):
    db = mysql.connector.connect(host="localhost", user="root", password="1213", database="sensor_db") 
    date = datetime.datetime.now()
    date = date.strftime("%c")

    cursor = db.cursor()
    cursor.execute("INSERT INTO log (card, user, status, datetime) VALUES (%s, %s, %s, %s)", (cardID, Name, Status, date))
    db.commit()
        
        
    cursor.close()
    
    db.close()
    
def input_temp_humidity(temperature, humidity):
    db = mysql.connector.connect(**db_config)
    date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor = db.cursor()
    cursor.execute("INSERT INTO TemperatureLog (status, datetime) VALUES (%s, %s)", (f"Temp: {temperature}, Hum: {humidity}", date))
    db.commit()
    cursor.close()
    db.close()

def input_lock(status):
    db = mysql.connector.connect(**db_config)
    date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor = db.cursor()
    cursor.execute("INSERT INTO LockLog (status, datetime) VALUES (%s, %s)", (status, date))
    db.commit()
    cursor.close()
    db.close()
    
def input_Alarm(Status):
    db = mysql.connector.connect(host="localhost", user="root", password="1213", database="sensor_db")  
    date = datetime.datetime.now()
    date = date.strftime("%c")

    cursor = db.cursor()
    cursor.execute("INSERT INTO BuzzerLog (status, datetime) VALUES (%s, %s)", (Status, date))
    db.commit()
        
        
    cursor.close()
    
    db.close()
    
def fetch_data_by_card_id(card_id):
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        query = "SELECT ID, Name FROM Registered WHERE ID = %s"
        cursor.execute(query, (card_id,))
        data = cursor.fetchone()
        cursor.close()
        conn.close()

        if data:
            return data[0], data[1]
        else:
            return None, None

    except mysql.connector.Error as error:
        print("Error connecting to MySQL database:", error)
        return None, None
    
    
def publish_temperature_humidity_lock():
    global lastTemperature, lastHumidity, currentLockStatus
    payload = {
        "Room": "Room 4",
        "Temperature": lastTemperature,
        "Humidity": lastHumidity,
        "LockStatus": currentLockStatus,
        "DateTime": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    payload_json = json.dumps(payload)
    myMQTTClient.publish("rpi3/sensors", payload_json, 1)
    input_temp_humidity(lastTemperature, lastHumidity)
    Timer(10, publish_temperature_humidity_lock).start()
    
def control_callback(client, userdata, message):
    payload = message.payload.decode('utf-8')
    try:
        data = json.loads(payload)
        if data["command"] == "open_gate4":
            scs.write(b'O')  # ???? 'O' ? Arduino
            print("Gate open command sent to Arduino")
    except json.JSONDecodeError:
        print("Failed to decode JSON from control message payload")

myMQTTClient.connect()
myMQTTClient.subscribe("rpi3/control", 1, control_callback) 

scs = serial.Serial('/dev/ttyUSB0', 9600)
data_published = False  # Flag to track whether data has been published
publish_temperature_humidity_lock()  # Start the periodic publishing

while True:
    if not data_published:
        while scs.in_waiting == 0:
            pass

        line = scs.readline().decode('ascii').rstrip()
        splittedValues = line.split(',')
        
        print("splited value:" , splittedValues)

        # Check if the line is not equal to ['Scan a card']
        if (splittedValues != ['Triggered']) and (splittedValues != ['Scan a card']):
            cardID = splittedValues[0]

            if cardID:
                check_access_result = check_access(cardID)
                if check_access_result:
                    owner_id, owner_name = fetch_data_by_card_id(cardID)
                    if owner_id and owner_name:
                        entries = 'In'
                        input_access(owner_id, owner_name, entries)
                        payload = {
                            "Room": "Room 4",
                            "Card_ID": owner_id,
                            "OwnerName": owner_name,
                            "DateTime": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        }

                        payload_json = json.dumps(payload)
                        myMQTTClient.publish("rpi3/data", payload_json, 1)
                        print("Data published:", payload_json)
                        data_published = True  # Set the flag to True

        if splittedValues == ['Triggered']:
            if currentAlarm != splittedValues[0]:
                currentAlarm = splittedValues[0]
                input_Alarm(splittedValues[0])
                payload = {
                    "Room": "Room 4",
                    "PirStatus": currentAlarm,
                    "DateTime": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                payload_json = json.dumps(payload)
                myMQTTClient.publish("rpi3/alarm", payload_json, 1)
                print("Alarm published:", payload_json)

        if len(splittedValues) > 2:
            try:
                lastTemperature = float(splittedValues[0])
                lastHumidity = float(splittedValues[1])
            except ValueError:
                print("Invalid temperature/humidity values")

    else:
        # Reset the flag and wait for a new card scan
        data_published = False