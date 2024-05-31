import time  #Import time library
from AWSIoTPythonSDK.MQTTLib import AWSIoTMQTTClient


# AWS IoT certificate based connection
myMQTTClient = AWSIoTMQTTClient("CloudVM")
# myMQTTClient.configureEndpoint("YOUR.ENDPOINT", 8883)
myMQTTClient.configureEndpoint("a3qhwyg4jcabb4-ats.iot.ap-southeast-1.amazonaws.com", 8883)
myMQTTClient.configureCredentials("/home/ubuntu/swe30011/cert/AmazonRootCA1.pem", "/home/ubuntu/swe30011/cert/9dcdf5ea290a0400a41690f8ebe9e19ffbffb959dc0aa8a440da93f7ab0b3acd-private.pem.key", "/home/ubuntu/swe30011/cert/9dcdf5ea290a0400a41690f8ebe9e19ffbffb959dc0aa8a440da93f7ab0b3acd-certificate.pem.crt")
myMQTTClient.configureOfflinePublishQueueing(-1)  # Infinite offline Publish queueing
myMQTTClient.configureDrainingFrequency(2)  # Draining: 2 Hz
myMQTTClient.configureConnectDisconnectTimeout(10)  # 10 sec
myMQTTClient.configureMQTTOperationTimeout(5)  # 5 sec

#connect and publish
myMQTTClient.connect()
myMQTTClient.publish("cloud/info", "connected", 0)
#myMQTTClient.publish("xxxx/info", "connected", 0)

while 1:
    time.sleep(2)  #Delay of 2 seconds
    
    value = 200
    payload = '{"cloud message: ":'+ str(value) +'}'
    print (payload)
    myMQTTClient.publish("cloud/data", payload, 0)
