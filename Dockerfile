FROM ubuntu:18.04
RUN apt-get update -y && \
    apt-get install -y python3-pip libpq-dev 

COPY ./requirements.txt /app/requirements.txt
RUN pip3 install -r /app/requirements.txt

WORKDIR /app
COPY . .
ENV PLAID_CLIENT_ID=5e717f8b062e7500146bfedc
ENV PLAID_PUBLIC_KEY=fd4fdc88940c3e8ad4bdafc8e1cdb5
ENV PLAID_SECRET=3a807e1be3a56c9c40378286eb6cb8
ENV PLAID_ENV=sandbox
ENV SQLALCHEMY_DATABASE_URI=postgresql://masteruser:productimpulses@maindb.cuwtgivgs05r.us-west-1.rds.amazonaws.com/impulses_dev
ENV FLASK_APP=application
ENV FLASK_RUN_PORT=8000
ENV LC_ALL=C.UTF-8
ENV LANG=C.UTF-8

CMD [ "flask", "run", "--host=0.0.0.0"]