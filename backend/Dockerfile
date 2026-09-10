FROM python:3.14-slim
#Create python virtual enviroment
#isolate your python app and install from system-level python
RUN python -m venv /opt/venv/
ENV PATH=/opt/venv/bin:$PATH


WORKDIR /app

#COPY local_folder/file container_destination
COPY requirements.txt /tmp/requirements.txt

#RUN within_container_while_building
RUN pip install -r /tmp/requirements.txt

COPY ./src .

CMD ["python", "-m", "http.server", "8000"]