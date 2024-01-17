#importation des différents modules
import io
import picamera
import logging
import socketserver
from threading import Condition
from http import server



# ------ CONFIGURATION ------

# CAMERA
FRAMERATE   = 60             # 60fps
RESOLUTION  = '640x480'      # 640pixel par 480pixel
ROTATION    = 180            # rotation de l'image de 180° pour avoir une image à l'endroit

# SERVEUR
IP          = ''             # adresse IP du serveur (laisser vide pour utiliser l'adresse IP de la raspberry)
PORT        = 8000           # port utilisé par le serveur

# HTML
TITLE      = 'Spider Cam'   # titre de la page HTML


# ---------------------------

PAGE = \
f"""
<html>
<head>
    <title>{TITLE}</title>
</head>
<body>
    <center><h1>Spider Cam</h1></center>
    <center><img src="stream.mjpg" width="640" height="480"></center>
</body>
</html>
"""

class StreamingOutput(object):
    def __init__(self):
        self.frame = None
        self.buffer = io.BytesIO()
        self.condition = Condition()

    def write(self, buf):
        if buf.startswith(b'\xff\xd8'):
            self.buffer.truncate()
            with self.condition:
                self.frame = self.buffer.getvalue()
                self.condition.notify_all()
            self.buffer.seek(0)
        return self.buffer.write(buf)

class StreamingHandler(server.BaseHTTPRequestHandler):
    def do_GET(self):
        # redirection de la page d'accueil
        if self.path == '/':
            self.send_response(301)
            self.send_header('Location', '/index.html')
            self.end_headers()

        # affichage de la page HTML
        elif self.path == '/index.html':
            content = PAGE.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.send_header('Content-Length', len(content))
            self.end_headers()
            self.wfile.write(content)

        # affichage du flux vidéo
        elif self.path == '/stream.mjpg':
            self.send_response(200)
            self.send_header('Age', 0)
            self.send_header('Cache-Control', 'no-cache, private')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=FRAME')
            self.end_headers()
            try:
                while True:
                    with output.condition:
                        output.condition.wait()
                        frame = output.frame
                    self.wfile.write(b'--FRAME\r\n')
                    self.send_header('Content-Type', 'image/jpeg')
                    self.send_header('Content-Length', len(frame))
                    self.end_headers()
                    self.wfile.write(frame)
                    self.wfile.write(b'\r\n')
            except Exception as e:
                logging.warning(
                    'Removed streaming client %s: %s',
                    self.client_address, str(e))
        else:
            self.send_error(404)
            self.end_headers()

class StreamingServer(socketserver.ThreadingMixIn, server.HTTPServer):
    allow_reuse_address = True
    daemon_threads = True

with picamera.PiCamera(resolution=RESOLUTION, framerate=FRAMERATE) as camera:
    # initialisation du flux vidéo
    output = StreamingOutput()
  
    # configuration de la caméra
    camera.rotation = ROTATION

    # démarrage du flux vidéo
    camera.start_recording(output, format='mjpeg')
    try:
        # démarrage du serveur
        address = (IP, PORT)
        server = StreamingServer(address, StreamingHandler)
        server.serve_forever()
    finally:
        camera.stop_recording()
