import json
import subprocess

topic_name = 'impulses-customer'
topic_arn = 'arn:aws:sns:us-west-2:941468269564:impulses-customer'
protocal = 'sms'
message = 'file://messages/message.txt'
message = 'leishoua'
#phone_numbers = ['+1-702-505-6593','+1-415-819-2258','+1-415-767-8665','+1-615-483-1195','+1-336-782-0775']
#phone_numbers = ['+1-415-819-2258']
phone_numbers = ['+1-415-370-2693']

def create_topic(topic_name):
	subprocess.call(['bash','aws_cli/aws_create_topic.sh', topic_name])

def opt_in(phone_number):
	subprocess.call(['bash','aws_cli/aws_opt_in.sh', phone_number])

def subscribe(phone_number,
			  topic_arn=topic_arn,
			  protocal=protocal):
	subprocess.call(['bash','aws_cli/aws_add_customer.sh', topic_arn, protocal, phone_number])

def publish(phone_number,
			message=message):
	subprocess.call(['bash','aws_cli/aws_publish.sh', message, phone_number])

if __name__ == '__main__':
	for phone_number in phone_numbers:
		subscribe(phone_number)
		opt_in(phone_number)
		publish(phone_number)
		publish(phone_number)

