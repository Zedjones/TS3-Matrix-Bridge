FROM python

RUN pip3 install poetry

COPY ts3_bot.py /app/ts3_bot.py
COPY pyproject.toml /app/pyproject.toml
COPY poetry.lock /app/poetry.lock

WORKDIR /app/
RUN poetry install
ENTRYPOINT [ "poetry", "run", "python3", "ts3_bot.py" ]