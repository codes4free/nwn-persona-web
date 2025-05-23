FROM python:3.8-slim
WORKDIR /app
ENV PATH="/usr/local/bin:$PATH"
RUN rm -f /usr/local/bin/python && ln -s /usr/local/bin/python3.8 /usr/local/bin/python
COPY . .
RUN pip install --upgrade pip && pip install -r requirements-web.txt
EXPOSE 5000
CMD ["sh", "start_web.sh"] 