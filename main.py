import datetime
import json
import logging

import ffmpeg
from google.cloud import storage
import os
from urllib import parse
import settings
import consumers
import random

# stream = ffmpeg.input('input.mp4')

# stream = ffmpeg.input('https://firebasestorage.googleapis.com/v0/b/subtitles-a6e05.appspot.com/o/maxim.kvando%2Fmp4-aac.mp4?alt=media&token=3eff4767-ec9c-4f2a-b1bf-b430d66838f1')
# audio_s = stream.audio
# stream = ffmpeg.output(audio_s, 'out.mp3')

# stream = ffmpeg.filter(stream, 'rotate', 90*3.14/180)
# stream = ffmpeg.drawtext(stream, 'test text bla bla bla', box=1)
# stream = ffmpeg.output(stream, 'output.mp4')

# ffmpeg.run(stream)


class Transport:
    def upload(self):
        raise NotImplementedError


class FirebaseStorageTransport(Transport):

    def __init__(self, from_filename='out.mp3', to_filename='/tmp/out.mp3'):
        self.to_filename = to_filename
        self.from_filename = from_filename
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = settings.CREDITIONALS_JSON
        self.client = storage.Client()
        self.bucket = self.client.get_bucket(settings.FIREBASE_STORAGE_BUCKET)

    def upload(self):
        blob = self.bucket.blob(self.to_filename)
        blob.upload_from_filename(self.from_filename)


class AudioExtractor:
    def __init__(self, url_from, url_to=None, transport=None):
        self.url_from = url_from
        self.url_to = url_to  # не нужен наверн

        # изначально урла выгядит как storage/?/username/filename
        # из урлы получим имя файла и директорию (имя пользователя является именем директории)
        # имя звукового файла будет именем видеофайла только с расширением mp3
        unparsed = parse.urlparse(self.url_from)
        patch = parse.unquote(unparsed.path)
        self.directory, self.filename = patch.split('/')[-2:]
        filename = self.filename.split('.')[0]
        filename += '.mp3'
        self.filename = filename
        self.sample_rate_hertz = 24000  # TODO: разобраться откуда брать

        if transport:
            self.transport = transport
        else:
            self.transport = FirebaseStorageTransport(to_filename=os.path.join(self.directory, self.filename),
                                                      from_filename=self.filename)
            print(self.transport.to_filename)

    def extract_and_upload_to_storage(self):
        stream = ffmpeg.input(self.url_from).audio
        stream = ffmpeg.output(stream, self.filename)
        ffmpeg.run(stream)
        self.transport.upload()
        print('upload complete')
        os.remove(self.filename)  #TODO: хранение во временной папке ОС
        url = f'gs://{settings.FIREBASE_STORAGE_BUCKET}/{os.path.join(self.directory, self.filename)}'
        return url

    def notify(self):
        pass


class VideoresizerAmqpConsumer(consumers.AmqpConsumer):
    EXCHANGE = settings.EXCHANGE
    QUEUE = settings.QUEUE_IN
    ROUTING_KEY = settings.ROUTING_KEY

    def on_message(self, _unused_channel, basic_deliver, properties, body):
        try:
            request = json.loads(body)
        except json.JSONDecodeError as e:
            self.logger.error(f'Invalid json: {e}')
            self.acknowledge_message(basic_deliver.delivery_tag)
            return

        # проверка на то, что приложение от которого пришел json в списке разрешенных
        if not properties and properties.app_id not in settings.ALLOWED_APP_ID:
            self.logger.error(f'App id {properties.app_id} not allowed.')
            self.acknowledge_message(basic_deliver.delivery_tag)
            return

        try:
            job = request['job']
            url = request['url']
            language_code = request['language_code']
        except KeyError as e:
            self.logger.error(f'Access to field in json object is invalid. {e}')
            self.acknowledge_message(basic_deliver.delivery_tag)
            return

        if job == 'audio-extract-and-recognize':
            self.logger.info(f'START {job} on {language_code} with {url}')
            extractor = AudioExtractor(url)
            storage_url = extractor.extract_and_upload_to_storage()
            result = {'url': storage_url,
                      'language_code': language_code,
                      'sample_rate_hertz': extractor.sample_rate_hertz,
                      }
            self.logger.info(f'Formed a result: {result}')

            result = json.dumps(result)
            properties.app_id = 'suptitle.videoresizer'
            properties.timestamp = datetime.datetime.now().timestamp()

            self._channel.basic_publish('', settings.QUEUE_STT, result, properties)

        super().on_message(_unused_channel, basic_deliver, properties, body)


def main():
    logging.basicConfig(level=settings.LOG_LEVEL, format=settings.LOG_FORMAT)
    consumer = consumers.ReconnectingAmqpConsumer(settings.BROKER, VideoresizerAmqpConsumer)
    consumer.run()


if __name__ == '__main__':
    main()
