FROM python:3.9.4-buster
RUN pip3 install pipenv
WORKDIR /work-dir
COPY ./Pipfile /work-dir/Pipfile
COPY ./Downloader.py /work-dir/downloader.py
COPY ./config.json /work-dir/config.json
RUN pipenv install
CMD [ "/usr/local/bin/pipenv", "run", "python", "Downloader.py" ]