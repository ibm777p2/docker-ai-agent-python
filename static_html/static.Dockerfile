# declare what image to use
#FROM image_name:latest
FROM python:3.14-slim

WORKDIR /app
#next.js
#reach static app
#vue static app
# COPY local_folder container_folder
#RUN mkdir -p /static_folder
#COPY ./static_html /static_folder


#same destination is /app
#COPY ./static_html / app
COPY ./src .
#RUN echo "hello" > index.html

#docker build -f Dockerfile -t pyapp .
#docket run pyapp
#docker build -f Dockerfile -t ibm777p2/ai-pyapp:latest .
#docker push ibm777p2/ai-pyapp:latest

#docker build -f Dockerfile -t ibm777p2/ai-pyapp:v1 .
#docker push ibm777p2/ai-pyapp:v1

#python -m http.server 8000
#docker run -it -p 3030:8000 pyapp
CMD ["python", "-m", "http.server", "8000"]