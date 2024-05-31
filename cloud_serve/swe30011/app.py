import logging
import json
import time
import mysql.connector
import requests
from AWSIoTPythonSDK.MQTTLib import AWSIoTMQTTClient
from flask import Flask, render_template, request, jsonify
from datetime import datetime
from pytz import timezone

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(levelname)s: %(message)s', handlers=[
    logging.FileHandler("app.log"),
    logging.StreamHandler()
])
logger = logging.getLogger()

# MySQL configuration
db_config = {
    'user': 'admin',
    'password': '1234567890',
    'host': 'mariadb.c7k4g60muzri.ap-southeast-1.rds.amazonaws.com',
    'database': 'sensor_db'
}

mqtt_data_messages = []
mqtt_sensors_messages = []
mqtt_alarm_messages = []

# AWS IoT certificate based connection
aws_client = AWSIoTMQTTClient("CloudVM_kelvin")
aws_client.configureEndpoint("a3qhwyg4jcabb4-ats.iot.ap-southeast-1.amazonaws.com", 8883)
aws_client.configureCredentials("/home/ubuntu/swe30011/cert/AmazonRootCA1.pem", 
                                "/home/ubuntu/swe30011/cert/9dcdf5ea290a0400a41690f8ebe9e19ffbffb959dc0aa8a440da93f7ab0b3acd-private.pem.key", 
                                "/home/ubuntu/swe30011/cert/9dcdf5ea290a0400a41690f8ebe9e19ffbffb959dc0aa8a440da93f7ab0b3acd-certificate.pem.crt")
aws_client.configureOfflinePublishQueueing(-1)  # Infinite offline Publish queueing
aws_client.configureDrainingFrequency(2)  # Draining: 2 Hz
aws_client.configureConnectDisconnectTimeout(100)  # 10 sec
aws_client.configureMQTTOperationTimeout(600)  # 5 sec

# Connect to AWS IoT
if aws_client.connect():
    print("Connected to AWS IoT")
else:
    print("Failed to connect to AWS IoT")
    
# MySQL connection function
def connect_to_database():
    try:
        conn = mysql.connector.connect(**db_config)
        return conn
    except mysql.connector.Error as err:
        logger.error(f"Failed to connect to MySQL database: {err}")
        return None

# Insert data into MySQL database
def insert_data(table_name, data):
    conn = connect_to_database()
    if conn:
        try:
            cursor = conn.cursor()
            columns = ', '.join(data.keys())
            placeholders = ', '.join(['%s'] * len(data))
            query = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"
            cursor.execute(query, list(data.values()))
            conn.commit()
            logger.info("Data inserted successfully into MySQL database")
        except mysql.connector.Error as err:
            logger.error(f"Failed to insert data into MySQL database: {err}")
        finally:
            cursor.close()
            conn.close()


# Subscribe to a topic
def custom_callback(client, userdata, message):

    # Append received message to the list
    payload = message.payload.decode('utf-8')
    try:
        data = json.loads(payload)
        mqtt_data_messages.append(data)
        insert_data("door_info", data)  # Insert data into MySQL database
        
    except json.JSONDecodeError:
        logger.error("Failed to decode JSON from message payload")

# Custom callback for sensors topic
def custom_sensors_callback(client, userdata, message):
    
    # Append received message to the list
    payload = message.payload.decode('utf-8')
    try:
        data = json.loads(payload)
        mqtt_sensors_messages.append(data)
        insert_data("room_info", data)  # Insert data into MySQL database
        
    except json.JSONDecodeError:
        logger.error("Failed to decode JSON from message payload")

# Custom callback for alarm topic
def custom_alarm_callback(client, userdata, message):

    
    # Append received message to the list
    payload = message.payload.decode('utf-8')
    try:
        data = json.loads(payload)
        mqtt_alarm_messages.append(data)
        insert_data("alarm_info", data)  # Insert data into MySQL database

    except json.JSONDecodeError:
        logger.error("Failed to decode JSON from message payload")
        
def calculate_temperature_analytics(temperature_data):
    if not temperature_data:
        return None
    temperatures = [entry[2] for entry in temperature_data]  # Assuming temperature is at index 2
    mean_temperature = sum(temperatures) / len(temperatures)
    min_temperature = min(temperatures)
    max_temperature = max(temperatures)
    return {
        'mean': round(mean_temperature, 2),
        'min': min_temperature,
        'max': max_temperature
    }
        
aws_client.subscribe("rpi3/data", 1, custom_callback)
aws_client.subscribe("rpi3/sensors", 1, custom_sensors_callback)
aws_client.subscribe("rpi3/alarm", 1, custom_alarm_callback)





@app.route('/')
def index():
    weather_data = get_weather()
    return render_template('index.html', weather_data=weather_data)


@app.route('/dashboard')
def dashboard():
    conn = connect_to_database()
    if conn:
        try:
            cursor = conn.cursor()
            # 获取alarm_info表中的数据
            query = "SELECT * FROM alarm_info ORDER BY ID DESC LIMIT 10"  # 获取最新的10条记录
            cursor.execute(query)
            alarm_data = cursor.fetchall()

            # 获取door_info表中的数据
            query = "SELECT * FROM door_info ORDER BY ID DESC LIMIT 10"
            cursor.execute(query)
            door_data = cursor.fetchall()

            # 获取room_info表中的数据
            query = "SELECT * FROM room_info ORDER BY ID DESC LIMIT 10"
            cursor.execute(query)
            room_data = cursor.fetchall()

            return render_template('dashboard.html', alarm_data=alarm_data, door_data=door_data, room_data=room_data)
        except mysql.connector.Error as err:
            logger.error(f"Failed to fetch data from MySQL database: {err}")
        finally:
            cursor.close()
            conn.close()
    return "Failed to connect to the database"

@app.route('/room/<room>')
def room_dashboard(room):
    conn = connect_to_database()
    if conn:
        try:
            cursor = conn.cursor()
            # 获取指定房间的alarm_info表中的数据
            query = "SELECT * FROM alarm_info WHERE Room = %s ORDER BY ID DESC LIMIT 10"
            cursor.execute(query, (room,))
            alarm_data = cursor.fetchall()

            # 获取指定房间的door_info表中的数据
            query = "SELECT * FROM door_info WHERE Room = %s ORDER BY ID DESC LIMIT 10"
            cursor.execute(query, (room,))
            door_data = cursor.fetchall()

            # 获取指定房间的room_info表中的数据
            query = "SELECT * FROM room_info WHERE Room = %s ORDER BY ID DESC LIMIT 10"
            cursor.execute(query, (room,))
            room_data = cursor.fetchall()

             # 计算温度分析数据
            temperature_analytics = calculate_temperature_analytics(room_data)
            
            return render_template('room_dashboard.html', room=room, alarm_data=alarm_data, door_data=door_data, room_data=room_data, temperature_analytics=temperature_analytics)
        except mysql.connector.Error as err:
            logger.error(f"Failed to fetch data from MySQL database: {err}")
        finally:
            cursor.close()
            conn.close()
    return "Failed to connect to the database"

@app.route('/open_gate', methods=['POST'])
def open_gate():
    room = request.form['room']
    # 发送控制命令给相应的 IoT 节点
    if room == 'Room 2':
        aws_client.publish("rpi3/control", json.dumps({"command": "open_gate2"}), 1)
        return jsonify({"message": "open gate 2 "})
    elif room == 'Room 3':
        aws_client.publish("rpi3/control", json.dumps({"command": "open_gate3"}), 1)
        return jsonify({"message": "open gate 3 "})
    elif room == 'Room 4':
        aws_client.publish("rpi3/control", json.dumps({"command": "open_gate4"}), 1)
        return jsonify({"message": "open gate 4 "})
    elif room == 'Room 1':
        aws_client.publish("rpi3/control", json.dumps({"command": "open_gate1"}), 1)
        return jsonify({"message": "open gate 1 "})
    else:
        return jsonify({"message": "Gate control not available for this room"})
    
# Route to fetch and process weather data
@app.route('/weather')
def get_weather():
    api_key = "71571ec77edd20067b360cedc54e88a2"
    city = "Kuching"
    url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={api_key}"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        temperature_kelvin = data['main']['temp']
        temperature_celsius =  round(temperature_kelvin - 273.15, 2)  # Convert temperature to Celsius
        humidity = data['main']['humidity']
        weather_description = data['weather'][0]['description']
        return {
            "temperature": temperature_celsius,
            "humidity": humidity,
            "weather_description": weather_description
        }
    else:
        return {"error": "Failed to fetch weather data"}

@app.route('/room_temperature')
def get_room_temperature():
    room = request.args.get('room')
    conn = connect_to_database()
    if conn:
        try:
            cursor = conn.cursor()
            query = "SELECT DateTime, temperature FROM room_info WHERE Room = %s ORDER BY ID DESC LIMIT 10"
            cursor.execute(query, (room,))
            temperature_data = cursor.fetchall()
            # southeast_asia_tz = timezone('Asia/Singapore')
            # converted_data = []
            # for row in temperature_data:
            #     timestamp = row[0]
            #     temperature = row[1]
            #     converted_timestamp = southeast_asia_tz.localize(timestamp)
            #     converted_data.append((converted_timestamp.isoformat(), temperature))
  
            return jsonify({"room": room, "temperature_data": temperature_data})
        except mysql.connector.Error as err:
            logger.error(f"Failed to fetch temperature data from MySQL database: {err}")
        finally:
            cursor.close()
            conn.close()
    return jsonify({"error": "Failed to connect to the database"})

    
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080, debug=True)